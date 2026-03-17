from __future__ import annotations

import json
import logging
from functools import lru_cache
from pathlib import Path

from pydantic import BaseModel
from pydantic_settings import BaseSettings, SettingsConfigDict

logger = logging.getLogger(__name__)

_ROOT_ENV = Path(__file__).resolve().parents[1] / ".env"


# ---------------------------------------------------------------------------
# Region model
# ---------------------------------------------------------------------------

class RegionEntry(BaseModel):
    code: str                          # ISO 3166-1 alpha-2 e.g. "AE"
    name: str                          # Display name e.g. "UAE"
    api_url: str                       # Private Link / VNet-peered URL
    is_hub: bool = False               # True for the hub's own entry
    tenant_id: str | None = None       # Azure AD tenant ID (for cross-tenant)
    client_id: str | None = None       # App Registration client ID on spoke
    audience: str | None = None        # Token audience e.g. "api://agentcore-spoke-sa"


# ---------------------------------------------------------------------------
# Application settings
# ---------------------------------------------------------------------------

class Settings(BaseSettings):
    host: str = "0.0.0.0"
    port: int = 8006
    log_level: str = "info"
    cors_origins: str = "*"

    # Path to regions.json (relative to working dir or absolute)
    regions_file: str = "regions.json"

    # Azure Key Vault (optional — if set, regions are loaded from KV secret)
    key_vault_url: str | None = None
    key_vault_regions_secret: str = "agentcore-region-registry"

    # Azure Managed Identity client ID for the hub (used to acquire spoke tokens)
    hub_mi_client_id: str | None = None

    # Request timeouts (seconds)
    proxy_timeout: int = 10
    health_check_timeout: int = 5

    # Skip MI auth in dev mode (spokes on localhost)
    skip_spoke_auth: bool = False

    model_config = SettingsConfigDict(
        env_prefix="REGION_GATEWAY_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()


# ---------------------------------------------------------------------------
# Region registry loader
# ---------------------------------------------------------------------------

_regions: list[RegionEntry] = []


def load_regions(settings: Settings | None = None) -> list[RegionEntry]:
    """Load regions from JSON file or Azure Key Vault secret."""
    global _regions
    if settings is None:
        settings = get_settings()

    raw: str | None = None

    # 1. Try Key Vault first (production)
    if settings.key_vault_url:
        try:
            from azure.identity import DefaultAzureCredential
            from azure.keyvault.secrets import SecretClient

            credential = DefaultAzureCredential()
            client = SecretClient(vault_url=settings.key_vault_url, credential=credential)
            secret = client.get_secret(settings.key_vault_regions_secret)
            raw = secret.value
            logger.info("Loaded regions from Key Vault secret '%s'", settings.key_vault_regions_secret)
        except Exception:
            logger.warning("Failed to load regions from Key Vault, falling back to file", exc_info=True)

    # 2. Fallback to JSON file
    if raw is None:
        regions_path = Path(settings.regions_file)
        if not regions_path.is_absolute():
            regions_path = Path(__file__).resolve().parents[1] / regions_path
        if regions_path.exists():
            raw = regions_path.read_text(encoding="utf-8")
            logger.info("Loaded regions from file '%s'", regions_path)
        else:
            logger.warning("No regions file found at '%s', starting with empty registry", regions_path)
            _regions = []
            return _regions

    if raw:
        data = json.loads(raw)
        _regions = [RegionEntry(**entry) for entry in data]

    return _regions


def get_regions() -> list[RegionEntry]:
    return _regions


def get_region_by_code(code: str) -> RegionEntry | None:
    code_upper = code.upper()
    for region in _regions:
        if region.code.upper() == code_upper:
            return region
    return None
