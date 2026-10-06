from fastapi import APIRouter

from app.auth.controllers.refresh import refresh_session

router = APIRouter()

router.add_api_route(
    path="/api/v1/auth/refresh",
    methods=["POST"],
    endpoint=refresh_session
)
