from fastapi import Depends, HTTPException

from app.auth.dependencies import get_current_user
from app.auth.models.user import User, UserRole


def require_roles(*allowed_roles: UserRole):
    def role_dependency(
        current_user: User = Depends(get_current_user),
    ) -> User:
        if current_user.role not in allowed_roles:
            raise HTTPException(
                status_code=403,
                detail="You do not have permission to access this resource",
            )

        return current_user

    return role_dependency
