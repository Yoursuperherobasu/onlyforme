"""CRUD operations for the model registry."""

from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select
from sqlmodel.ext.asyncio.session import AsyncSession

from agentcore.services.database.models.model_registry.model import (
    ModelRegistry,
    ModelRegistryCreate,
    ModelRegistryRead,
    ModelRegistryUpdate,
)
from agentcore.utils.crypto import decrypt_api_key, encrypt_api_key

logger = logging.getLogger(__name__)


def _encryption_key() -> str:
    """Return the encryption key from environment."""
    key = os.getenv("MODEL_REGISTRY_ENCRYPTION_KEY", "")
    if not key:
        # Fallback: derive a Fernet-compatible key from WEBUI_SECRET_KEY or use a default
        # In production, MODEL_REGISTRY_ENCRYPTION_KEY should always be set
        from cryptography.fernet import Fernet

        raw = os.getenv("WEBUI_SECRET_KEY", "default-agentcore-registry-key")
        import base64
        import hashlib

        # Derive a 32-byte key from the secret and base64-encode it for Fernet
        derived = hashlib.sha256(raw.encode()).digest()
        key = base64.urlsafe_b64encode(derived).decode()
    return key


async def create_model(
    session: AsyncSession,
    data: ModelRegistryCreate,
) -> ModelRegistryRead:
    """Insert a new model into the registry."""
    enc_key = _encryption_key()
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
    )

    if data.api_key and enc_key:
        row.api_key_encrypted = encrypt_api_key(data.api_key, enc_key)

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
) -> ModelRegistryRead | None:
    """Update an existing registry entry."""
    enc_key = _encryption_key()
    row = await session.get(ModelRegistry, model_id)
    if row is None:
        return None

    update_fields = data.model_dump(exclude_unset=True)

    # Handle API key separately
    plain_key = update_fields.pop("api_key", None)
    if plain_key and enc_key:
        row.api_key_encrypted = encrypt_api_key(plain_key, enc_key)

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
) -> dict | None:
    """Return the full config with decrypted API key.  Internal use only (components)."""
    enc_key = _encryption_key()
    row = await session.get(ModelRegistry, model_id)
    if row is None:
        return None

    config: dict = {
        "provider": row.provider,
        "model_name": row.model_name,
        "base_url": row.base_url,
        "environment": row.environment,
        "provider_config": row.provider_config or {},
        "capabilities": row.capabilities or {},
        "default_params": row.default_params or {},
    }

    if row.api_key_encrypted and enc_key:
        config["api_key"] = decrypt_api_key(row.api_key_encrypted, enc_key)
    else:
        config["api_key"] = ""

    return config