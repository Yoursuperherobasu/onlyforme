"""Spoke-side middleware to authenticate requests from the hub's region-gateway.

When the hub proxies a dashboard request to this spoke, it sends a Bearer token
issued by Azure AD using the hub's Managed Identity. This module validates that
token so the spoke only serves data to the authorized hub.

On spoke deployments: DEPLOYMENT_ROLE=spoke and HUB_MI_OBJECT_ID must be set.
On hub deployments: this middleware is a no-op (hub calls its own local DB).
"""

from __future__ import annotations

import logging
import os

from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

logger = logging.getLogger(__name__)

_bearer_scheme = HTTPBearer(auto_error=False)

# These are read at import time from env vars.
# On hub: DEPLOYMENT_ROLE is "hub" so this middleware does nothing.
# On spoke: DEPLOYMENT_ROLE is "spoke" and HUB_MI_OBJECT_ID is the hub's
#           Managed Identity object ID (from Azure AD).
_DEPLOYMENT_ROLE = os.getenv("DEPLOYMENT_ROLE", "hub").lower()
_HUB_MI_OBJECT_ID = os.getenv("HUB_MI_OBJECT_ID", "")
_SPOKE_AUDIENCE = os.getenv("SPOKE_AUDIENCE", "")


# Cache the JWKS keys to avoid fetching on every request
_jwks_client = None


def _get_jwks_client():
    """Lazily initialize the JWKS client for Azure AD token validation."""
    global _jwks_client
    if _jwks_client is None:
        try:
            import jwt
            _jwks_client = jwt.PyJWKClient(
                "https://login.microsoftonline.com/common/discovery/v2.0/keys",
                cache_jwk_set=True,
                lifespan=3600,
            )
        except ImportError:
            logger.error("PyJWT is required for spoke hub auth. Install: pip install PyJWT[crypto]")
            raise
    return _jwks_client


async def verify_hub_token(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
) -> str | None:
    """Dependency that validates hub-originated requests on spoke deployments.

    Returns:
        The hub caller user ID from X-Hub-Caller header, or None if running as hub.

    Raises:
        HTTPException 401: If token is missing or invalid on spoke deployment.
    """
    # On hub deployment, skip this check entirely
    if _DEPLOYMENT_ROLE != "spoke":
        return None

    # On spoke: if no bearer token, check if this is a normal local frontend request.
    # Local frontend requests use cookie auth (handled by get_current_active_user).
    # Hub requests use Bearer token.
    if credentials is None:
        # No bearer token — this is a local request, let normal auth handle it
        return None

    # Bearer token present — validate it as a hub MI token
    token = credentials.credentials

    try:
        import jwt

        jwks_client = _get_jwks_client()
        signing_key = jwks_client.get_signing_key_from_jwt(token)

        # Decode and validate the token.
        # In cross-tenant scenarios we skip issuer verification because
        # the token comes from the spoke's tenant, not a fixed issuer.
        payload = jwt.decode(
            token,
            signing_key.key,
            algorithms=["RS256"],
            audience=_SPOKE_AUDIENCE if _SPOKE_AUDIENCE else None,
            options={
                "verify_aud": bool(_SPOKE_AUDIENCE),
                "verify_iss": False,
                "verify_exp": True,
            },
        )

        # Verify this token is from the hub's Managed Identity
        token_oid = payload.get("oid", "")
        if _HUB_MI_OBJECT_ID and token_oid != _HUB_MI_OBJECT_ID:
            logger.warning(
                "Token OID '%s' does not match expected hub MI OID '%s'",
                token_oid, _HUB_MI_OBJECT_ID,
            )
            raise HTTPException(status_code=401, detail="Unauthorized: not from hub")

        # Extract caller info
        hub_caller = request.headers.get("X-Hub-Caller")
        hub_request_id = request.headers.get("X-Hub-Request-Id")
        logger.info(
            "Hub request authenticated. caller=%s request_id=%s oid=%s",
            hub_caller, hub_request_id, token_oid,
        )
        return hub_caller

    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Hub token expired")
    except jwt.InvalidTokenError as e:
        logger.warning("Invalid hub token: %s", e)
        raise HTTPException(status_code=401, detail="Invalid hub token")
    except Exception as e:
        logger.error("Hub auth error: %s", e, exc_info=True)
        raise HTTPException(status_code=401, detail="Hub authentication failed")
