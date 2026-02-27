from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from agentcore.services.cache.redis_client import get_redis_client
from agentcore.services.deps import get_settings_service


def _revocation_key(user_id: UUID) -> str:
    return f"auth:revoked_after:user:{user_id}"


async def revoke_user_tokens(user_id: UUID) -> None:
    settings_service = get_settings_service()
    redis = get_redis_client(settings_service)
    now_ts = int(datetime.now(timezone.utc).timestamp())
    await redis.set(_revocation_key(user_id), str(now_ts))


async def is_user_token_revoked(user_id: UUID, token_iat: int | None) -> bool:
    settings_service = get_settings_service()
    redis = get_redis_client(settings_service)
    revoked_after = await redis.get(_revocation_key(user_id))
    if not revoked_after:
        return False
    revoked_after_ts = int(revoked_after)
    token_iat_ts = int(token_iat or 0)
    return token_iat_ts <= revoked_after_ts

