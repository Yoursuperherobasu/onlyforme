from __future__ import annotations

from datetime import datetime, timezone
from http import HTTPStatus
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import and_, func, or_, select

from agentcore.api.utils import CurrentActiveUser, DbSession
from agentcore.services.database.models.file.model import File as UserFile
from agentcore.services.database.models.knowledge_base.model import KnowledgeBase
from agentcore.services.database.models.user_department_membership.model import UserDepartmentMembership
from agentcore.services.database.models.user_organization_membership.model import UserOrganizationMembership
from agentcore.services.deps import get_storage_service
from agentcore.services.storage.service import StorageService

router = APIRouter(tags=["Knowledge Bases"], prefix="/knowledge_bases")


def _is_admin_role(role: str | None) -> bool:
    return role in {"super_admin", "department_admin", "root"}


async def _get_scope_memberships(session: DbSession, user_id: UUID) -> tuple[set[UUID], set[UUID]]:
    org_rows = (
        await session.exec(
            select(UserOrganizationMembership.org_id).where(
                UserOrganizationMembership.user_id == user_id,
                UserOrganizationMembership.status.in_(["accepted", "active"]),
            )
        )
    ).all()
    dept_rows = (
        await session.exec(
            select(UserDepartmentMembership.department_id).where(
                UserDepartmentMembership.user_id == user_id,
                UserDepartmentMembership.status == "active",
            )
        )
    ).all()
    return set(org_rows), set(dept_rows)


async def _knowledge_base_visibility_filters(session: DbSession, current_user: CurrentActiveUser):
    role = getattr(current_user, "role", None)
    org_ids, dept_ids = await _get_scope_memberships(session, current_user.id)

    if getattr(current_user, "is_superuser", False) or role in {"root", "super_admin"}:
        if org_ids:
            return [KnowledgeBase.org_id.in_(list(org_ids))]
        return [KnowledgeBase.created_by == current_user.id]

    if role == "department_admin":
        filters = [KnowledgeBase.created_by == current_user.id]
        if dept_ids:
            filters.append(KnowledgeBase.dept_id.in_(list(dept_ids)))
        elif org_ids:
            filters.append(
                and_(
                    KnowledgeBase.org_id.in_(list(org_ids)),
                    KnowledgeBase.dept_id.is_(None),
                )
            )
        return filters

    filters = [KnowledgeBase.created_by == current_user.id]
    if dept_ids:
        filters.append(KnowledgeBase.dept_id.in_(list(dept_ids)))
    if org_ids:
        filters.append(
            and_(
                KnowledgeBase.org_id.in_(list(org_ids)),
                KnowledgeBase.dept_id.is_(None),
            )
        )
    return filters


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
            func.coalesce(func.sum(UserFile.size), 0).label("size"),
            func.count(UserFile.id).label("file_count"),
        )
        .select_from(KnowledgeBase)
        .join(UserFile, UserFile.knowledge_base_id == KnowledgeBase.id, isouter=True)
        .where(or_(*filters))
        .group_by(KnowledgeBase.id, KnowledgeBase.name)
        .order_by(KnowledgeBase.name.asc())
    )
    rows = (await session.exec(stmt)).all()

    return [
        {
            "id": str(row.id),
            "name": row.name,
            "size": int(row.size or 0),
            "words": 0,
            "characters": 0,
            "chunks": 0,
            "avg_chunk_size": 0,
            "file_count": int(row.file_count or 0),
        }
        for row in rows
    ]


@router.delete("/{kb_id}", status_code=HTTPStatus.OK)
async def delete_knowledge_base(
    kb_id: UUID,
    current_user: CurrentActiveUser,
    session: DbSession,
    storage_service: StorageService = Depends(get_storage_service),
):
    filters = await _knowledge_base_visibility_filters(session, current_user)
    kb = (
        await session.exec(
            select(KnowledgeBase).where(
                KnowledgeBase.id == kb_id,
                or_(*filters),
            )
        )
    ).first()

    if not kb:
        raise HTTPException(status_code=404, detail="Knowledge base not found")

    files = (await session.exec(select(UserFile).where(UserFile.knowledge_base_id == kb.id))).all()
    for file in files:
        try:
            storage_path = file.path
            user_prefix = f"{file.user_id}/"
            if storage_path.startswith(user_prefix):
                storage_path = storage_path[len(user_prefix) :]
            await storage_service.delete_file(agent_id=str(file.user_id), file_name=storage_path)
        except Exception:
            # Keep delete idempotent even if storage object is already missing.
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
