from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlmodel import select
from sqlmodel.sql.expression import SelectOfScalar

from agentcore.api.utils import CurrentActiveUser, DbSession
from agentcore.api.schemas import UsersResponse, UserReadWithPermissions
from agentcore.initial_setup.setup import get_or_create_default_folder
from agentcore.services.auth.utils import (
    get_current_active_superuser,
    get_password_hash,
    verify_password,
)
from agentcore.services.database.models.user.crud import (
    get_user_by_id,
    get_user_by_username,
    update_user,
)
from agentcore.services.database.models.user.model import User, UserCreate, UserRead, UserUpdate
from agentcore.services.deps import get_settings_service
from agentcore.services.auth.permissions import get_permissions_for_role, permission_cache
from agentcore.services.cache.user_cache import UserCacheService

from agentcore.services.cache.user_cache import UserCacheService
from agentcore.services.auth.permissions import permission_cache
from agentcore.services.auth.decorators import PermissionChecker


router = APIRouter(tags=["Users"], prefix="/users")


@router.post("/", response_model=UserRead, status_code=201)
async def add_user(
    user: UserCreate,
    session: DbSession,
    current_user: User = Depends(PermissionChecker(["manage_users"])),
) -> User:
    """Add a new user to the database."""
    new_user = User.model_validate(user, from_attributes=True)
    try:
        creator_email = getattr(current_user, "username", None)
        creator_role = getattr(current_user, "role", None)
        new_user.creator_email = creator_email
        new_user.creator_role = creator_role

        # Department admin creation: require department name
        if new_user.role == "department_admin":
            if not user.department_name:
                raise HTTPException(status_code=400, detail="Department name is required for department admins.")
            new_user.department_name = user.department_name
            new_user.department_admin_email = None
        else:
            # Non-department admin creation:
            # If creator is department admin, bind their department automatically
            if creator_role == "department_admin":
                if not current_user.department_name:
                    raise HTTPException(
                        status_code=400,
                        detail="Department admin creator is missing department name.",
                    )
                new_user.department_admin_email = creator_email
                new_user.department_name = current_user.department_name
            # If creator is super admin, require department admin email selection
            elif creator_role == "super_admin":
                if not user.department_admin_email:
                    raise HTTPException(
                        status_code=400,
                        detail="Department admin email is required.",
                    )
                dept_admin = await get_user_by_username(session, user.department_admin_email)
                if not dept_admin or dept_admin.role != "department_admin":
                    raise HTTPException(
                        status_code=400,
                        detail="Selected department admin email is invalid.",
                    )
                if not dept_admin.department_name:
                    raise HTTPException(
                        status_code=400,
                        detail="Selected department admin has no department name.",
                    )
                new_user.department_admin_email = dept_admin.username
                new_user.department_name = dept_admin.department_name

        new_user.password = get_password_hash(user.password)
        new_user.is_superuser = new_user.role in {"super_admin", "department_admin"}
        new_user.is_active = get_settings_service().auth_settings.NEW_USER_IS_ACTIVE
        session.add(new_user)
        await session.commit()
        await session.refresh(new_user)
        folder = await get_or_create_default_folder(session, new_user.id)
        if not folder:
            raise HTTPException(status_code=500, detail="Error creating default project")
    except IntegrityError as e:
        await session.rollback()
        raise HTTPException(status_code=400, detail="This username is unavailable.") from e

    return new_user



@router.get("/whoami", response_model=UserReadWithPermissions)
async def read_current_user(
    current_user: CurrentActiveUser,
    db: DbSession
) -> dict:
    """Retrieve the current user's data."""
    settings_service = get_settings_service()
    user_cache = UserCacheService(settings_service)

    # Try cache for user
    try:
        cached_user = await user_cache.get_user(str(current_user.id))
        if cached_user:
            print(f"User from cache {current_user.id}")
        else:
            user = await get_user_by_id(db, current_user.id)
            cached_user = user.model_dump()
            
            await user_cache.set_user(user)
            print(f"Cached user {current_user.id}")
    except Exception as e:
        print(f"User cache error: {e}")
        cached_user = current_user.model_dump()

    # Try cache for permissions
    try:
        if permission_cache:
            user_permissions = await permission_cache.get_permissions_for_role(current_user.role)
        else:
            user_permissions = await get_permissions_for_role(current_user.role)
    except Exception as e:
        print(f"Permission cache error: {e}")
        user_permissions = await get_permissions_for_role(current_user.role)
    if not user_permissions:
        user_permissions = await get_permissions_for_role(current_user.role)

    return {
        **cached_user,
        "permissions": user_permissions
    }

@router.get("/", response_model=UsersResponse)
async def read_all_users(
    *,
    skip: int = 0,
    limit: int = 10,
    role: str | None = None,
    q: str | None = None,
    session: DbSession,
    _: User = Depends(PermissionChecker(["manage_users"])),
) -> UsersResponse:
    """Retrieve a list of users from the database with pagination."""
    query: SelectOfScalar = select(User)
    if role:
        query = query.where(User.role == role)
    if q:
        query = query.where(User.username.ilike(f"%{q}%"))
    query = query.offset(skip).limit(limit)
    users = (await session.exec(query)).fetchall()

    count_query = select(func.count()).select_from(User)
    if role:
        count_query = count_query.where(User.role == role)
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
        user_permissions = await get_permissions_for_role(user.role)
        if "manage_users" not in user_permissions:
            raise HTTPException(status_code=403, detail="Permission denied")
    if update_password:
        if not user.is_superuser:
            raise HTTPException(status_code=400, detail="You can't change your password here")
        user_update.password = get_password_hash(user_update.password)
    if user_update.role:
        user_update.is_superuser = user_update.role in {"super_admin", "department_admin"}

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
    new_password = get_password_hash(user_update.password)
    user.password = new_password
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


    stmt = select(User).where(User.id == user_id)
    user_db = (await session.exec(stmt)).first()
    if not user_db:
        raise HTTPException(status_code=404, detail="User not found")

    await session.delete(user_db)
    await session.commit()

    return {"detail": "User deleted"}
