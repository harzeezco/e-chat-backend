from fastapi import APIRouter
from app.auth.controllers.register import register
from app.auth.schemas.register import RegisterResponse

router = APIRouter()

router.add_api_route(
    path="/api/v1/auth/register",
    methods=["POST"],
    endpoint=register,
    response_model=RegisterResponse
)
