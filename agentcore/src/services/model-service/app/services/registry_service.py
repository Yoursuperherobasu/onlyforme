"""CRUD operations for the model registry."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.registry import (
    ModelRegistry,
    ModelRegistryCreate,
    ModelRegistryRead,
    ModelRegistryUpdate,
)
from app.utils.crypto import decrypt_api_key, encrypt_api_key

logger = logging.getLogger(__name__)


async def create_model(
    session: AsyncSession,
    data: ModelRegistryCreate,
    encryption_key: str,
) -> ModelRegistryRead:
    """Insert a new model into the registry."""
    row = ModelRegistry(
        display_name=data.display_name,
        description=data.description,
        provider=data.provider,
        model_name=data.model_name,
        model_type=data.model_type,
        base_url=data.base_url,
        environment=data.environment,
        provider_config=data.provider_config,
        capabilities=data.capabilities,
        default_params=data.default_params,
        is_active=data.is_active,
        created_by=data.created_by,
        # Tenancy / RBAC fields
        org_id=data.org_id,
        dept_id=data.dept_id,
        public_dept_ids=data.public_dept_ids,
        created_by_id=data.created_by_id,
        visibility_scope=data.visibility_scope,
        approval_status=data.approval_status,
        requested_by=data.requested_by,
        request_to=data.request_to,
    )

    if data.api_key and encryption_key:
        row.api_key_encrypted = encrypt_api_key(data.api_key, encryption_key)

    session.add(row)
    await session.commit()
    await session.refresh(row)
    return ModelRegistryRead.from_orm_model(row)


async def get_models(
    session: AsyncSession,
    *,
    provider: str | None = None,
    environment: str | None = None,
    model_type: str | None = None,
    active_only: bool = True,
) -> list[ModelRegistryRead]:
    """Return all registry entries, optionally filtered."""
    stmt = select(ModelRegistry)
    if active_only:
        stmt = stmt.where(ModelRegistry.is_active.is_(True))
    if provider:
        stmt = stmt.where(ModelRegistry.provider == provider)
    if environment:
        stmt = stmt.where(ModelRegistry.environment == environment)
    if model_type:
        stmt = stmt.where(ModelRegistry.model_type == model_type)
    stmt = stmt.order_by(ModelRegistry.provider, ModelRegistry.display_name)

    result = await session.execute(stmt)
    rows = result.scalars().all()
    return [ModelRegistryRead.from_orm_model(r) for r in rows]


async def get_model(session: AsyncSession, model_id: UUID) -> ModelRegistryRead | None:
    """Return a single registry entry by ID."""
    row = await session.get(ModelRegistry, model_id)
    if row is None:
        return None
    return ModelRegistryRead.from_orm_model(row)


async def update_model(
    session: AsyncSession,
    model_id: UUID,
    data: ModelRegistryUpdate,
    encryption_key: str,
) -> ModelRegistryRead | None:
    """Update an existing registry entry."""
    row = await session.get(ModelRegistry, model_id)
    if row is None:
        return None

    update_fields = data.model_dump(exclude_unset=True)

    # Handle API key separately
    plain_key = update_fields.pop("api_key", None)
    if plain_key and encryption_key:
        row.api_key_encrypted = encrypt_api_key(plain_key, encryption_key)

    for field, value in update_fields.items():
        setattr(row, field, value)

    row.updated_at = datetime.now(timezone.utc)
    session.add(row)
    await session.commit()
    await session.refresh(row)
    return ModelRegistryRead.from_orm_model(row)


async def delete_model(session: AsyncSession, model_id: UUID) -> bool:
    """Hard-delete a registry entry. Returns True if the row existed."""
    row = await session.get(ModelRegistry, model_id)
    if row is None:
        return False
    await session.delete(row)
    await session.commit()
    return True


async def get_decrypted_config(
    session: AsyncSession,
    model_id: UUID,
    encryption_key: str,
) -> dict | None:
    """Return the full config with decrypted API key.  Internal use only (chat completions)."""
    row = await session.get(ModelRegistry, model_id)
    if row is None:
        return None

    config: dict = {
        "provider": row.provider,
        "model_name": row.model_name,
        "model_type": row.model_type,
        "base_url": row.base_url,
        "environment": row.environment,
        "provider_config": row.provider_config or {},
        "capabilities": row.capabilities or {},
        "default_params": row.default_params or {},
    }

    if row.api_key_encrypted and encryption_key:
        config["api_key"] = decrypt_api_key(row.api_key_encrypted, encryption_key)
    else:
        config["api_key"] = ""

    return config
