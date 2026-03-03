import base64
import hashlib
import os
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


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

    raw = os.getenv("WEBUI_SECRET_KEY", "default-agentcore-registry-key")
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
