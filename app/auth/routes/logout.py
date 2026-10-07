from fastapi import APIRouter
from app.auth.controllers.logout import logout

router = APIRouter()

router.add_api_route(
    path="/api/v1/auth/logout",
    methods=["POST"],
    endpoint=logout,
)
