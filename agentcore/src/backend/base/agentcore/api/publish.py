"""Agent publish endpoints."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field
from sqlmodel import select

from agentcore.api.utils import CurrentActiveUser, DbSession
from agentcore.services.database.models.agent.model import Agent
from agentcore.services.database.models.user.model import User
from agentcore.services.database.models.user_department_membership.model import UserDepartmentMembership

router = APIRouter(prefix="/publish", tags=["Publish"])


class PublishRequest(BaseModel):
    """Request schema for publishing an agent."""

    agent_id: UUID = Field(..., description="UUID of the agent to publish")


class PublishResponse(BaseModel):
    """Response schema for publish operation."""

    detail: str


class UnpublishRequest(BaseModel):
    """Request schema for unpublishing an agent."""

    agent_id: UUID = Field(..., description="UUID of the agent to unpublish")


class ValidatePublishEmailResponse(BaseModel):
    """Validation response for publish recipient emails."""

    agent_id: UUID
    email: str
    department_id: UUID | None
    exists_in_department: bool
    message: str


async def _current_user_department_ids(session: DbSession, user_id: UUID) -> set[UUID]:
    rows = (
        await session.exec(
            select(UserDepartmentMembership.department_id).where(
                UserDepartmentMembership.user_id == user_id,
                UserDepartmentMembership.status == "active",
            )
        )
    ).all()
    return set(rows)


@router.get("/agents")
async def get_published_agents() -> list[dict]:
    """Get all published agents. Stubbed for now."""
    return []


@router.post("/", status_code=501, response_model=PublishResponse)
async def publish_agent(request: PublishRequest) -> PublishResponse:
    """Publish an agent. Stubbed."""
    raise HTTPException(status_code=501, detail="Publish API not implemented.")


@router.delete("/", status_code=501, response_model=PublishResponse)
async def unpublish_agent(request: UnpublishRequest) -> PublishResponse:
    """Unpublish an agent. Stubbed."""
    raise HTTPException(status_code=501, detail="Unpublish API not implemented.")


@router.get("/status/{agent_id}", status_code=501, response_model=PublishResponse)
async def get_publish_status(agent_id: UUID) -> PublishResponse:
    """Get publish status. Stubbed."""
    raise HTTPException(status_code=501, detail="Publish status API not implemented.")


@router.get("/validate-email", response_model=ValidatePublishEmailResponse)
async def validate_publish_email(
    *,
    agent_id: UUID = Query(..., description="Agent ID"),
    email: str = Query(..., description="Recipient email to validate"),
    session: DbSession,
    current_user: CurrentActiveUser,
) -> ValidatePublishEmailResponse:
    """Validate that an email exists in the same department(s) as the current user."""
    normalized_email = str(email).strip().lower()
    if "@" not in normalized_email:
        raise HTTPException(status_code=400, detail="Invalid email format.")

    agent = await session.get(Agent, agent_id)
    if not agent or agent.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Agent not found.")

    current_user_dept_ids = await _current_user_department_ids(session, current_user.id)
    if not current_user_dept_ids:
        return ValidatePublishEmailResponse(
            agent_id=agent_id,
            email=normalized_email,
            department_id=None,
            exists_in_department=False,
            message="Current user has no active department mapping.",
        )

    user = (
        await session.exec(
            select(User).where(
                (User.username.ilike(normalized_email)) | (User.email.ilike(normalized_email)),
            )
        )
    ).first()

    if not user:
        return ValidatePublishEmailResponse(
            agent_id=agent_id,
            email=normalized_email,
            department_id=next(iter(current_user_dept_ids)),
            exists_in_department=False,
            message="Email not found in user table for this department.",
        )

    memberships = (
        await session.exec(
            select(UserDepartmentMembership).where(
                UserDepartmentMembership.user_id == user.id,
                UserDepartmentMembership.department_id.in_(list(current_user_dept_ids)),
                UserDepartmentMembership.status == "active",
            )
        )
    ).all()

    exists_in_department = len(memberships) > 0
    resolved_department_id = memberships[0].department_id if memberships else next(iter(current_user_dept_ids))
    return ValidatePublishEmailResponse(
        agent_id=agent_id,
        email=normalized_email,
        department_id=resolved_department_id,
        exists_in_department=exists_in_department,
        message=(
            "Email found in this department."
            if exists_in_department
            else "Email exists, but not in this department."
        ),
    )
