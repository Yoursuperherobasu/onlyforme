import base64
import hashlib
import logging
import os
from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

logger = logging.getLogger(__name__)

_ROOT_ENV = Path(__file__).resolve().parents[4] / ".env"


def _read_root_env_key(name: str) -> str:
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
                return v.strip().strip("'\"")
    except Exception:
        pass
    return ""


def _derive_encryption_key() -> str:
    key = os.getenv("GRAPH_RAG_SERVICE_ENCRYPTION_KEY", "").strip()
    if key and key not in ("your-secret-key-here", "your-fernet-key-here"):
        return key

    raw = os.getenv("WEBUI_SECRET_KEY", "").strip()
    if not raw:
        raw = _read_root_env_key("WEBUI_SECRET_KEY")
    if not raw:
        raw = "default-agentcore-registry-key"
        logger.warning(
            "No GRAPH_RAG_SERVICE_ENCRYPTION_KEY or WEBUI_SECRET_KEY set — "
            "using default key. Set a proper key for production!"
        )

    derived = hashlib.sha256(raw.encode()).digest()
    return base64.urlsafe_b64encode(derived).decode()


class Settings(BaseSettings):
    api_key: str = ""
    host: str = "0.0.0.0"
    port: int = 8004
    log_level: str = "info"
    cors_origins: str = "*"
    database_url: str | None = None
    encryption_key: str = ""

    # Neo4j
    neo4j_uri: str = ""
    neo4j_username: str = "neo4j"
    neo4j_password: str = ""
    neo4j_database: str = "neo4j"

    # Batch sizes
    ingest_batch_size: int = 100
    embed_batch_size: int = 200

    model_config = SettingsConfigDict(
        env_prefix="GRAPH_RAG_SERVICE_",
        env_file=".env",
        env_file_encoding="utf-8",
    )


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    if not settings.encryption_key or settings.encryption_key in (
        "your-secret-key-here",
        "your-fernet-key-here",
    ):
        settings.encryption_key = _derive_encryption_key()
    # Also read NEO4J vars from root .env if not set via prefix
    if not settings.neo4j_uri:
        settings.neo4j_uri = os.getenv("NEO4J_URI", "") or _read_root_env_key("NEO4J_URI")
    if settings.neo4j_username == "neo4j":
        val = os.getenv("NEO4J_USERNAME", "") or _read_root_env_key("NEO4J_USERNAME")
        if val:
            settings.neo4j_username = val
    if not settings.neo4j_password:
        settings.neo4j_password = os.getenv("NEO4J_PASSWORD", "") or _read_root_env_key("NEO4J_PASSWORD")
    return settings
