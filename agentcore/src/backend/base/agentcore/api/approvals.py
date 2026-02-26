"""Approval API router backed by database tables.

This exposes approval requests for approvers (department admins) and lets them
approve/reject pending PROD publish requests.
"""

from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, File, Form, HTTPException, UploadFile, status
from loguru import logger
from pydantic import BaseModel
from sqlmodel import select

from agentcore.api.utils import CurrentActiveUser, DbSession
from agentcore.services.database.models.agent.model import Agent
from agentcore.services.database.models.agent_deployment_prod.model import (
    AgentDeploymentProd,
    DeploymentPRODStatusEnum,
    ProdDeploymentLifecycleEnum,
)
from agentcore.services.database.models.agent_registry.model import RegistryDeploymentEnvEnum
from agentcore.services.database.models.approval_request.model import (
    ApprovalDecisionEnum,
    ApprovalRequest,
)
from agentcore.services.database.models.folder.model import Folder
from agentcore.services.database.models.user.model import User
from agentcore.services.database.registry_service import sync_agent_registry


class SubmittedBy(BaseModel):
    name: str
    avatar: str | None = None


class ApprovalAgent(BaseModel):
    id: str
    title: str
    status: str  # pending, approved, rejected
    description: str
    submittedBy: SubmittedBy
    project: str
    submitted: str
    version: str
    recentChanges: str
    adminComments: str | None = None
    adminAttachments: list[dict] | None = None


class ApprovalPreviewResponse(BaseModel):
    id: str
    title: str
    version: str
    snapshot: dict


class ApprovalResponse(BaseModel):
    success: bool
    message: str
    agentId: str
    newStatus: str
    timestamp: str
    approvedBy: str | None = None


router = APIRouter(prefix="/approvals", tags=["approvals"])


def _to_status_label(decision: ApprovalDecisionEnum | None) -> str:
    if decision is None:
        return "pending"
    if decision == ApprovalDecisionEnum.APPROVED:
        return "approved"
    return "rejected"


def _humanize_age(ts: datetime) -> str:
    now = datetime.now(timezone.utc)
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=timezone.utc)
    delta = now - ts
    total_sec = max(int(delta.total_seconds()), 0)
    if total_sec < 60:
        return f"{total_sec}s ago"
    if total_sec < 3600:
        return f"{total_sec // 60}m ago"
    if total_sec < 86400:
        return f"{total_sec // 3600}h ago"
    return f"{total_sec // 86400}d ago"


def _is_global_approver(user: CurrentActiveUser) -> bool:
    return str(getattr(user, "role", "")).lower() in {"root", "super_admin"}


async def _get_approval_for_action(
    *,
    session: DbSession,
    approval_or_agent_id: str,
    current_user: CurrentActiveUser,
) -> ApprovalRequest:
    req: ApprovalRequest | None = None
    target_uuid: UUID | None = None
    try:
        target_uuid = UUID(approval_or_agent_id)
    except Exception:
        target_uuid = None

    if target_uuid:
        req = (await session.exec(select(ApprovalRequest).where(ApprovalRequest.id == target_uuid))).first()

    if not req and target_uuid:
        stmt = (
            select(ApprovalRequest)
            .where(ApprovalRequest.agent_id == target_uuid)
            .where(ApprovalRequest.decision == None)  # noqa: E711
            .order_by(ApprovalRequest.requested_at.desc())
        )
        if not _is_global_approver(current_user):
            stmt = stmt.where(ApprovalRequest.request_to == current_user.id)
        req = (await session.exec(stmt)).first()

    if not req:
        raise HTTPException(status_code=404, detail="Approval request not found")

    if not _is_global_approver(current_user) and req.request_to != current_user.id:
        raise HTTPException(status_code=403, detail="Not allowed to act on this approval")

    return req


async def _get_approval_for_view(
    *,
    session: DbSession,
    approval_or_agent_id: str,
    current_user: CurrentActiveUser,
) -> ApprovalRequest:
    req: ApprovalRequest | None = None
    target_uuid: UUID | None = None
    try:
        target_uuid = UUID(approval_or_agent_id)
    except Exception:
        target_uuid = None

    if not target_uuid:
        raise HTTPException(status_code=404, detail="Approval request not found")

    # Direct match by approval request id.
    req = (await session.exec(select(ApprovalRequest).where(ApprovalRequest.id == target_uuid))).first()
    if req:
        if _is_global_approver(current_user) or req.request_to == current_user.id or req.requested_by == current_user.id:
            return req
        raise HTTPException(status_code=403, detail="Not allowed to view this approval")

    # Fallback by agent id: latest request visible to user.
    stmt = select(ApprovalRequest).where(ApprovalRequest.agent_id == target_uuid).order_by(ApprovalRequest.requested_at.desc())
    if not _is_global_approver(current_user):
        stmt = stmt.where(
            (ApprovalRequest.request_to == current_user.id) | (ApprovalRequest.requested_by == current_user.id)
        )
    req = (await session.exec(stmt)).first()
    if not req:
        raise HTTPException(status_code=404, detail="Approval request not found")
    return req


async def _collect_attachment_metadata(
    *,
    files: list[UploadFile] | None,
    now: datetime,
) -> list[dict]:
    uploaded_files: list[dict] = []
    for file in files or []:
        contents = await file.read()
        uploaded_files.append(
            {
                "filename": file.filename,
                "size": len(contents),
                "uploadedAt": now.isoformat(),
            }
        )
    return uploaded_files


@router.get("", response_model=list[ApprovalAgent])
async def get_approvals(
    *,
    session: DbSession,
    current_user: CurrentActiveUser,
) -> list[ApprovalAgent]:
    """Fetch approvals for the current approver."""
    try:
        stmt = select(ApprovalRequest).order_by(ApprovalRequest.requested_at.desc())
        if not _is_global_approver(current_user):
            stmt = stmt.where(ApprovalRequest.request_to == current_user.id)
        rows = (await session.exec(stmt)).all()

        payload: list[ApprovalAgent] = []
        for req in rows:
            deployment = await session.get(AgentDeploymentProd, req.deployment_id)
            if not deployment:
                continue

            requester = await session.get(User, req.requested_by)
            agent = await session.get(Agent, req.agent_id)
            project_name = ""
            if agent and agent.project_id:
                folder = await session.get(Folder, agent.project_id)
                if folder:
                    project_name = folder.name

            title = deployment.agent_name or (agent.name if agent else "Untitled Agent")
            description = deployment.agent_description or req.publish_description or ""
            submitter_name = (
                requester.display_name
                if requester and requester.display_name
                else (requester.username if requester else "Unknown")
            )

            payload.append(
                ApprovalAgent(
                    id=str(req.id),
                    title=title,
                    status=_to_status_label(req.decision),
                    description=description,
                    submittedBy=SubmittedBy(name=submitter_name, avatar=None),
                    project=project_name,
                    submitted=(
                        req.updated_at.replace(tzinfo=timezone.utc).isoformat()
                        if req.updated_at.tzinfo is None
                        else req.updated_at.isoformat()
                    ),
                    version=f"v{deployment.version_number}",
                    recentChanges="",  # intentionally blank for now
                )
            )
        return payload
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching approvals: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch approvals",
        ) from e


@router.post("/{agent_id}/approve", response_model=ApprovalResponse)
async def approve_agent(
    agent_id: str,
    *,
    session: DbSession,
    current_user: CurrentActiveUser,
    comments: str = Form(default=""),
    attachments: list[UploadFile] | None = File(default=None),
) -> ApprovalResponse:
    """Approve a pending deployment request."""
    now = datetime.now(timezone.utc)
    req = await _get_approval_for_action(
        session=session,
        approval_or_agent_id=agent_id,
        current_user=current_user,
    )
    if req.decision is not None:
        raise HTTPException(status_code=400, detail="Approval request already finalized")

    deployment = await session.get(AgentDeploymentProd, req.deployment_id)
    if not deployment:
        raise HTTPException(status_code=404, detail="Linked deployment not found")

    uploaded_files = await _collect_attachment_metadata(files=attachments, now=now)
    if not comments.strip() and not uploaded_files:
        raise HTTPException(
            status_code=400,
            detail="Either comments or attachments are required for approval",
        )

    req.decision = ApprovalDecisionEnum.APPROVED
    req.justification = comments.strip() if comments else None
    existing = req.file_path if isinstance(req.file_path, dict) else {}
    existing_files = existing.get("files", [])
    if uploaded_files:
        existing["files"] = [*existing_files, *uploaded_files]
        req.file_path = existing
    req.reviewed_at = now
    req.updated_at = now
    session.add(req)

    deployment.status = DeploymentPRODStatusEnum.PUBLISHED
    deployment.lifecycle_step = ProdDeploymentLifecycleEnum.PUBLISHED
    deployment.is_active = True
    deployment.approval_id = req.id
    deployment.updated_at = now
    session.add(deployment)

    # Shadow deployment: keep previous versions active so
    # multiple versions can run side-by-side.

    await session.commit()

    try:
        await sync_agent_registry(
            session,
            agent_id=deployment.agent_id,
            org_id=deployment.org_id,
            acted_by=current_user.id,
            deployment_env=RegistryDeploymentEnvEnum.PROD,
        )
        await session.commit()
    except Exception as reg_err:
        logger.warning(f"Registry sync failed after approval {req.id}: {reg_err}")

    # Sync FileTrigger nodes → auto-create trigger_config entries
    if deployment.agent_snapshot:
        try:
            from agentcore.services.deps import get_trigger_service
            trigger_svc = get_trigger_service()
            await trigger_svc.sync_folder_monitors_for_agent(
                session=session,
                agent_id=deployment.agent_id,
                environment="prod",
                version=f"v{deployment.version_number}",
                deployment_id=deployment.id,
                flow_data=deployment.agent_snapshot,
                created_by=req.requested_by,
            )
        except Exception as fm_err:
            logger.warning(f"FileTrigger sync failed after approval {req.id}: {fm_err}")

    approver_name = getattr(current_user, "username", None)
    return ApprovalResponse(
        success=True,
        message="Agent approved successfully",
        agentId=str(req.agent_id),
        newStatus="approved",
        timestamp=now.isoformat(),
        approvedBy=approver_name,
    )


@router.post("/{agent_id}/reject", response_model=ApprovalResponse)
async def reject_agent(
    agent_id: str,
    *,
    session: DbSession,
    current_user: CurrentActiveUser,
    comments: str = Form(default=""),
    reason: str | None = Form(default=None),
    attachments: list[UploadFile] | None = File(default=None),
) -> ApprovalResponse:
    """Reject a pending deployment request."""
    now = datetime.now(timezone.utc)
    req = await _get_approval_for_action(
        session=session,
        approval_or_agent_id=agent_id,
        current_user=current_user,
    )
    if req.decision is not None:
        raise HTTPException(status_code=400, detail="Approval request already finalized")

    deployment = await session.get(AgentDeploymentProd, req.deployment_id)
    if not deployment:
        raise HTTPException(status_code=404, detail="Linked deployment not found")

    uploaded_files = await _collect_attachment_metadata(files=attachments, now=now)
    if not comments.strip() and not uploaded_files:
        raise HTTPException(
            status_code=400,
            detail="Either comments or attachments are required for rejection",
        )

    rejection_reason = reason or "Not approved"
    justification = comments.strip()
    req.decision = ApprovalDecisionEnum.REJECTED
    req.justification = f"{rejection_reason}: {justification}" if justification else rejection_reason
    existing = req.file_path if isinstance(req.file_path, dict) else {}
    existing_files = existing.get("files", [])
    if uploaded_files:
        existing["files"] = [*existing_files, *uploaded_files]
        req.file_path = existing
    req.reviewed_at = now
    req.updated_at = now
    session.add(req)

    deployment.status = DeploymentPRODStatusEnum.UNPUBLISHED
    deployment.is_active = False
    deployment.updated_at = now
    session.add(deployment)

    await session.commit()

    approver_name = getattr(current_user, "username", None)
    return ApprovalResponse(
        success=True,
        message="Agent rejected",
        agentId=str(req.agent_id),
        newStatus="rejected",
        timestamp=now.isoformat(),
        approvedBy=approver_name,
    )


@router.post("/{agent_id}/attachments")
async def upload_attachments(
    agent_id: str,
    *,
    session: DbSession,
    current_user: CurrentActiveUser,
    attachments: list[UploadFile] = File(...),
):
    """Attach metadata of uploaded files to approval request."""
    req = await _get_approval_for_action(
        session=session,
        approval_or_agent_id=agent_id,
        current_user=current_user,
    )
    uploaded_files: list[dict] = []
    now = datetime.now(timezone.utc)
    for file in attachments:
        contents = await file.read()
        uploaded_files.append(
            {
                "filename": file.filename,
                "size": len(contents),
                "uploadedAt": now.isoformat(),
            }
        )

    existing = req.file_path if isinstance(req.file_path, dict) else {}
    existing_files = existing.get("files", [])
    existing["files"] = [*existing_files, *uploaded_files]
    req.file_path = existing
    req.updated_at = now
    session.add(req)
    await session.commit()

    return {
        "success": True,
        "message": "Attachments uploaded successfully",
        "agentId": str(req.agent_id),
        "uploadedFiles": uploaded_files,
    }


@router.get("/{agent_id}", response_model=ApprovalAgent)
async def get_agent_details(
    agent_id: str,
    *,
    session: DbSession,
    current_user: CurrentActiveUser,
) -> ApprovalAgent:
    req = await _get_approval_for_view(
        session=session,
        approval_or_agent_id=agent_id,
        current_user=current_user,
    )
    deployment = await session.get(AgentDeploymentProd, req.deployment_id)
    if not deployment:
        raise HTTPException(status_code=404, detail="Linked deployment not found")
    requester = await session.get(User, req.requested_by)
    agent = await session.get(Agent, req.agent_id)
    project_name = ""
    if agent and agent.project_id:
        folder = await session.get(Folder, agent.project_id)
        if folder:
            project_name = folder.name

    return ApprovalAgent(
        id=str(req.id),
        title=deployment.agent_name or (agent.name if agent else "Untitled Agent"),
        status=_to_status_label(req.decision),
        description=deployment.agent_description or req.publish_description or "",
        submittedBy=SubmittedBy(
            name=(requester.display_name if requester and requester.display_name else (requester.username if requester else "Unknown")),
            avatar=None,
        ),
        project=project_name,
        submitted=(
            req.updated_at.replace(tzinfo=timezone.utc).isoformat()
            if req.updated_at.tzinfo is None
            else req.updated_at.isoformat()
        ),
        version=f"v{deployment.version_number}",
        recentChanges="",  # intentionally blank for now
        adminComments=req.justification,
        adminAttachments=(req.file_path.get("files", []) if isinstance(req.file_path, dict) else []),
    )


@router.get("/{agent_id}/preview", response_model=ApprovalPreviewResponse)
async def get_agent_preview(
    agent_id: str,
    *,
    session: DbSession,
    current_user: CurrentActiveUser,
) -> ApprovalPreviewResponse:
    req = await _get_approval_for_view(
        session=session,
        approval_or_agent_id=agent_id,
        current_user=current_user,
    )
    deployment = await session.get(AgentDeploymentProd, req.deployment_id)
    if not deployment:
        raise HTTPException(status_code=404, detail="Linked deployment not found")

    if not deployment.agent_snapshot:
        raise HTTPException(
            status_code=404,
            detail="No deployment snapshot found for preview",
        )

    return ApprovalPreviewResponse(
        id=str(req.id),
        title=deployment.agent_name or "Review Details",
        version=f"v{deployment.version_number}",
        snapshot=deployment.agent_snapshot,
    )


@router.post("/{agent_id}/reset-status")
async def reset_agent_status(
    agent_id: str,
    *,
    session: DbSession,
    current_user: CurrentActiveUser,
):
    """Reset status back to pending (kept for testing/demo utility)."""
    req = await _get_approval_for_action(
        session=session,
        approval_or_agent_id=agent_id,
        current_user=current_user,
    )
    deployment = await session.get(AgentDeploymentProd, req.deployment_id)
    if not deployment:
        raise HTTPException(status_code=404, detail="Linked deployment not found")

    now = datetime.now(timezone.utc)
    req.decision = None
    req.reviewed_at = None
    req.updated_at = now
    session.add(req)

    deployment.status = DeploymentPRODStatusEnum.PENDING_APPROVAL
    deployment.is_active = False
    deployment.updated_at = now
    session.add(deployment)

    await session.commit()
    return {
        "success": True,
        "message": "Agent status reset to pending",
        "agentId": str(req.agent_id),
        "newStatus": "pending",
    }
