from __future__ import annotations

import os


class RabbitMQConfig:
    """Configuration for RabbitMQ connection, read from environment variables."""

    def __init__(self) -> None:
        self.enabled: bool = os.getenv("RABBITMQ_ENABLED", "false").lower() in ("true", "1", "yes")
        self.host: str = os.getenv("RABBITMQ_HOST", "localhost")
        self.port: int = int(os.getenv("RABBITMQ_PORT", "5672"))
        self.user: str = os.getenv("RABBITMQ_USER", "guest")
        self.password: str = os.getenv("RABBITMQ_PASSWORD", "guest")
        self.vhost: str = os.getenv("RABBITMQ_VHOST", "/")
        self.prefetch_count: int = int(os.getenv("RABBITMQ_PREFETCH_COUNT", "5"))
        self.build_queue: str = os.getenv("RABBITMQ_BUILD_QUEUE", "agentcore.build")
        self.run_queue: str = os.getenv("RABBITMQ_RUN_QUEUE", "agentcore.run")
        self.retry_max: int = int(os.getenv("RABBITMQ_RETRY_MAX", "3"))
        # Per-queue retry overrides (falls back to RABBITMQ_RETRY_MAX)
        self.build_retry_max: int = int(os.getenv("RABBITMQ_BUILD_RETRY_MAX", str(self.retry_max)))
        self.run_retry_max: int = int(os.getenv("RABBITMQ_RUN_RETRY_MAX", str(self.retry_max)))
        self.reconnect_delay: float = float(os.getenv("RABBITMQ_RECONNECT_DELAY", "5.0"))

    @property
    def url(self) -> str:
        return os.getenv(
            "RABBITMQ_URL",
            f"amqp://{self.user}:{self.password}@{self.host}:{self.port}/{self.vhost}",
        )
