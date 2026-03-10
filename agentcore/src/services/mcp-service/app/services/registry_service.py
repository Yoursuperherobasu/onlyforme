"""CRUD operations for the MCP server registry."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.registry import (
    McpRegistry,
    McpRegistryCreate,
    McpRegistryRead,
    McpRegistryUpdate,
)
from app.utils.crypto import decrypt_json, encrypt_json

logger = logging.getLogger(__name__)


async def create_server(
    session: AsyncSession,
    data: McpRegistryCreate,
    encryption_key: str,
) -> McpRegistryRead:
    """Register a new MCP server."""
    row = McpRegistry(
        server_name=data.server_name,
        description=data.description,
        mode=data.mode,
        url=data.url,
        command=data.command,
        args=data.args,
        is_active=data.is_active,
        created_by=data.created_by,
        # Tenancy / RBAC fields
        deployment_env=getattr(data, "deployment_env", "DEV"),
        status=getattr(data, "status", "disconnected"),
        org_id=data.org_id,
        dept_id=data.dept_id,
        visibility=getattr(data, "visibility", "private"),
        public_scope=data.public_scope,
        public_dept_ids=data.public_dept_ids,
        shared_user_ids=data.shared_user_ids,
        approval_status=getattr(data, "approval_status", "approved"),
        requested_by=data.requested_by,
        request_to=data.request_to,
        created_by_id=data.created_by_id,
    )

    if data.env_vars and encryption_key:
        row.env_vars_encrypted = encrypt_json(data.env_vars, encryption_key)
    if data.headers and encryption_key:
        row.headers_encrypted = encrypt_json(data.headers, encryption_key)

    session.add(row)
    await session.commit()
    await session.refresh(row)
    return McpRegistryRead.from_orm_model(row)


async def get_servers(
    session: AsyncSession,
    *,
    active_only: bool = True,
) -> list[McpRegistryRead]:
    """Return all MCP servers, optionally filtered by active status."""
    stmt = select(McpRegistry)
    if active_only:
        stmt = stmt.where(McpRegistry.is_active.is_(True))
    stmt = stmt.order_by(McpRegistry.server_name)

    result = await session.execute(stmt)
    rows = result.scalars().all()
    return [McpRegistryRead.from_orm_model(r) for r in rows]


async def get_server(session: AsyncSession, server_id: UUID) -> McpRegistryRead | None:
    """Return a single MCP server by ID."""
    row = await session.get(McpRegistry, server_id)
    if row is None:
        return None
    return McpRegistryRead.from_orm_model(row)


async def get_server_by_name(session: AsyncSession, server_name: str) -> McpRegistryRead | None:
    """Return a single MCP server by name."""
    stmt = select(McpRegistry).where(McpRegistry.server_name == server_name)
    result = await session.execute(stmt)
    row = result.scalars().first()
    if row is None:
        return None
    return McpRegistryRead.from_orm_model(row)


async def update_server(
    session: AsyncSession,
    server_id: UUID,
    data: McpRegistryUpdate,
    encryption_key: str,
) -> McpRegistryRead | None:
    """Update an existing MCP server."""
    row = await session.get(McpRegistry, server_id)
    if row is None:
        return None

    update_fields = data.model_dump(exclude_unset=True)

    # Handle secrets separately
    plain_env_vars = update_fields.pop("env_vars", None)
    if plain_env_vars is not None and encryption_key:
        row.env_vars_encrypted = encrypt_json(plain_env_vars, encryption_key) if plain_env_vars else None

    plain_headers = update_fields.pop("headers", None)
    if plain_headers is not None and encryption_key:
        row.headers_encrypted = encrypt_json(plain_headers, encryption_key) if plain_headers else None

    for field, value in update_fields.items():
        setattr(row, field, value)

    row.updated_at = datetime.now(timezone.utc)
    session.add(row)
    await session.commit()
    await session.refresh(row)
    return McpRegistryRead.from_orm_model(row)


async def delete_server(session: AsyncSession, server_id: UUID) -> bool:
    """Hard-delete an MCP server. Returns True if the row existed."""
    row = await session.get(McpRegistry, server_id)
    if row is None:
        return False
    await session.delete(row)
    await session.commit()
    return True


async def get_decrypted_config_by_id(
    session: AsyncSession,
    server_id: UUID,
    encryption_key: str,
) -> tuple[str, dict] | None:
    """Return (server_name, config_dict) with decrypted secrets, looked up by ID."""
    row = await session.get(McpRegistry, server_id)
    if row is None:
        return None

    config: dict = {}

    if row.mode == "sse":
        if row.url:
            config["url"] = row.url
        if row.headers_encrypted and encryption_key:
            config["headers"] = decrypt_json(row.headers_encrypted, encryption_key)
    elif row.mode == "stdio":
        if row.command:
            config["command"] = row.command
        if row.args:
            config["args"] = row.args

    if row.env_vars_encrypted and encryption_key:
        config["env"] = decrypt_json(row.env_vars_encrypted, encryption_key)

    return row.server_name, config


async def get_decrypted_config(
    session: AsyncSession,
    server_name: str,
    encryption_key: str,
) -> dict | None:
    """Return the full MCP server config with decrypted secrets."""
    stmt = select(McpRegistry).where(McpRegistry.server_name == server_name)
    result = await session.execute(stmt)
    row = result.scalars().first()
    if row is None:
        return None

    config: dict = {}

    if row.mode == "sse":
        if row.url:
            config["url"] = row.url
        if row.headers_encrypted and encryption_key:
            config["headers"] = decrypt_json(row.headers_encrypted, encryption_key)
    elif row.mode == "stdio":
        if row.command:
            config["command"] = row.command
        if row.args:
            config["args"] = row.args

    # Env vars apply to both modes
    if row.env_vars_encrypted and encryption_key:
        config["env"] = decrypt_json(row.env_vars_encrypted, encryption_key)

    return config
