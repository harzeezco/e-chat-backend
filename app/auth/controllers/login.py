
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from sqlalchemy import select
from fastapi import Depends, Request
from sqlalchemy.exc import IntegrityError
from datetime import datetime, timezone

from app.auth.schemas.login import LoginRequest
from app.database import get_db
from app.auth.models.user import User, UserStatus
from app.auth.utils.password import verify_password_hash
from app.auth.services.jwt_access_token import access_token, ACCESS_TOKEN_MINUTES, refresh_token, REFRESH_TOKEN_DAYS
from app.auth.services.audit_logs import create_audit_log
from app.auth.utils.rate_limiter import RateLimiter
from app.auth.utils.generate_id import generate_id
from app.auth.models.login_attempt import LoginAttempt
from app.auth.models.refresh_token import RefreshToken
from app.auth.services.verify import (
    store_verification_token,
    delete_verification_token,
)
from app.auth.services.create_email_outbox import create_email_outbox
from app.auth.services.jwt_access_token import decode_refresh_token


login_rate_limit = RateLimiter(
    limit=5,
    window_seconds=60
)


def login(request: Request, data: LoginRequest, session: Session = Depends(get_db)):
    client_ip = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent")

    rate_limiter_key = f"rate_limit:login:{client_ip}"

    allowed, count = login_rate_limit.check(rate_limiter_key)

    attempt = LoginAttempt(
        id=f"log_{generate_id(8)}",
        email=data.email,
        ip_address=client_ip,
        user_agent=user_agent,
        success=False,
        failure_reason=None,
    )

    if not allowed:
        attempt.failure_reason = "Too many login attempts"
        session.add(attempt)
        session.commit()

        return JSONResponse(
            status_code=429,
            content={
                "success": False,
                "message": "Too many login attempts. Please try again later.",
                "data": None,
            },
        )

    if len(data.password) < 6:
        attempt.failure_reason = "Password is less than 6"
        session.add(attempt)
        session.commit()
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

        attempt.failure_reason = "User already exist"
        session.add(attempt)

        session.commit()
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
        attempt.failure_reason = "Password is not valid"
        session.add(attempt)
        session.commit()
        return JSONResponse(
            status_code=401,
            content={
                "success": False,
                "message": "Email or password not available",
                "data": None
            }
        )

    if existing_user.status.value == UserStatus.PENDING.value:
        attempt.failure_reason = "User is pending"
        session.add(attempt)
        session.commit()
        verification_token = generate_id(16)

        try:

            store_verification_token(
                token=verification_token,
                user_id=existing_user.id,
            )

            verification_url = f"http://localhost:8000/api/v1/verify?token={verification_token}"

            create_email_outbox(
                session=session,
                to_email=existing_user.email,
                subject="Verify your account",
                body=(
                    "Welcome!\n\n"
                    "Please verify your account by clicking the link below:\n\n"
                    f"{verification_url}\n\n"
                    "This link will expire in 10 minutes."
                )
            )
            session.commit()
        except IntegrityError:
            delete_verification_token(token=verification_token)

        return JSONResponse(
            status_code=403,
            content={
                "success": False,
                "message": f"Check your mail to verify your account",
                "data": None
            }
        )
    elif existing_user.status.value != UserStatus.ACTIVE.value:
        attempt.failure_reason = "User is not active"
        session.add(attempt)
        session.commit()

        return JSONResponse(
            status_code=403,
            content={
                "success": False,
                "message": "Email or password not available",
                "data": None
            }
        )

    attempt.success = True
    session.add(attempt)
    session.commit()
    access_jwt = access_token(existing_user.id)
    refresh_jwt = refresh_token(existing_user.id)
    refresh_claims = decode_refresh_token(refresh_jwt)

    create_audit_log(
        session,
        action="USER_LOGIN",
        user_id=existing_user.id,
        resource_type="USER",
        resource_id=existing_user.id,
        ip_address=client_ip,
        user_agent=user_agent,
        event_data={
            "role": existing_user.role.value,
            "status": existing_user.status.value,
        },
    )

    session.add(
        RefreshToken(
            jti=refresh_claims["jti"],
            user_id=existing_user.id,
            expires_at=datetime.fromtimestamp(
                refresh_claims["exp"],
                tz=timezone.utc,
            ),
        )
    )

    session.commit()

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
        value=access_jwt,
        httponly=True,
        secure=False,
        samesite="lax",
        max_age=int(ACCESS_TOKEN_MINUTES) * 60,
        path="/"
    )

    response.set_cookie(
        key="refresh_token",
        value=refresh_jwt,
        httponly=True,
        secure=False,
        samesite="lax",
        max_age=int(REFRESH_TOKEN_DAYS * 24 * 60 * 60),
        path="/api/v1/auth"
    )

    return response
