from fastapi import APIRouter
from app.auth.controllers.login import login

router = APIRouter()

router.add_api_route(path="/api/v1/auth/login",
                     methods=["POST"], endpoint=login)
