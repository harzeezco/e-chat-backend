
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from sqlalchemy import select
from fastapi import Depends, Request


from app.auth.schemas.login import LoginRequest
from app.database import get_db
from app.auth.models.user import User, UserStatus
from app.auth.utils.password import verify_password_hash
from app.auth.services.jwt_access_token import access_token, ACCESS_TOKEN_MINUTES
from app.auth.utils.rate_limiter import RateLimiter

login_rate_limit = RateLimiter(
    limit=5,
    window_seconds=60
)


def login(request: Request, data: LoginRequest, session: Session = Depends(get_db)):
    client_ip = request.client.host if request.client else None

    rate_limiter_key = f"rate_limit:login:{client_ip}"

    allowed, count = login_rate_limit.check(rate_limiter_key)

    if not allowed:
        return JSONResponse(
            status_code=429,
            content={
                "success": False,
                "message": "Too many registration attempts. Please try again later.",
                "data": None,
            },
        )


    if len(data.password) < 6:
        return JSONResponse(
            status_code=400,
            content={
                "success": False,
                "message": "Password must be greater than 6",
                "data": None
            }
        )

    existing_user = session.scalar(
        select(User).where(User.email == data.email))

    if not existing_user:
        return JSONResponse(
            status_code=401,
            content={
                "success": False,
                "message": "Email or password not available",
                "data": None
            }
        )

    is_valid_password = verify_password_hash(
        data.password, existing_user.password_hash)

    if not is_valid_password:
        return JSONResponse(
            status_code=401,
            content={
                "success": False,
                "message": "Email or password not available",
                "data": None
            }
        )

    if existing_user.status.value != UserStatus.ACTIVE.value:
        return JSONResponse(
            status_code=403,
            content={
                "success": False,
                "message": "Email or password not available",
                "data": None
            }
        )
    elif existing_user.status.value == UserStatus.PENDING.value:
        return JSONResponse(
            status_code=403,
            content={
                "success": False,
                "message": f"Check your mail to verify your account",
                "data": None
            }
        )

    token = access_token(existing_user.id)

    response = JSONResponse(
        status_code=200,
        content={
            "success": True,
            "message": "Login successful, welcome back",
            "data": None
        }
    )

    response.set_cookie(
        key="access_token",
        value=token,
        httponly=True,
        secure=False,
        samesite="lax",
        max_age=int(ACCESS_TOKEN_MINUTES) * 60,
        path="/"
    )

    return response
