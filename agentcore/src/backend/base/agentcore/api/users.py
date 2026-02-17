from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import distinct, func
from sqlalchemy.exc import IntegrityError
from sqlmodel import select
from sqlmodel.sql.expression import SelectOfScalar

from agentcore.api.schemas import UsersResponse, UserReadWithPermissions
from agentcore.api.utils import CurrentActiveUser, DbSession
from agentcore.initial_setup.setup import get_or_create_default_folder
from agentcore.services.auth.decorators import PermissionChecker
from agentcore.services.auth.permissions import get_permissions_for_role, normalize_role, permission_cache
from agentcore.services.auth.utils import get_password_hash, verify_password
from agentcore.services.cache.user_cache import UserCacheService
from agentcore.services.database.models.department.model import Department
from agentcore.services.database.models.organization.model import Organization
from agentcore.services.database.models.role.model import Role
from agentcore.services.database.models.user.crud import get_user_by_id, get_user_by_username, update_user
from agentcore.services.database.models.user.model import User, UserCreate, UserRead, UserUpdate
from agentcore.services.database.models.user_department_membership.model import UserDepartmentMembership
from agentcore.services.database.models.user_organization_membership.model import UserOrganizationMembership
from agentcore.services.deps import get_settings_service

router = APIRouter(tags=["Users"], prefix="/users")

ACTIVE_ORG_STATUSES = {"accepted", "active"}
ACTIVE_DEPT_STATUS = "active"


async def _get_role_entity(session: DbSession, role_name: str) -> Role:
    normalized = normalize_role(role_name)
    role = (await session.exec(select(Role).where(Role.name == normalized))).first()
    if not role:
        raise HTTPException(status_code=400, detail=f"Role '{normalized}' is not configured.")
    return role


async def _get_admin_org_ids(session: DbSession, current_user: User) -> set[UUID]:
    if normalize_role(current_user.role) == "root":
        return set((await session.exec(select(Organization.id))).all())
    rows = (
        await session.exec(
            select(UserOrganizationMembership.org_id).where(
                UserOrganizationMembership.user_id == current_user.id,
                UserOrganizationMembership.status.in_(list(ACTIVE_ORG_STATUSES)),
            )
        )
    ).all()
    return set(rows)


async def _get_admin_department_ids(session: DbSession, current_user: User) -> set[UUID]:
    rows = (
        await session.exec(
            select(UserDepartmentMembership.department_id).where(
                UserDepartmentMembership.user_id == current_user.id,
                UserDepartmentMembership.status == ACTIVE_DEPT_STATUS,
            )
        )
    ).all()
    return set(rows)


async def _resolve_creator_org(
    session: DbSession,
    current_user: User,
    organization_name: str | None,
) -> UUID:
    org_ids = await _get_admin_org_ids(session, current_user)
    if not org_ids:
        raise HTTPException(status_code=400, detail="Creator has no organization membership.")

    if len(org_ids) == 1 and not organization_name:
        return next(iter(org_ids))

    if not organization_name:
        raise HTTPException(status_code=400, detail="Organization name is required.")

    org = (
        await session.exec(
            select(Organization).where(
                Organization.id.in_(list(org_ids)),
                Organization.name == organization_name,
            )
        )
    ).first()
    if not org:
        raise HTTPException(status_code=400, detail="Invalid organization name.")
    return org.id


async def _ensure_org_membership(
    session: DbSession,
    *,
    user_id: UUID,
    org_id: UUID,
    role_id: UUID,
    actor_user_id: UUID,
) -> None:
    existing = (
        await session.exec(
            select(UserOrganizationMembership).where(
                UserOrganizationMembership.user_id == user_id,
                UserOrganizationMembership.org_id == org_id,
            )
        )
    ).first()
    if existing:
        existing.role_id = role_id
        existing.status = "active"
        existing.updated_at = datetime.now(timezone.utc)
        existing.accepted_at = existing.accepted_at or datetime.now(timezone.utc)
        session.add(existing)
        return

    session.add(
        UserOrganizationMembership(
            user_id=user_id,
            org_id=org_id,
            status="active",
            role_id=role_id,
            invited_by=actor_user_id,
            accepted_at=datetime.now(timezone.utc),
        )
    )


async def _ensure_department_membership(
    session: DbSession,
    *,
    user_id: UUID,
    org_id: UUID,
    department_id: UUID,
    role_id: UUID,
    actor_user_id: UUID,
) -> None:
    existing = (
        await session.exec(
            select(UserDepartmentMembership).where(
                UserDepartmentMembership.user_id == user_id,
                UserDepartmentMembership.org_id == org_id,
                UserDepartmentMembership.department_id == department_id,
            )
        )
    ).first()
    if existing:
        existing.role_id = role_id
        existing.status = ACTIVE_DEPT_STATUS
        existing.updated_at = datetime.now(timezone.utc)
        existing.assigned_at = existing.assigned_at or datetime.now(timezone.utc)
        session.add(existing)
        return

    session.add(
        UserDepartmentMembership(
            user_id=user_id,
            org_id=org_id,
            department_id=department_id,
            status=ACTIVE_DEPT_STATUS,
            role_id=role_id,
            assigned_by=actor_user_id,
            assigned_at=datetime.now(timezone.utc),
        )
    )


async def _visible_user_ids_for_admin(session: DbSession, current_user: User) -> set[UUID]:
    role = normalize_role(current_user.role)
    if role == "root":
        return set((await session.exec(select(User.id))).all())

    if role == "super_admin":
        org_ids = await _get_admin_org_ids(session, current_user)
        if not org_ids:
            return {current_user.id}
        rows = (
            await session.exec(
                select(distinct(UserOrganizationMembership.user_id)).where(
                    UserOrganizationMembership.org_id.in_(list(org_ids)),
                    UserOrganizationMembership.status.in_(list(ACTIVE_ORG_STATUSES)),
                )
            )
        ).all()
        return set(rows) | {current_user.id}

    if role == "department_admin":
        dept_ids = await _get_admin_department_ids(session, current_user)
        if not dept_ids:
            return {current_user.id}
        rows = (
            await session.exec(
                select(distinct(UserDepartmentMembership.user_id)).where(
                    UserDepartmentMembership.department_id.in_(list(dept_ids)),
                    UserDepartmentMembership.status == ACTIVE_DEPT_STATUS,
                )
            )
        ).all()
        return set(rows) | {current_user.id}

    return {current_user.id}


@router.post("/", response_model=UserRead, status_code=201)
async def add_user(
    user: UserCreate,
    session: DbSession,
    current_user: User = Depends(PermissionChecker(["manage_users"])),
) -> User:
    """Add a new user to the database and stitch org/dept memberships by creator role."""
    new_user = User.model_validate(user, from_attributes=True)
    try:
        creator_email = getattr(current_user, "username", None)
        creator_role = normalize_role(getattr(current_user, "role", "developer"))
        target_role = normalize_role(new_user.role)
        new_user.creator_email = creator_email
        new_user.creator_role = creator_role
        new_user.role = target_role

        if creator_role == "root":
            if target_role != "super_admin":
                raise HTTPException(status_code=403, detail="Root admin can only create super admin users.")
            if not user.organization_name:
                raise HTTPException(status_code=400, detail="Organization name is required.")
        elif creator_role == "super_admin":
            if target_role not in {"department_admin", "developer", "business_user", "consumer"}:
                raise HTTPException(status_code=403, detail="Super admin can only create department or business users.")
        elif creator_role == "department_admin":
            if target_role not in {"developer", "business_user", "consumer"}:
                raise HTTPException(status_code=403, detail="Department admin can only create department users.")
        else:
            raise HTTPException(status_code=403, detail="Only admins can create users.")

        new_user.password = get_password_hash(user.password)
        new_user.is_superuser = new_user.role in {"super_admin", "department_admin", "root"}
        new_user.is_active = get_settings_service().auth_settings.NEW_USER_IS_ACTIVE
        session.add(new_user)
        await session.flush()

        role_entity = await _get_role_entity(session, target_role)

        if creator_role == "root":
            org = Organization(
                name=user.organization_name,
                description=user.organization_description,
                status="active",
                owner_user_id=new_user.id,
                created_by=current_user.id,
                updated_by=current_user.id,
            )
            session.add(org)
            await session.flush()
            await _ensure_org_membership(
                session,
                user_id=new_user.id,
                org_id=org.id,
                role_id=role_entity.id,
                actor_user_id=current_user.id,
            )
            root_role = await _get_role_entity(session, "root")
            await _ensure_org_membership(
                session,
                user_id=current_user.id,
                org_id=org.id,
                role_id=root_role.id,
                actor_user_id=current_user.id,
            )

        elif creator_role == "super_admin":
            org_id = await _resolve_creator_org(session, current_user, user.organization_name)
            await _ensure_org_membership(
                session,
                user_id=new_user.id,
                org_id=org_id,
                role_id=role_entity.id,
                actor_user_id=current_user.id,
            )

            if target_role == "department_admin":
                if not user.department_name:
                    raise HTTPException(status_code=400, detail="Department name is required for department admins.")
                department = Department(
                    org_id=org_id,
                    name=user.department_name,
                    admin_user_id=new_user.id,
                    status="active",
                    created_by=current_user.id,
                    updated_by=current_user.id,
                )
                session.add(department)
                await session.flush()
                new_user.department_name = department.name
                new_user.department_admin_email = None
                await _ensure_department_membership(
                    session,
                    user_id=new_user.id,
                    org_id=org_id,
                    department_id=department.id,
                    role_id=role_entity.id,
                    actor_user_id=current_user.id,
                )
            else:
                if not user.department_admin_email:
                    raise HTTPException(status_code=400, detail="Department admin email is required.")
                dept_admin = await get_user_by_username(session, user.department_admin_email)
                if not dept_admin or normalize_role(dept_admin.role) != "department_admin":
                    raise HTTPException(status_code=400, detail="Selected department admin email is invalid.")
                dept_admin_membership = (
                    await session.exec(
                        select(UserDepartmentMembership).where(
                            UserDepartmentMembership.user_id == dept_admin.id,
                            UserDepartmentMembership.org_id == org_id,
                            UserDepartmentMembership.status == ACTIVE_DEPT_STATUS,
                        )
                    )
                ).first()
                if not dept_admin_membership:
                    raise HTTPException(status_code=400, detail="Selected department admin has no department mapping.")
                department = await session.get(Department, dept_admin_membership.department_id)
                new_user.department_admin_email = dept_admin.username
                new_user.department_name = department.name if department else None
                await _ensure_department_membership(
                    session,
                    user_id=new_user.id,
                    org_id=org_id,
                    department_id=dept_admin_membership.department_id,
                    role_id=role_entity.id,
                    actor_user_id=current_user.id,
                )

        elif creator_role == "department_admin":
            creator_membership = (
                await session.exec(
                    select(UserDepartmentMembership).where(
                        UserDepartmentMembership.user_id == current_user.id,
                        UserDepartmentMembership.status == ACTIVE_DEPT_STATUS,
                    )
                )
            ).first()
            if not creator_membership:
                raise HTTPException(status_code=400, detail="Department admin is missing membership mapping.")
            department = await session.get(Department, creator_membership.department_id)
            new_user.department_admin_email = current_user.username
            new_user.department_name = department.name if department else None
            await _ensure_org_membership(
                session,
                user_id=new_user.id,
                org_id=creator_membership.org_id,
                role_id=role_entity.id,
                actor_user_id=current_user.id,
            )
            await _ensure_department_membership(
                session,
                user_id=new_user.id,
                org_id=creator_membership.org_id,
                department_id=creator_membership.department_id,
                role_id=role_entity.id,
                actor_user_id=current_user.id,
            )

        session.add(new_user)
        await session.commit()
        await session.refresh(new_user)

        folder = await get_or_create_default_folder(session, new_user.id)
        if not folder:
            raise HTTPException(status_code=500, detail="Error creating default project")
    except HTTPException:
        await session.rollback()
        raise
    except IntegrityError as e:
        await session.rollback()
        raise HTTPException(status_code=400, detail="This username is unavailable.") from e
    except Exception as e:
        await session.rollback()
        raise HTTPException(status_code=500, detail=str(e)) from e

    return new_user


@router.get("/whoami", response_model=UserReadWithPermissions)
async def read_current_user(
    current_user: CurrentActiveUser,
    db: DbSession,
) -> dict:
    """Retrieve the current user's data."""
    settings_service = get_settings_service()
    user_cache = UserCacheService(settings_service)

    try:
        cached_user = await user_cache.get_user(str(current_user.id))
        if not cached_user:
            user = await get_user_by_id(db, current_user.id)
            cached_user = user.model_dump()
            await user_cache.set_user(user)
    except Exception:
        cached_user = current_user.model_dump()

    try:
        if permission_cache:
            user_permissions = await permission_cache.get_permissions_for_role(current_user.role)
        else:
            user_permissions = await get_permissions_for_role(current_user.role)
    except Exception:
        user_permissions = await get_permissions_for_role(current_user.role)

    if not user_permissions:
        user_permissions = await get_permissions_for_role(current_user.role)

    return {
        **cached_user,
        "permissions": user_permissions,
    }


@router.get("/", response_model=UsersResponse)
async def read_all_users(
    *,
    skip: int = 0,
    limit: int = 10,
    role: str | None = None,
    q: str | None = None,
    session: DbSession,
    current_admin: User = Depends(PermissionChecker(["manage_users"])),
) -> UsersResponse:
    """Retrieve a list of users from the database with hierarchy-aware visibility."""
    visible_user_ids = await _visible_user_ids_for_admin(session, current_admin)
    if not visible_user_ids:
        return UsersResponse(total_count=0, users=[])

    query: SelectOfScalar = select(User).where(User.id.in_(list(visible_user_ids)))
    if role:
        query = query.where(User.role == normalize_role(role))
    if q:
        query = query.where(User.username.ilike(f"%{q}%"))
    query = query.offset(skip).limit(limit)
    users = (await session.exec(query)).fetchall()

    count_query = select(func.count()).select_from(User).where(User.id.in_(list(visible_user_ids)))
    if role:
        count_query = count_query.where(User.role == normalize_role(role))
    if q:
        count_query = count_query.where(User.username.ilike(f"%{q}%"))
    total_count = (await session.exec(count_query)).first()

    return UsersResponse(
        total_count=total_count,
        users=[UserRead(**user.model_dump()) for user in users],
    )


@router.patch("/{user_id}", response_model=UserRead)
async def patch_user(
    user_id: UUID,
    user_update: UserUpdate,
    user: CurrentActiveUser,
    session: DbSession,
) -> User:
    """Update an existing user's data."""
    update_password = bool(user_update.password)

    if user.id != user_id:
        visible_user_ids = await _visible_user_ids_for_admin(session, user)
        if user_id not in visible_user_ids:
            raise HTTPException(status_code=403, detail="Permission denied")
        user_permissions = await get_permissions_for_role(user.role)
        if "manage_users" not in user_permissions:
            raise HTTPException(status_code=403, detail="Permission denied")
    if update_password:
        if not user.is_superuser:
            raise HTTPException(status_code=400, detail="You can't change your password here")
        user_update.password = get_password_hash(user_update.password)
    if user_update.role:
        user_update.role = normalize_role(user_update.role)
        user_update.is_superuser = user_update.role in {"super_admin", "department_admin", "root"}

    if user_db := await get_user_by_id(session, user_id):
        if not update_password:
            user_update.password = user_db.password
        return await update_user(user_db, user_update, session)
    raise HTTPException(status_code=404, detail="User not found")


@router.patch("/{user_id}/reset-password", response_model=UserRead)
async def reset_password(
    user_id: UUID,
    user_update: UserUpdate,
    user: CurrentActiveUser,
    session: DbSession,
) -> User:
    """Reset a user's password."""
    if user_id != user.id:
        raise HTTPException(status_code=400, detail="You can't change another user's password")

    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if verify_password(user_update.password, user.password):
        raise HTTPException(status_code=400, detail="You can't use your current password")
    user.password = get_password_hash(user_update.password)
    await session.commit()
    await session.refresh(user)
    return user


@router.delete("/{user_id}")
async def delete_user(
    user_id: UUID,
    session: DbSession,
    current_user: User = Depends(PermissionChecker(["manage_users"])),
) -> dict:
    """Delete a user from the database."""
    if current_user.id == user_id:
        raise HTTPException(status_code=400, detail="You can't delete your own user account")

    visible_user_ids = await _visible_user_ids_for_admin(session, current_user)
    if user_id not in visible_user_ids:
        raise HTTPException(status_code=403, detail="Permission denied")

    user_db = (await session.exec(select(User).where(User.id == user_id))).first()
    if not user_db:
        raise HTTPException(status_code=404, detail="User not found")

    await session.delete(user_db)
    await session.commit()
    return {"detail": "User deleted"}
