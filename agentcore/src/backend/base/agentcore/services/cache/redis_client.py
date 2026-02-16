from typing import Optional
import redis.asyncio as redis
from agentcore.services.settings.service import SettingsService

_redis_client: Optional[redis.StrictRedis] = None

def get_redis_client(settings_service: SettingsService) -> redis.StrictRedis:
    global _redis_client
    if _redis_client is None:
        _redis_client = redis.StrictRedis(
            host=settings_service.settings.redis_host,
            port=settings_service.settings.redis_port,
            db=settings_service.settings.redis_db,
            password=settings_service.settings.redis_password,
            ssl=settings_service.settings.redis_ssl,
            decode_responses=True,
            socket_connect_timeout=5,
            socket_timeout=5,
        )
    return _redis_client
