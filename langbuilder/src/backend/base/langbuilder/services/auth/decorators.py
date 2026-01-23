from typing import List, Annotated
from fastapi import HTTPException, status, Depends
from langbuilder.services.auth.permissions import get_permissions_for_role
from langbuilder.services.auth.utils import get_current_active_user
from functools import wraps
from fastapi import Depends
from langbuilder.services.database.models.user.model import User

class PermissionChecker:
    def __init__(self, required_permissions: list[str], all_required: bool = True):
        self.required_permissions = required_permissions
        self.all_required = all_required

    def __call__(
        self,
        current_user: User = Depends(get_current_active_user),
    ) -> User:
        print("Checking permissions for user:", current_user.username)
        if not current_user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Not authenticated",
            )
        print("User role:", current_user.role)
        user_permissions = get_permissions_for_role(current_user.role)
        print("User permissions:", user_permissions)
        if self.all_required:
            has_access = all(
                perm in user_permissions for perm in self.required_permissions
            )
            error_msg = f"Missing required permissions"
        else:
            has_access = any(
                perm in user_permissions for perm in self.required_permissions
            )
            error_msg = (
                f"Requires at least one of: {self.required_permissions}"
            )
        print("Access granted:", has_access)
        if  has_access is False:
            print(status.HTTP_403_FORBIDDEN, error_msg, "*****")
            from fastapi.responses import JSONResponse
            raise HTTPException(
        status_code=403, 
        detail=f"Missing required permissions"
    )
        return current_user

    
    
def verify_permissions(perms: list[str], all_req: bool = True):
    def decorator(func):
        # We attach the dependency to the function metadata
        # so FastAPI still sees it, but your code stays clean.
        @wraps(func)
        async def wrapper(*args, **kwargs):
            return await func(*args, **kwargs)
        
        # Add the dependency to the route's dependency list programmatically
        if not hasattr(func, "dependencies"):
            func.dependencies = []
        func.dependencies.append(Depends(PermissionChecker(perms, all_req)))
        return wrapper
    return decorator