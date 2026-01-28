from typing import Optional
import json
import redis.asyncio as redis

from langbuilder.services.database.models.user.model import User
from langbuilder.services.settings.service import SettingsService
from .redis_client import get_redis_client


class UserCacheService:
    def __init__(self, settings_service: SettingsService):
        self.redis = get_redis_client(settings_service)
        self.ttl = settings_service.settings.redis_cache_expire

    async def get_user(self, user_id: str) -> Optional[dict]:
        key = f"user:{user_id}"
        data_str = await self.redis.get(key)
        return json.loads(data_str) if data_str else None

    async def set_user(self, user: User):
        key = f"user:{user.id}"
        # 🔐 IMPORTANT: exclude password
        data_str = user.model_dump_json(exclude={"password"})
        await self.redis.setex(key, self.ttl, data_str)

    async def delete_user(self, user_id: str):
        await self.redis.delete(f"user:{user_id}")