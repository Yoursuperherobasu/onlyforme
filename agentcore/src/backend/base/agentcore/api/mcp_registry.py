"""REST endpoints for the MCP server registry."""

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
    McpToolInfo,
)
from agentcore.services import mcp_registry_service

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
    return await mcp_registry_service.get_servers(session, active_only=active_only)


@router.post("/", response_model=McpRegistryRead, status_code=201)
async def create_mcp_server(
    body: McpRegistryCreate,
    session: DbSession,
    current_user: CurrentActiveUser,
):
    """Register a new MCP server."""
    if not body.created_by and current_user:
        body.created_by = current_user.username
    return await mcp_registry_service.create_server(session, body)


@router.get("/{server_id}", response_model=McpRegistryRead)
async def get_mcp_server(
    server_id: UUID,
    session: DbSession,
    current_user: CurrentActiveUser,
):
    """Get a single MCP server by ID."""
    server = await mcp_registry_service.get_server(session, server_id)
    if server is None:
        raise HTTPException(status_code=404, detail="MCP server not found")
    return server


@router.put("/{server_id}", response_model=McpRegistryRead)
async def update_mcp_server(
    server_id: UUID,
    body: McpRegistryUpdate,
    session: DbSession,
    current_user: CurrentActiveUser,
):
    """Update an existing MCP server."""
    server = await mcp_registry_service.update_server(session, server_id, body)
    if server is None:
        raise HTTPException(status_code=404, detail="MCP server not found")
    return server


@router.delete("/{server_id}", status_code=204)
async def delete_mcp_server(
    server_id: UUID,
    session: DbSession,
    current_user: CurrentActiveUser,
):
    """Delete a registered MCP server."""
    deleted = await mcp_registry_service.delete_server(session, server_id)
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
    """Test connectivity to an MCP server and return the number of tools discovered."""
    try:
        from agentcore.base.mcp.util import update_tools

        # Build config in the format expected by update_tools
        server_config: dict = {}
        if body.mode == "sse":
            if body.url:
                server_config["url"] = body.url
            if body.headers:
                server_config["headers"] = body.headers
        elif body.mode == "stdio":
            if body.command:
                server_config["command"] = body.command
            if body.args:
                server_config["args"] = body.args

        if body.env_vars:
            server_config["env"] = body.env_vars

        _, tool_list, _ = await update_tools(
            server_name="test-connection",
            server_config=server_config,
        )

        return McpTestConnectionResponse(
            success=True,
            message=f"Connected successfully. Found {len(tool_list)} tool(s).",
            tools_count=len(tool_list),
        )
    except Exception as e:
        logger.warning("MCP test connection failed: %s", e)
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
    """Probe a registered MCP server: test connectivity and discover tools."""
    try:
        from agentcore.base.mcp.util import update_tools

        result = await mcp_registry_service.get_decrypted_config_by_id(session, server_id)
        if result is None:
            raise HTTPException(status_code=404, detail="MCP server not found")

        server_name, server_config = result

        _, tool_list, _ = await update_tools(
            server_name=server_name,
            server_config=server_config,
        )

        tools_info = [
            McpToolInfo(name=t.name, description=t.description or "")
            for t in tool_list
        ]

        return McpProbeResponse(
            success=True,
            message=f"Connected successfully. Found {len(tool_list)} tool(s).",
            tools_count=len(tool_list),
            tools=tools_info,
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.warning("MCP probe failed for server %s: %s", server_id, e)
        return McpProbeResponse(success=False, message=str(e))
