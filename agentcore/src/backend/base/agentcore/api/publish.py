"""AgentCore Publish API.

[PUBLISH STUBBED] All OpenWebUI integration removed.
These are dummy endpoints — will be replaced with internal portal publish.
"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

router = APIRouter(prefix="/publish", tags=["Publish"])


# ── Stub schemas ──────────────────────────────────────────────────────────────

class PublishRequest(BaseModel):
    """Request schema for publishing a flow."""

    agent_id: UUID = Field(..., description="UUID of the flow to publish")


class PublishResponse(BaseModel):
    """Response schema for publish operation."""

    detail: str


class UnpublishRequest(BaseModel):
    """Request schema for unpublishing a flow."""

    agent_id: UUID = Field(..., description="UUID of the flow to unpublish")


# ── Stub routes ───────────────────────────────────────────────────────────────

@router.get("/flows")
async def get_published_flows() -> list[dict]:
    """Get all published flows. [PUBLISH STUBBED]"""
    return []


@router.post("/", status_code=501, response_model=PublishResponse)
async def publish_flow(request: PublishRequest) -> PublishResponse:
    """Publish a flow. [PUBLISH STUBBED] — migrating to internal portal."""
    raise HTTPException(status_code=501, detail="Publish API not implemented — migrating to internal portal.")


@router.delete("/", status_code=501, response_model=PublishResponse)
async def unpublish_flow(request: UnpublishRequest) -> PublishResponse:
    """Unpublish a flow. [PUBLISH STUBBED] — migrating to internal portal."""
    raise HTTPException(status_code=501, detail="Unpublish API not implemented — migrating to internal portal.")


@router.get("/status/{agent_id}", status_code=501, response_model=PublishResponse)
async def get_publish_status(agent_id: UUID) -> PublishResponse:
    """Get publish status. [PUBLISH STUBBED] — migrating to internal portal."""
    raise HTTPException(status_code=501, detail="Publish status API not implemented — migrating to internal portal.")
