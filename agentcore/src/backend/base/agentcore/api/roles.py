from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import delete
from sqlmodel import select

from agentcore.api.utils import DbSession
from agentcore.api.schemas import (
    PermissionReadResponse,
    RoleCreateRequest,
    RoleReadResponse,
    RoleUpdateRequest,
)
from agentcore.services.auth.decorators import PermissionChecker
from agentcore.services.auth.permissions import invalidate_role_permissions_cache
from agentcore.services.database.models.permission import Permission
from agentcore.services.database.models.role import Role
from agentcore.services.database.models.role_permission import RolePermission
from agentcore.services.database.models.user.model import User


router = APIRouter(tags=["Roles"], prefix="/roles")


def _normalize_role_name(name: str) -> str:
    return name.strip().lower().replace(" ", "_")


@router.get(
    "/permissions",
    response_model=list[PermissionReadResponse],
    dependencies=[Depends(PermissionChecker(["view_access_control_page", "manage_roles"], all_required=False))],
)
async def list_permissions(session: DbSession) -> list[Permission]:
    permissions = (await session.exec(select(Permission).order_by(Permission.name))).all()
    return permissions


@router.get(
    "/",
    response_model=list[RoleReadResponse],
    dependencies=[Depends(PermissionChecker(["view_access_control_page", "manage_roles"], all_required=False))],
)
async def list_roles(session: DbSession) -> list[RoleReadResponse]:
    roles = (await session.exec(select(Role).order_by(Role.name))).all()
    role_permissions = (await session.exec(select(RolePermission))).all()
    permissions = (await session.exec(select(Permission))).all()

    perms_by_id = {p.id: p.key for p in permissions}
    perms_by_role: dict[UUID, list[str]] = {}
    for rp in role_permissions:
        perms_by_role.setdefault(rp.role_id, []).append(perms_by_id.get(rp.permission_id, ""))

    response: list[RoleReadResponse] = []
    for role in roles:
        response.append(
            RoleReadResponse(
                id=role.id,
                name=role.name,
                description=role.description,
                is_system=role.is_system,
                permissions=[p for p in perms_by_role.get(role.id, []) if p],
            )
        )
    return response


@router.post(
    "/",
    response_model=RoleReadResponse,
    dependencies=[Depends(PermissionChecker(["manage_roles"]))],
)
async def create_role(payload: RoleCreateRequest, session: DbSession) -> RoleReadResponse:
    name = _normalize_role_name(payload.name)
    existing = (await session.exec(select(Role).where(Role.name == name))).first()
    if existing:
        raise HTTPException(status_code=409, detail="Role name already exists")

    role = Role(name=name, description=payload.description, is_system=False)
    session.add(role)
    await session.commit()
    await session.refresh(role)

    if payload.permissions:
        await _replace_role_permissions(session, role.id, payload.permissions)
        await invalidate_role_permissions_cache(role.name)

    return RoleReadResponse(
        id=role.id,
        name=role.name,
        description=role.description,
        is_system=role.is_system,
        permissions=payload.permissions or [],
    )


@router.patch(
    "/{role_id}",
    response_model=RoleReadResponse,
    dependencies=[Depends(PermissionChecker(["manage_roles"]))],
)
async def update_role(role_id: UUID, payload: RoleUpdateRequest, session: DbSession) -> RoleReadResponse:
    role = await session.get(Role, role_id)
    if not role:
        raise HTTPException(status_code=404, detail="Role not found")
    if role.is_system and payload.name and _normalize_role_name(payload.name) != role.name:
        raise HTTPException(status_code=400, detail="System roles cannot be renamed")

    if payload.name:
        role.name = _normalize_role_name(payload.name)
    if payload.description is not None:
        role.description = payload.description

    session.add(role)
    await session.commit()
    await session.refresh(role)

    permissions: list[str] = []
    if payload.permissions is not None:
        await _replace_role_permissions(session, role.id, payload.permissions)
        await invalidate_role_permissions_cache(role.name)
        permissions = payload.permissions
    else:
        permissions = await _get_permissions_for_role(session, role.id)

    return RoleReadResponse(
        id=role.id,
        name=role.name,
        description=role.description,
        is_system=role.is_system,
        permissions=permissions,
    )


@router.put(
    "/{role_id}/permissions",
    response_model=RoleReadResponse,
    dependencies=[Depends(PermissionChecker(["manage_roles"]))],
)
async def replace_role_permissions(role_id: UUID, permissions: list[str], session: DbSession) -> RoleReadResponse:
    role = await session.get(Role, role_id)
    if not role:
        raise HTTPException(status_code=404, detail="Role not found")

    await _replace_role_permissions(session, role.id, permissions)
    await invalidate_role_permissions_cache(role.name)
    return RoleReadResponse(
        id=role.id,
        name=role.name,
        description=role.description,
        is_system=role.is_system,
        permissions=permissions,
    )


@router.delete(
    "/{role_id}",
    dependencies=[Depends(PermissionChecker(["manage_roles"]))],
)
async def delete_role(role_id: UUID, session: DbSession) -> dict:
    role = await session.get(Role, role_id)
    if not role:
        raise HTTPException(status_code=404, detail="Role not found")
    if role.is_system:
        raise HTTPException(status_code=400, detail="System roles cannot be deleted")

    users_with_role = (await session.exec(select(User).where(User.role == role.name))).first()
    if users_with_role:
        raise HTTPException(status_code=400, detail="Role is in use by existing users")

    # delete role permissions
    await session.exec(delete(RolePermission).where(RolePermission.role_id == role.id))
    await session.delete(role)
    await session.commit()
    return {"detail": "Role deleted"}


async def _replace_role_permissions(session: DbSession, role_id: UUID, permissions: list[str]) -> None:
    # Remove existing
    await session.exec(delete(RolePermission).where(RolePermission.role_id == role_id))

    if not permissions:
        await session.commit()
        return

    perm_rows = (await session.exec(select(Permission).where(Permission.key.in_(permissions)))).all()
    for perm in perm_rows:
        session.add(RolePermission(role_id=role_id, permission_id=perm.id))
    await session.commit()


async def _get_permissions_for_role(session: DbSession, role_id: UUID) -> list[str]:
    rows = (await session.exec(select(RolePermission).where(RolePermission.role_id == role_id))).all()
    if not rows:
        return []
    perm_ids = [row.permission_id for row in rows]
    perm_rows = (await session.exec(select(Permission).where(Permission.id.in_(perm_ids)))).all()
    return [p.key for p in perm_rows]
