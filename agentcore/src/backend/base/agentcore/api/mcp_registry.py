"""REST endpoints for the MCP server registry.

All operations proxy through the MCP microservice.
"""

from __future__ import annotations

import logging
from uuid import UUID

from fastapi import APIRouter, HTTPException

from agentcore.api.utils import CurrentActiveUser, DbSession
from agentcore.services.database.models.mcp_registry.model import (
    McpRegistryCreate,
    McpRegistryRead,
    McpRegistryUpdate,
    McpTestConnectionRequest,
    McpTestConnectionResponse,
    McpProbeResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/mcp/registry", tags=["MCP Registry"])


# ---------------------------------------------------------------------------
# CRUD
# ---------------------------------------------------------------------------


@router.get("/", response_model=list[McpRegistryRead])
async def list_mcp_servers(
    session: DbSession,
    current_user: CurrentActiveUser,
    active_only: bool = True,
):
    """List all registered MCP servers."""
    from agentcore.services.mcp_service_client import fetch_mcp_servers_async

    return await fetch_mcp_servers_async(active_only=active_only)


@router.post("/", response_model=McpRegistryRead, status_code=201)
async def create_mcp_server(
    body: McpRegistryCreate,
    session: DbSession,
    current_user: CurrentActiveUser,
):
    """Register a new MCP server."""
    from agentcore.services.mcp_service_client import create_mcp_server_via_service

    if not body.created_by and current_user:
        body.created_by = current_user.username

    return await create_mcp_server_via_service(body.model_dump())


@router.get("/{server_id}", response_model=McpRegistryRead)
async def get_mcp_server(
    server_id: UUID,
    session: DbSession,
    current_user: CurrentActiveUser,
):
    """Get a single MCP server by ID."""
    from agentcore.services.mcp_service_client import get_mcp_server_via_service

    result = await get_mcp_server_via_service(str(server_id))
    if result is None:
        raise HTTPException(status_code=404, detail="MCP server not found")
    return result


@router.put("/{server_id}", response_model=McpRegistryRead)
async def update_mcp_server(
    server_id: UUID,
    body: McpRegistryUpdate,
    session: DbSession,
    current_user: CurrentActiveUser,
):
    """Update an existing MCP server."""
    from agentcore.services.mcp_service_client import update_mcp_server_via_service

    result = await update_mcp_server_via_service(str(server_id), body.model_dump(exclude_unset=True))
    if result is None:
        raise HTTPException(status_code=404, detail="MCP server not found")
    return result


@router.delete("/{server_id}", status_code=204)
async def delete_mcp_server(
    server_id: UUID,
    session: DbSession,
    current_user: CurrentActiveUser,
):
    """Delete a registered MCP server."""
    from agentcore.services.mcp_service_client import delete_mcp_server_via_service

    deleted = await delete_mcp_server_via_service(str(server_id))
    if not deleted:
        raise HTTPException(status_code=404, detail="MCP server not found")


# ---------------------------------------------------------------------------
# Test connection
# ---------------------------------------------------------------------------


@router.post("/test-connection", response_model=McpTestConnectionResponse)
async def test_mcp_connection(
    body: McpTestConnectionRequest,
    current_user: CurrentActiveUser,
):
    """Test connectivity to an MCP server via the microservice."""
    from agentcore.services.mcp_service_client import test_mcp_connection_via_service

    try:
        return await test_mcp_connection_via_service(body.model_dump())
    except Exception as e:
        logger.warning("MCP test connection via microservice failed: %s", e)
        return McpTestConnectionResponse(success=False, message=str(e))


# ---------------------------------------------------------------------------
# Probe registered server
# ---------------------------------------------------------------------------


@router.post("/{server_id}/probe", response_model=McpProbeResponse)
async def probe_mcp_server(
    server_id: UUID,
    session: DbSession,
    current_user: CurrentActiveUser,
):
    """Probe a registered MCP server via the microservice."""
    from agentcore.services.mcp_service_client import probe_mcp_server_via_service

    try:
        return await probe_mcp_server_via_service(str(server_id))
    except HTTPException:
        raise
    except Exception as e:
        logger.warning("MCP probe via microservice failed for server %s: %s", server_id, e)
        return McpProbeResponse(success=False, message=str(e))
