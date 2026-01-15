from typing import List, Dict
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
    "developer": [ACTIONS["EDIT_FLOWS"], ],
    "viewer": [ACTIONS["VIEW_FILES_TAB"]]
}

def get_permissions_for_role(role: str) -> List[str]:
    # Superusers always get all permissions
    if role == "admin":
        return list(ACTIONS.values())
    perms = ROLE_PERMISSIONS.get(role.lower(), [])
    logger.debug(f"Role: {role} | Permissions found: {perms}")
    return ROLE_PERMISSIONS.get(role.lower(), [])