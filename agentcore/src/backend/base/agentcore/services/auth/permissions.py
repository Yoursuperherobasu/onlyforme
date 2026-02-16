from typing import List, Dict, Optional
from loguru import logger
from agentcore.services.settings.service import SettingsService
from agentcore.services.cache.redis_client import get_redis_client
from agentcore.services.deps import session_scope
from agentcore.services.database.models.role import Role
from agentcore.services.database.models.permission import Permission
from agentcore.services.database.models.role_permission import RolePermission
from sqlmodel import select, text


ROLE_ALIASES = {
    "admin": "super_admin",
    "super admin": "super_admin",
    "department admin": "department_admin",
    "business user": "business_user",
}


def _normalize_role(role: str) -> str:
    normalized = role.strip().lower().replace(" ", "_")
    return ROLE_ALIASES.get(normalized, normalized)


def normalize_role(role: str) -> str:
    return _normalize_role(role)


ACTIONS = {
    "VIEW_DASHBOARD": "view_dashboard",
    "MANAGE_USERS": "manage_users",
    "EDIT_FLOWS": "edit_flows",
    "VIEW_COSTS": "view_costs",
    "VIEW_FILES_TAB": "view_files_tab",
    "VIEW_ADMIN_PAGE": "view_admin_page",
    "VIEW_ACCESS_CONTROL_PAGE": "view_access_control_page",
    "MANAGE_ROLES": "manage_roles",
    "VIEW_FLOWS_PAGE": "view_flows_page",
    "VIEW_COMPONENTS_PAGE": "view_components_page",
    "VIEW_ASSETS_FILES_TAB": "view_assets_files_tab",
    "VIEW_ASSETS_KNOWLEDGE_TAB": "view_assets_knowledge_tab",
    "VIEW_SETTINGS_PAGE": "view_settings_page",
    "VIEW_SETTINGS_GLOBAL_VARIABLES_TAB": "view_settings_global_variables_tab",
    "VIEW_SETTINGS_API_KEYS_TAB": "view_settings_api_keys_tab",
    "VIEW_SETTINGS_SHORTCUTS_TAB": "view_settings_shortcuts_tab",
    "VIEW_SETTINGS_MESSAGES_TAB": "view_settings_messages_tab",
    "VIEW_MCP_SERVERS_PAGE": "view_mcp_servers_page",
    "VIEW_MODEL_CATALOGUE_PAGE": "view_model_catalogue_page",
    "VIEW_AGENT_CATALOGUE_PAGE": "view_agent_catalogue_page",
    "VIEW_ORCHESTRATOR_PAGE": "view_orchestrator_page",
    "VIEW_GUARDRAILS_PAGE": "view_guardrails_page",
    "VIEW_VECTOR_DB_PAGE": "view_vector_db_page",
    "VIEW_OBSERVABILITY_DASHBOARD": "view_observability_dashboard",
    "VIEW_APPROVAL_PAGE": "view_approval_page",
    "VIEW_TIMEOUT_SETTINGS_PAGE": "view_timeout_settings_page",
    "VIEW_WORKFLOWS_PAGE": "view_workflows_page",
    "VIEW_PLAYGROUND_PAGE": "view_playground_page",
    "VIEW_FLOW_EDITOR": "view_flow_editor",
}

ROLE_PERMISSIONS: Dict[str, List[str]] = {
    "super_admin": [
        ACTIONS["VIEW_DASHBOARD"],
        ACTIONS["MANAGE_USERS"],
        ACTIONS["EDIT_FLOWS"],
        ACTIONS["VIEW_COSTS"],
        ACTIONS["VIEW_FILES_TAB"],
        ACTIONS["VIEW_ADMIN_PAGE"],
        ACTIONS["VIEW_ACCESS_CONTROL_PAGE"],
        ACTIONS["MANAGE_ROLES"],
        ACTIONS["VIEW_FLOWS_PAGE"],
        ACTIONS["VIEW_COMPONENTS_PAGE"],
        ACTIONS["VIEW_ASSETS_FILES_TAB"],
        ACTIONS["VIEW_ASSETS_KNOWLEDGE_TAB"],
        ACTIONS["VIEW_SETTINGS_PAGE"],
        ACTIONS["VIEW_SETTINGS_GLOBAL_VARIABLES_TAB"],
        ACTIONS["VIEW_SETTINGS_API_KEYS_TAB"],
        ACTIONS["VIEW_SETTINGS_SHORTCUTS_TAB"],
        ACTIONS["VIEW_SETTINGS_MESSAGES_TAB"],
        ACTIONS["VIEW_MCP_SERVERS_PAGE"],
        ACTIONS["VIEW_MODEL_CATALOGUE_PAGE"],
        ACTIONS["VIEW_AGENT_CATALOGUE_PAGE"],
        ACTIONS["VIEW_ORCHESTRATOR_PAGE"],
        ACTIONS["VIEW_GUARDRAILS_PAGE"],
        ACTIONS["VIEW_VECTOR_DB_PAGE"],
        ACTIONS["VIEW_OBSERVABILITY_DASHBOARD"],
        ACTIONS["VIEW_APPROVAL_PAGE"],
        ACTIONS["VIEW_TIMEOUT_SETTINGS_PAGE"],
        ACTIONS["VIEW_WORKFLOWS_PAGE"],
        ACTIONS["VIEW_PLAYGROUND_PAGE"],
        ACTIONS["VIEW_FLOW_EDITOR"],
    ],
    "department_admin": [
        ACTIONS["VIEW_DASHBOARD"],
        ACTIONS["EDIT_FLOWS"],
        ACTIONS["VIEW_COSTS"],
        ACTIONS["VIEW_FILES_TAB"],
        ACTIONS["VIEW_ADMIN_PAGE"],
        ACTIONS["VIEW_ACCESS_CONTROL_PAGE"],
        ACTIONS["MANAGE_USERS"],
        ACTIONS["MANAGE_ROLES"],
        ACTIONS["VIEW_FLOWS_PAGE"],
        ACTIONS["VIEW_COMPONENTS_PAGE"],
        ACTIONS["VIEW_ASSETS_FILES_TAB"],
        ACTIONS["VIEW_ASSETS_KNOWLEDGE_TAB"],
        ACTIONS["VIEW_AGENT_CATALOGUE_PAGE"],
        ACTIONS["VIEW_SETTINGS_PAGE"],
        ACTIONS["VIEW_SETTINGS_GLOBAL_VARIABLES_TAB"],
        ACTIONS["VIEW_SETTINGS_API_KEYS_TAB"],
        ACTIONS["VIEW_SETTINGS_SHORTCUTS_TAB"],
        ACTIONS["VIEW_SETTINGS_MESSAGES_TAB"],
        ACTIONS["VIEW_FLOW_EDITOR"],
    ],
    "developer": [
        ACTIONS["VIEW_DASHBOARD"],
        ACTIONS["VIEW_FLOWS_PAGE"],
        ACTIONS["VIEW_COMPONENTS_PAGE"],
        ACTIONS["VIEW_ASSETS_FILES_TAB"],
        ACTIONS["VIEW_SETTINGS_PAGE"],
        ACTIONS["VIEW_SETTINGS_SHORTCUTS_TAB"],
        ACTIONS["VIEW_AGENT_CATALOGUE_PAGE"],
        ACTIONS["VIEW_FLOW_EDITOR"],
        ACTIONS["EDIT_FLOWS"],
    ],
    "business_user": [
        ACTIONS["VIEW_DASHBOARD"],
        ACTIONS["VIEW_FLOWS_PAGE"],
        ACTIONS["VIEW_COMPONENTS_PAGE"],
        ACTIONS["VIEW_ASSETS_FILES_TAB"],
        ACTIONS["VIEW_FLOW_EDITOR"],
    ],
}

PERMISSION_VERSION = "v3"  # 🔥 bump this when permissions change


class PermissionCacheService:
    def __init__(self, settings_service: SettingsService):
        self.redis = get_redis_client(settings_service)
        self.ttl = settings_service.settings.redis_cache_expire

    async def get_permissions_for_role(self, role: str) -> List[str]:
        role = _normalize_role(role)
        key = f"role:{PERMISSION_VERSION}:{role}"

        cached = await self.redis.get(key)
        if cached:
            if isinstance(cached, bytes):
                cached = cached.decode("utf-8")
            cached = str(cached)
            if cached.strip():
                perms = cached.split(",")
                if perms != [""]:
                    return perms

        perms = await _get_permissions_for_role_db(role)
        if not perms:
            perms = ROLE_PERMISSIONS.get(role, [])
        await self.redis.set(key, ",".join(perms), ex=self.ttl)

        logger.info(f"RBAC cached → {key} = {perms}")
        return perms


permission_cache: Optional[PermissionCacheService] = None


async def get_permissions_for_role(role: str) -> List[str]:
    if permission_cache is None:
        # 🔥 fallback (no Redis)
        perms = await _get_permissions_for_role_db(_normalize_role(role))
        if perms:
            return perms
        normalized = _normalize_role(role)
        return ROLE_PERMISSIONS.get(normalized, [])

    perms = await permission_cache.get_permissions_for_role(role)
    if perms:
        return perms
    normalized = _normalize_role(role)
    return ROLE_PERMISSIONS.get(normalized, [])


async def _get_permissions_for_role_db(role: str) -> List[str]:
    role = _normalize_role(role)
    async with session_scope() as session:
        role_row = (await session.exec(select(Role).where(Role.name == role))).first()
        if not role_row:
            return []
        stmt = (
            select(Permission.key)
            .select_from(RolePermission)
            .join(Permission, RolePermission.permission_id == Permission.id)
            .where(RolePermission.role_id == role_row.id)
        )
        permissions = (await session.exec(stmt)).all()
        if permissions:
            return list(permissions)

        # Raw SQL fallback (avoids ORM/table name edge cases)
        try:
            return await get_permissions_for_role_session(session, role)
        except Exception:
            return []


async def get_permissions_for_role_session(session, role: str) -> List[str]:
    role = _normalize_role(role)
    raw = await session.exec(
        text(
            "SELECT p.key FROM role_permission rp "
            "JOIN permission p ON p.id = rp.permission_id "
            "JOIN role r ON r.id = rp.role_id "
            "WHERE r.name = :role_name"
        ),
        {"role_name": role},
    )
    return list(raw.all())


async def invalidate_role_permissions_cache(role: str) -> None:
    if not permission_cache:
        return
    role = _normalize_role(role)
    key = f"role:{PERMISSION_VERSION}:{role}"
    try:
        await permission_cache.redis.delete(key)
    except Exception as exc:  # noqa: BLE001
        logger.warning(f"Failed to invalidate permission cache for {role}: {exc}")
