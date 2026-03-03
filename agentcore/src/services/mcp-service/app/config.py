from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    api_key: str = ""
    host: str = "0.0.0.0"
    port: int = 8002
    log_level: str = "info"
    cors_origins: str = "*"
    database_url: str | None = None
    encryption_key: str = ""

    # MCP-specific settings
    server_timeout: int = 20
    max_sessions_per_server: int = 10
    session_idle_timeout: int = 400
    session_cleanup_interval: int = 120

    model_config = SettingsConfigDict(
        env_prefix="MCP_SERVICE_",
        env_file=".env",
        env_file_encoding="utf-8",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
