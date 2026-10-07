from fastapi import APIRouter, Depends

from app.auth.dependencies import get_current_user
from app.auth.models.user import User

router = APIRouter()

@router.get("/api/v1/auth/session")
def get_session(current_user: User = Depends(get_current_user)):
    return {
        "success": True,
        "data": {
            "id": current_user.id,
            "email": current_user.email,
            "role": current_user.role.value,
            "status": current_user.status.value,
            "authenticated": True
        }
    }
