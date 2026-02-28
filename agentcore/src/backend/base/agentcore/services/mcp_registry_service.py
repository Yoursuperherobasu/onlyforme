"""CRUD operations for the MCP server registry."""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select
from sqlmodel.ext.asyncio.session import AsyncSession

from agentcore.services.database.models.mcp_registry.model import (
    McpRegistry,
    McpRegistryCreate,
    McpRegistryRead,
    McpRegistryUpdate,
)
from agentcore.utils.crypto import decrypt_api_key, encrypt_api_key

logger = logging.getLogger(__name__)


def _encryption_key() -> str:
    """Return the encryption key from environment."""
    key = os.getenv("MODEL_REGISTRY_ENCRYPTION_KEY", "")
    if not key:
        raw = os.getenv("WEBUI_SECRET_KEY", "default-agentcore-registry-key")
        import base64
        import hashlib

        derived = hashlib.sha256(raw.encode()).digest()
        key = base64.urlsafe_b64encode(derived).decode()
    return key


def _encrypt_json(data: dict, enc_key: str) -> str:
    """Encrypt a dict as JSON string."""
    return encrypt_api_key(json.dumps(data), enc_key)


def _decrypt_json(encrypted: str, enc_key: str) -> dict:
    """Decrypt an encrypted JSON string back to dict."""
    return json.loads(decrypt_api_key(encrypted, enc_key))


async def create_server(
    session: AsyncSession,
    data: McpRegistryCreate,
) -> McpRegistryRead:
    """Register a new MCP server."""
    enc_key = _encryption_key()
    row = McpRegistry(
        server_name=data.server_name,
        description=data.description,
        mode=data.mode,
        url=data.url,
        command=data.command,
        args=data.args,
        is_active=data.is_active,
        created_by=data.created_by,
    )

    if data.env_vars and enc_key:
        row.env_vars_encrypted = _encrypt_json(data.env_vars, enc_key)
    if data.headers and enc_key:
        row.headers_encrypted = _encrypt_json(data.headers, enc_key)

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
) -> McpRegistryRead | None:
    """Update an existing MCP server."""
    enc_key = _encryption_key()
    row = await session.get(McpRegistry, server_id)
    if row is None:
        return None

    update_fields = data.model_dump(exclude_unset=True)

    # Handle secrets separately
    plain_env_vars = update_fields.pop("env_vars", None)
    if plain_env_vars is not None and enc_key:
        row.env_vars_encrypted = _encrypt_json(plain_env_vars, enc_key) if plain_env_vars else None

    plain_headers = update_fields.pop("headers", None)
    if plain_headers is not None and enc_key:
        row.headers_encrypted = _encrypt_json(plain_headers, enc_key) if plain_headers else None

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
) -> tuple[str, dict] | None:
    """Return (server_name, config_dict) with decrypted secrets, looked up by ID."""
    enc_key = _encryption_key()
    row = await session.get(McpRegistry, server_id)
    if row is None:
        return None

    config: dict = {}

    if row.mode == "sse":
        if row.url:
            config["url"] = row.url
        if row.headers_encrypted and enc_key:
            config["headers"] = _decrypt_json(row.headers_encrypted, enc_key)
    elif row.mode == "stdio":
        if row.command:
            config["command"] = row.command
        if row.args:
            config["args"] = row.args

    if row.env_vars_encrypted and enc_key:
        config["env"] = _decrypt_json(row.env_vars_encrypted, enc_key)

    return row.server_name, config


async def get_decrypted_config(
    session: AsyncSession,
    server_name: str,
) -> dict | None:
    """Return the full MCP server config with decrypted secrets. Internal use only (components)."""
    enc_key = _encryption_key()
    stmt = select(McpRegistry).where(McpRegistry.server_name == server_name)
    result = await session.execute(stmt)
    row = result.scalars().first()
    if row is None:
        return None

    config: dict = {}

    if row.mode == "sse":
        if row.url:
            config["url"] = row.url
        if row.headers_encrypted and enc_key:
            config["headers"] = _decrypt_json(row.headers_encrypted, enc_key)
    elif row.mode == "stdio":
        if row.command:
            config["command"] = row.command
        if row.args:
            config["args"] = row.args

    # Env vars apply to both modes
    if row.env_vars_encrypted and enc_key:
        config["env"] = _decrypt_json(row.env_vars_encrypted, enc_key)

    return config
