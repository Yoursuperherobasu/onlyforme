from __future__ import annotations

from datetime import datetime, timezone
from http import HTTPStatus
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import and_, func, or_, select, true
from sqlmodel import select as sm_select

from agentcore.api.utils import CurrentActiveUser, DbSession
from agentcore.services.auth.permissions import normalize_role
from agentcore.services.database.models.department.model import Department
from agentcore.services.database.models.file.model import File as UserFile
from agentcore.services.database.models.knowledge_base.model import KBVisibilityEnum, KnowledgeBase
from agentcore.services.database.models.organization.model import Organization
from agentcore.services.database.models.user.model import User
from agentcore.services.database.models.user_department_membership.model import UserDepartmentMembership
from agentcore.services.database.models.user_organization_membership.model import UserOrganizationMembership
from agentcore.services.deps import get_storage_service
from agentcore.services.storage.service import StorageService

router = APIRouter(tags=["Knowledge Bases"], prefix="/knowledge_bases")


def _to_utc(dt: datetime | None) -> datetime | None:
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _is_admin_role(role: str | None) -> bool:
    return normalize_role(role or "") in {"super_admin", "department_admin", "root"}


async def _get_scope_memberships(session: DbSession, user_id: UUID) -> tuple[set[UUID], set[UUID]]:
    org_rows = (
        await session.exec(
            sm_select(UserOrganizationMembership.org_id).where(
                UserOrganizationMembership.user_id == user_id,
                UserOrganizationMembership.status.in_(["accepted", "active"]),
            )
        )
    ).all()
    dept_rows = (
        await session.exec(
            sm_select(UserDepartmentMembership.department_id).where(
                UserDepartmentMembership.user_id == user_id,
                UserDepartmentMembership.status == "active",
            )
        )
    ).all()
    org_ids = {r if isinstance(r, UUID) else r[0] for r in org_rows}
    dept_ids = {r if isinstance(r, UUID) else r[0] for r in dept_rows}
    return org_ids, dept_ids


async def _knowledge_base_visibility_filters(session: DbSession, current_user: CurrentActiveUser):
    """Build OR-able filter conditions based on user role and KB visibility."""
    role = normalize_role(getattr(current_user, "role", None) or "")
    org_ids, dept_ids = await _get_scope_memberships(session, current_user.id)

    # Root sees all knowledge bases across organizations.
    if role == "root":
        return [true()]

    # Super admins can see all KBs in their org scope, regardless of visibility.
    if getattr(current_user, "is_superuser", False) or role == "super_admin":
        if org_ids:
            return [KnowledgeBase.org_id.in_(list(org_ids))]
        return [KnowledgeBase.created_by == current_user.id]

    # Department admins:
    # own + all KBs from shared departments (including PRIVATE) + ORGANIZATION in shared org.
    if role == "department_admin":
        filters = [KnowledgeBase.created_by == current_user.id]
        if dept_ids:
            creator_shares_dept = (
                select(UserDepartmentMembership.department_id)
                .where(
                    UserDepartmentMembership.user_id == KnowledgeBase.created_by,
                    UserDepartmentMembership.status == "active",
                    UserDepartmentMembership.department_id.in_(list(dept_ids)),
                )
                .exists()
            )
            filters.append(creator_shares_dept)
        if org_ids:
            filters.append(
                and_(
                    KnowledgeBase.visibility == KBVisibilityEnum.ORGANIZATION,
                    KnowledgeBase.org_id.in_(list(org_ids)),
                )
            )
        return filters

    # Developers/business users:
    # own + DEPARTMENT in shared depts + ORGANIZATION in shared org.
    filters = [KnowledgeBase.created_by == current_user.id]
    if dept_ids:
        creator_shares_dept = (
            select(UserDepartmentMembership.department_id)
            .where(
                UserDepartmentMembership.user_id == KnowledgeBase.created_by,
                UserDepartmentMembership.status == "active",
                UserDepartmentMembership.department_id.in_(list(dept_ids)),
            )
            .exists()
        )
        filters.append(
            and_(
                KnowledgeBase.visibility == KBVisibilityEnum.DEPARTMENT,
                creator_shares_dept,
            )
        )
    if org_ids:
        filters.append(
            and_(
                KnowledgeBase.visibility == KBVisibilityEnum.ORGANIZATION,
                KnowledgeBase.org_id.in_(list(org_ids)),
            )
        )
    return filters


async def _can_manage_knowledge_base(
    session: DbSession,
    current_user: CurrentActiveUser,
    kb: KnowledgeBase,
) -> bool:
    role = normalize_role(getattr(current_user, "role", None) or "")
    if role == "root":
        return True
    if kb.created_by == current_user.id:
        return True
    if role == "super_admin":
        org_ids, _ = await _get_scope_memberships(session, current_user.id)
        return bool(kb.org_id and kb.org_id in org_ids)
    if role == "department_admin":
        _, dept_ids = await _get_scope_memberships(session, current_user.id)
        return bool(kb.dept_id and kb.dept_id in dept_ids)
    return False


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get("", status_code=HTTPStatus.OK)
@router.get("/", status_code=HTTPStatus.OK)
async def list_knowledge_bases(
    current_user: CurrentActiveUser,
    session: DbSession,
) -> list[dict]:
    filters = await _knowledge_base_visibility_filters(session, current_user)
    stmt = (
        select(
            KnowledgeBase.id,
            KnowledgeBase.name,
            KnowledgeBase.visibility,
            KnowledgeBase.created_by,
            KnowledgeBase.updated_at.label("kb_updated_at"),
            func.max(UserFile.updated_at).label("last_file_updated_at"),
            func.coalesce(func.sum(UserFile.size), 0).label("size"),
            func.count(UserFile.id).label("file_count"),
        )
        .select_from(KnowledgeBase)
        .join(UserFile, UserFile.knowledge_base_id == KnowledgeBase.id, isouter=True)
        .where(or_(*filters))
        .group_by(
            KnowledgeBase.id,
            KnowledgeBase.name,
            KnowledgeBase.visibility,
            KnowledgeBase.created_by,
            KnowledgeBase.updated_at,
        )
        .order_by(KnowledgeBase.name.asc())
    )
    rows = (await session.exec(stmt)).all()

    payload: list[dict] = []
    role = normalize_role(getattr(current_user, "role", None) or "")
    creator_ids = {row.created_by for row in rows if row.created_by}
    creator_email_map: dict[UUID, str] = {}
    dept_map: dict[UUID, str] = {}
    org_map: dict[UUID, str] = {}

    if creator_ids:
        creator_rows = (
            await session.exec(select(User.id, User.email, User.username).where(User.id.in_(list(creator_ids))))
        ).all()
        creator_email_map = {uid: (email or username) for uid, email, username in creator_rows}

        if role in {"department_admin", "super_admin", "root"}:
            dept_rows = (
                await session.exec(
                    select(UserDepartmentMembership.user_id, Department.name)
                    .join(Department, Department.id == UserDepartmentMembership.department_id)
                    .where(
                        UserDepartmentMembership.user_id.in_(list(creator_ids)),
                        UserDepartmentMembership.status == "active",
                    )
                )
            ).all()
            for user_id, dept_name in dept_rows:
                dept_map.setdefault(user_id, dept_name)

        if role == "root":
            org_rows = (
                await session.exec(
                    select(UserOrganizationMembership.user_id, Organization.name)
                    .join(Organization, Organization.id == UserOrganizationMembership.org_id)
                    .where(
                        UserOrganizationMembership.user_id.in_(list(creator_ids)),
                        UserOrganizationMembership.status.in_(["accepted", "active"]),
                    )
                )
            ).all()
            for user_id, org_name in org_rows:
                org_map.setdefault(user_id, org_name)

    for row in rows:
        timestamps = [_to_utc(ts) for ts in (row.kb_updated_at, row.last_file_updated_at)]
        timestamps = [ts for ts in timestamps if ts is not None]
        last_activity = max(timestamps) if timestamps else None
        is_own = row.created_by == current_user.id
        created_by_email = creator_email_map.get(row.created_by)
        department_name = dept_map.get(row.created_by)
        organization_name = org_map.get(row.created_by)

        if role in {"developer", "business_user"}:
            created_by_email = None
            department_name = None
            organization_name = None
        elif role == "department_admin":
            department_name = None
            organization_name = None
        elif role == "super_admin":
            organization_name = None
        elif role == "root" and is_own:
            department_name = None
            organization_name = None

        payload.append(
            {
                "id": str(row.id),
                "name": row.name,
                "visibility": row.visibility.value if row.visibility else "PRIVATE",
                "created_by": str(row.created_by),
                "size": int(row.size or 0),
                "words": 0,
                "characters": 0,
                "chunks": 0,
                "avg_chunk_size": 0,
                "file_count": int(row.file_count or 0),
                "updated_at": row.kb_updated_at.isoformat() if row.kb_updated_at else None,
                "last_activity": last_activity.isoformat() if last_activity else None,
                "is_own_kb": is_own,
                "created_by_email": created_by_email,
                "department_name": department_name,
                "organization_name": organization_name,
            }
        )

    return payload


class KnowledgeBaseUpdate(BaseModel):
    visibility: KBVisibilityEnum


@router.patch("/{kb_id}", status_code=HTTPStatus.OK)
async def update_knowledge_base(
    kb_id: UUID,
    payload: KnowledgeBaseUpdate,
    current_user: CurrentActiveUser,
    session: DbSession,
):
    """Update KB visibility. Only the creator or admins can change visibility."""
    kb = (
        await session.exec(
            sm_select(KnowledgeBase).where(KnowledgeBase.id == kb_id)
        )
    ).first()

    if not kb:
        raise HTTPException(status_code=404, detail="Knowledge base not found")

    if not await _can_manage_knowledge_base(session, current_user, kb):
        raise HTTPException(status_code=403, detail="Not authorized to update this knowledge base")

    kb.visibility = payload.visibility
    kb.updated_at = datetime.now(timezone.utc)

    session.add(kb)
    await session.commit()
    await session.refresh(kb)

    return {
        "id": str(kb.id),
        "name": kb.name,
        "visibility": kb.visibility.value,
        "updated_at": kb.updated_at.isoformat(),
    }


@router.delete("/{kb_id}", status_code=HTTPStatus.OK)
async def delete_knowledge_base(
    kb_id: UUID,
    current_user: CurrentActiveUser,
    session: DbSession,
    storage_service: StorageService = Depends(get_storage_service),
):
    kb = (
        await session.exec(
            sm_select(KnowledgeBase).where(
                KnowledgeBase.id == kb_id,
            )
        )
    ).first()

    if not kb:
        raise HTTPException(status_code=404, detail="Knowledge base not found")
    if not await _can_manage_knowledge_base(session, current_user, kb):
        raise HTTPException(status_code=403, detail="Not authorized to delete this knowledge base")

    files = (await session.exec(sm_select(UserFile).where(UserFile.knowledge_base_id == kb.id))).all()
    for file in files:
        try:
            storage_path = file.path
            user_prefix = f"{file.user_id}/"
            if storage_path.startswith(user_prefix):
                storage_path = storage_path[len(user_prefix):]
            await storage_service.delete_file(agent_id=str(file.user_id), file_name=storage_path)
        except Exception:
            pass
        await session.delete(file)

    await session.delete(kb)
    await session.commit()
    return {"message": "Knowledge base deleted successfully"}


@router.delete("", status_code=HTTPStatus.OK)
@router.delete("/", status_code=HTTPStatus.OK)
async def delete_knowledge_bases_batch(
    payload: dict,
    current_user: CurrentActiveUser,
    session: DbSession,
    storage_service: StorageService = Depends(get_storage_service),
):
    kb_ids = payload.get("kb_names", [])
    if not isinstance(kb_ids, list) or not kb_ids:
        raise HTTPException(status_code=400, detail="kb_names must be a non-empty list")

    deleted_count = 0
    for raw_id in kb_ids:
        try:
            kb_id = UUID(str(raw_id))
        except Exception:
            continue
        try:
            await delete_knowledge_base(kb_id, current_user, session, storage_service)
            deleted_count += 1
        except HTTPException:
            continue

    return {"deleted_count": deleted_count, "timestamp": datetime.now(timezone.utc).isoformat()}
