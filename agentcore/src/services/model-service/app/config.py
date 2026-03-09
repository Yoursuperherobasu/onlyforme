import base64
import hashlib
import os
from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# Locate the project root .env so we can read WEBUI_SECRET_KEY even when
# this microservice is started as an independent process.
_ROOT_ENV = Path(__file__).resolve().parents[4] / ".env"


def _read_root_env_key(name: str) -> str:
    """Read a single key from the project-root .env file (no shell expansion)."""
    if not _ROOT_ENV.exists():
        return ""
    try:
        for line in _ROOT_ENV.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" not in line:
                continue
            k, _, v = line.partition("=")
            if k.strip() == name:
                v = v.strip().strip("'\"")
                return v
    except Exception:
        pass
    return ""


def _derive_encryption_key() -> str:
    """Derive a Fernet-compatible encryption key.

    Resolution order (matches the main backend):
      1. MODEL_SERVICE_ENCRYPTION_KEY  (explicit, set in .env)
      2. MODEL_REGISTRY_ENCRYPTION_KEY (shared with the main backend)
      3. Derive from WEBUI_SECRET_KEY via SHA-256 → base64url
      4. Derive from a built-in default (dev only)
    """
    key = os.getenv("MODEL_SERVICE_ENCRYPTION_KEY", "").strip()
    if key and key != "your-secret-key-here" and key != "your-fernet-key-here":
        return key

    key = os.getenv("MODEL_REGISTRY_ENCRYPTION_KEY", "").strip()
    if key:
        return key

    # Try OS env first, then fall back to reading the root .env file directly.
    raw = os.getenv("WEBUI_SECRET_KEY", "").strip()
    if not raw:
        raw = _read_root_env_key("WEBUI_SECRET_KEY")
    if not raw:
        raw = "default-agentcore-registry-key"

    derived = hashlib.sha256(raw.encode()).digest()
    return base64.urlsafe_b64encode(derived).decode()


class Settings(BaseSettings):
    api_key: str = ""
    host: str = "0.0.0.0"
    port: int = 8001
    log_level: str = "info"
    cors_origins: str = "*"
    default_timeout: int = 300
    max_retries: int = 1
    database_url: str | None = None
    encryption_key: str = ""
    key_vault_url: str | None = None
    key_vault_secret_prefix: str = "agentcore-model"
    key_vault_tenant_id: str | None = None
    key_vault_client_id: str | None = None
    key_vault_client_secret: str | None = None

    model_config = SettingsConfigDict(
        env_prefix="MODEL_SERVICE_",
        env_file=".env",
        env_file_encoding="utf-8",
    )


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    # If the .env placeholder was loaded, derive a real key instead
    if not settings.encryption_key or settings.encryption_key in (
        "your-secret-key-here",
        "your-fernet-key-here",
    ):
        settings.encryption_key = _derive_encryption_key()
    return settings
