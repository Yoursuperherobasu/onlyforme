from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


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
    return Settings()
