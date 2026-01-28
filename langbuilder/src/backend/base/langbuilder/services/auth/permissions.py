from typing import List, Dict, Optional
import redis.asyncio as redis
from langbuilder.services.settings.service import SettingsService
from langbuilder.services.cache.redis_client import get_redis_client
from loguru import logger


# Define granular actions
ACTIONS = {
    "VIEW_DASHBOARD": "view_dashboard",
    "MANAGE_USERS": "manage_users",
    "EDIT_FLOWS": "edit_flows",
    "VIEW_COSTS": "view_costs",
    "VIEW_FILES_TAB": "view_files_tab",
}

# The Production Mapping
ROLE_PERMISSIONS: Dict[str, List[str]] = {
    "admin": [ACTIONS["VIEW_DASHBOARD"], ACTIONS["MANAGE_USERS"], ACTIONS["EDIT_FLOWS"], ACTIONS["VIEW_COSTS"], ACTIONS["VIEW_FILES_TAB"]],
    "manager": [ACTIONS["VIEW_DASHBOARD"], ACTIONS["EDIT_FLOWS"], ACTIONS["VIEW_COSTS"], ACTIONS["VIEW_FILES_TAB"]],
    "developer": [ACTIONS["VIEW_DASHBOARD"], ],
    "viewer": [ACTIONS["VIEW_FILES_TAB"]]
}

class PermissionCacheService:
    def __init__(self, settings_service: SettingsService):
        self.redis = get_redis_client(settings_service)
        self.ttl = settings_service.settings.redis_cache_expire

    async def get_permissions_for_role(self, role: str) -> List[str]:
        key = f"role:{role.lower()}"
        cached = await self.redis.get(key)

        if cached:
            return cached.split(",")  # Deserialize list
        perms = ROLE_PERMISSIONS.get(role.lower(), [])
        key = f"role:{role.lower()}"
        await self.redis.set(key, ",".join(perms), ex=self.ttl)
        logger.debug(f"Role: {role} | Permissions cached: {perms}")
        return perms


permission_cache: Optional[PermissionCacheService] = None

async def get_permissions_for_role(role: str) -> List[str]: 
    if permission_cache:
        return await permission_cache.get_permissions_for_role(role)
    return ROLE_PERMISSIONS.get(role.lower(), [])