# Router for base api
from fastapi import APIRouter

from agentcore.api.api_key import router as api_key_router
from agentcore.api.chat import router as chat_router
from agentcore.api.endpoints import router as endpoints_router
from agentcore.api.files_agent import router as files_router
from agentcore.api.files_user import router as files_router_user
from agentcore.api.agent import router as agents_router
from agentcore.api.login import router as login_router
from agentcore.api.mcp_server import router as mcp_router
from agentcore.api.registry import router as registry_router
from agentcore.api.mcp_projects import router as mcp_projects_router
from agentcore.api.mcp_config import router as mcp_router_config
from agentcore.api.monitor import router as monitor_router
from agentcore.api.observability import router as observability_router
from agentcore.api.evaluation import router as evaluation_router
from agentcore.api.projects import router as projects_router
from agentcore.api.publish import router as publish_router
from agentcore.api.approvals import router as approvals_router
from agentcore.api.starter_projects import router as starter_projects_router
from agentcore.api.store import router as store_router
from agentcore.api.users import router as users_router
from agentcore.api.validate import router as validate_router
from agentcore.api.variable import router as variables_router
from agentcore.api.roles import router as roles_router
from agentcore.api.approvals import router as approvals_router
from agentcore.api.cache import router as cache_router
from agentcore.api.control_panel import router as control_panel_router

router = APIRouter(
    prefix="/api",
)

router.include_router(chat_router)
router.include_router(approvals_router)
router.include_router(endpoints_router)
router.include_router(validate_router)
router.include_router(agents_router)
router.include_router(users_router)
router.include_router(api_key_router)
router.include_router(login_router)
router.include_router(variables_router)
router.include_router(files_router)
router.include_router(monitor_router)
router.include_router(projects_router)
router.include_router(publish_router)
router.include_router(registry_router)
router.include_router(starter_projects_router)
router.include_router(store_router)
router.include_router(mcp_router)
router.include_router(mcp_projects_router)
router.include_router(observability_router)
router.include_router(evaluation_router)
router.include_router(files_router_user)
router.include_router(mcp_router_config)
router.include_router(roles_router)
router.include_router(approvals_router)
router.include_router(control_panel_router)
router.include_router(cache_router)