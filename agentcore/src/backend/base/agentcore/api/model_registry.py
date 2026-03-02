"""REST endpoints for the model registry.

All operations proxy through the Model microservice.
"""

from __future__ import annotations

import logging
from uuid import UUID

from fastapi import APIRouter, HTTPException

from agentcore.api.utils import CurrentActiveUser, DbSession
from agentcore.services.database.models.model_registry.model import (
    ModelRegistryCreate,
    ModelRegistryRead,
    ModelRegistryUpdate,
    TestConnectionRequest,
    TestConnectionResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/models/registry", tags=["Model Registry"])


# ---------------------------------------------------------------------------
# CRUD
# ---------------------------------------------------------------------------


@router.get("/", response_model=list[ModelRegistryRead])
async def list_registry_models(
    session: DbSession,
    current_user: CurrentActiveUser,
    provider: str | None = None,
    environment: str | None = None,
    model_type: str | None = None,
    active_only: bool = True,
):
    """List all registered models, optionally filtered by provider, environment, and/or model type."""
    from agentcore.services.model_service_client import fetch_registry_models_async

    return await fetch_registry_models_async(
        provider=provider, environment=environment, model_type=model_type, active_only=active_only
    )


@router.post("/", response_model=ModelRegistryRead, status_code=201)
async def create_registry_model(
    body: ModelRegistryCreate,
    session: DbSession,
    current_user: CurrentActiveUser,
):
    """Register a new model."""
    from agentcore.services.model_service_client import create_registry_model_via_service

    if not body.created_by and current_user:
        body.created_by = current_user.username

    return await create_registry_model_via_service(body.model_dump())


@router.get("/{model_id}", response_model=ModelRegistryRead)
async def get_registry_model(
    model_id: UUID,
    session: DbSession,
    current_user: CurrentActiveUser,
):
    """Get a single registered model by ID."""
    from agentcore.services.model_service_client import get_registry_model_via_service

    result = await get_registry_model_via_service(str(model_id))
    if result is None:
        raise HTTPException(status_code=404, detail="Model not found")
    return result


@router.put("/{model_id}", response_model=ModelRegistryRead)
async def update_registry_model(
    model_id: UUID,
    body: ModelRegistryUpdate,
    session: DbSession,
    current_user: CurrentActiveUser,
):
    """Update an existing registered model."""
    from agentcore.services.model_service_client import update_registry_model_via_service

    result = await update_registry_model_via_service(str(model_id), body.model_dump(exclude_unset=True))
    if result is None:
        raise HTTPException(status_code=404, detail="Model not found")
    return result


@router.delete("/{model_id}", status_code=204)
async def delete_registry_model(
    model_id: UUID,
    session: DbSession,
    current_user: CurrentActiveUser,
):
    """Delete a registered model."""
    from agentcore.services.model_service_client import delete_registry_model_via_service

    deleted = await delete_registry_model_via_service(str(model_id))
    if not deleted:
        raise HTTPException(status_code=404, detail="Model not found")


# ---------------------------------------------------------------------------
# Test connection
# ---------------------------------------------------------------------------


@router.post("/test-connection", response_model=TestConnectionResponse)
async def test_model_connection(
    body: TestConnectionRequest,
    current_user: CurrentActiveUser,
):
    """Test an LLM connection via the microservice."""
    from agentcore.services.model_service_client import test_connection_via_service

    try:
        return await test_connection_via_service(body.model_dump())
    except Exception as e:
        logger.warning("Test connection via microservice failed: %s", e)
        return TestConnectionResponse(success=False, message=str(e))


# ---------------------------------------------------------------------------
# Test embedding connection
# ---------------------------------------------------------------------------


@router.post("/test-embedding-connection", response_model=TestConnectionResponse)
async def test_embedding_connection(
    body: TestConnectionRequest,
    current_user: CurrentActiveUser,
):
    """Test an embedding connection via the microservice."""
    from agentcore.services.model_service_client import test_embedding_connection_via_service

    try:
        return await test_embedding_connection_via_service(body.model_dump())
    except Exception as e:
        logger.warning("Test embedding connection via microservice failed: %s", e)
        return TestConnectionResponse(success=False, message=str(e))
