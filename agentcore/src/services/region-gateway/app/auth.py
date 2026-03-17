from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field

from app.config import RegionEntry, get_settings

logger = logging.getLogger(__name__)


@dataclass
class _CachedToken:
    token: str
    expires_at: float  # unix timestamp


@dataclass
class SpokeAuthService:
    """Acquires Azure AD tokens to authenticate hub → spoke API calls.

    Supports cross-tenant authentication using multi-tenant app registrations
    or Azure Lighthouse. Each spoke can be in a different Azure AD tenant.
    """

    _token_cache: dict[str, _CachedToken] = field(default_factory=dict)

    async def get_token(self, region: RegionEntry) -> str | None:
        """Get a valid bearer token for the given spoke region.

        Returns None if auth is skipped (dev mode) or region has no audience.
        """
        settings = get_settings()

        if settings.skip_spoke_auth:
            return None

        if not region.audience:
            logger.debug("No audience configured for region '%s', skipping auth", region.code)
            return None

        # Check cache (refresh 5 minutes before expiry)
        cached = self._token_cache.get(region.code)
        if cached and cached.expires_at > (time.time() + 300):
            return cached.token

        # Acquire fresh token
        token_str, expires_at = await self._acquire_token(region)
        self._token_cache[region.code] = _CachedToken(token=token_str, expires_at=expires_at)
        logger.info("Acquired MI token for region '%s' (expires in %.0fs)", region.code, expires_at - time.time())
        return token_str

    async def _acquire_token(self, region: RegionEntry) -> tuple[str, float]:
        """Acquire token from Azure AD using Managed Identity.

        For cross-tenant scenarios:
        - Hub MI must be a multi-tenant app OR
        - Hub MI must have Azure Lighthouse access to spoke tenant OR
        - Use client credentials flow with a cross-tenant app registration

        The DefaultAzureCredential handles MI on Azure, and falls back to
        environment credentials / Azure CLI for local development.
        """
        from azure.identity.aio import DefaultAzureCredential, ManagedIdentityCredential

        settings = get_settings()

        # Use ManagedIdentityCredential if hub MI client ID is specified,
        # otherwise fall back to DefaultAzureCredential (works in dev with az login)
        if settings.hub_mi_client_id:
            credential = ManagedIdentityCredential(client_id=settings.hub_mi_client_id)
        else:
            credential = DefaultAzureCredential()

        try:
            # For cross-tenant: the audience must be an app registration
            # that the hub's MI is authorized to access.
            # The spoke's app registration must have the hub MI's app ID
            # listed as an authorized client application.
            scope = f"{region.audience}/.default"
            token = await credential.get_token(scope)
            return token.token, token.expires_on
        finally:
            await credential.close()


# Singleton
spoke_auth = SpokeAuthService()
