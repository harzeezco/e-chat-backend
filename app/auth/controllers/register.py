from fastapi import Depends, Request
from fastapi.responses import JSONResponse
import time

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database import get_db

from app.auth.schemas.register import RegisterRequest

from app.auth.models.user import User, UserRole, UserStatus
from app.auth.models.registration_attempt import RegistrationAttempt

from app.auth.utils.password import hash_password
from app.auth.utils.rate_limiter import RateLimiter
from app.auth.utils.generate_id import generate_id

from app.auth.services.audit_logs import create_audit_log

from app.auth.services.verify import (
    store_verification_token,
    delete_verification_token,
)

from app.auth.services.create_email_outbox import create_email_outbox

registration_limiter = RateLimiter(
    limit=5,
    window_seconds=60,
)

def register(
    data: RegisterRequest,
    request: Request,
    session: Session = Depends(get_db),
) -> JSONResponse:
    user_agent = request.headers.get("user-agent")

    client_ip = request.client.host if request.client else None

    if client_ip is None:
        client_ip = "unknown"

    rate_limit_key = f"rate_limit:register:{client_ip}"

    allowed, count = registration_limiter.check(rate_limit_key)

    if not allowed:
        return JSONResponse(
            status_code=429,
            content={
                "success": False,
                "message": "Too many registration attempts. Please try again later.",
                "data": None,
            },
        )

    attempt = RegistrationAttempt(
        id=f"reg_{generate_id(8)}",
        email=data.email,
        ip_address=client_ip,
        user_agent=user_agent,
        success=False,
        failure_reason=None,
    )

    session.add(attempt)
    session.commit()

    existing_user = session.scalar(
        select(User).where(User.email == data.email)
    )

    if existing_user:

        attempt = session.get(
            RegistrationAttempt,
            attempt.id,
        )

        attempt.failure_reason = "email_exists"

        session.commit()

        return JSONResponse(
            status_code=409,
            content={
                "success": False,
                "message": "Invalid email or password",
                "data": None,
            },
        )

    hashed_password = hash_password(data.password)

    user = User(
        id=f"usr_{generate_id(8)}",
        email=data.email,
        password_hash=hashed_password,
        role=UserRole.CUSTOMER,
        status=UserStatus.PENDING,
    )

    try:
        session.add(user)

        session.flush()

        create_audit_log(
            session,
            action="USER_REGISTERED",
            user_id=user.id,
            resource_type="USER",
            resource_id=user.id,
            ip_address=client_ip,
            user_agent=user_agent,
            event_data={
                "role": user.role.value,
                "status": user.status.value,
            },
        )

        verification_token = generate_id(16)

        store_verification_token(
            verification_token,
            user.id,
        )

        verification_url = f"http://localhost:8000/api/v1/verify?token={verification_token}"

        create_email_outbox(
            session=session,
            to_email=user.email,
            subject="Verify your account",
            body=(
                "Welcome!\n\n"
                "Please verify your account by clicking the link below:\n\n"
                f"{verification_url}\n\n"
                "This link will expire in 10 minutes."
            )
        )

    except IntegrityError:
        session.rollback()

        try:
            delete_verification_token(
                token=verification_token
            )
        except Exception:
            pass

        # Reload the already committed registration attempt.
        attempt = session.get(
            RegistrationAttempt,
            attempt.id,
        )

        attempt.failure_reason = "user_creation_conflict"

        session.commit()

        return JSONResponse(
            status_code=409,
            content={
                "success": False,
                "message": "Invalid email or password",
                "data": None,
            },
        )

    except Exception:

        session.rollback()

        try:
            delete_verification_token(
                token=verification_token
            )
        except Exception:
            pass

        # Reload the committed registration attempt.
        attempt = session.get(
            RegistrationAttempt,
            attempt.id,
        )

        attempt.failure_reason = "email_send_failed"
        session.commit()

        return JSONResponse(
            status_code=503,
            content={
                "success": False,
                "message": "Unable to send verification email. Please try again later.",
                "data": None,
            },
        )

    attempt = session.get(
        RegistrationAttempt,
        attempt.id,
    )

    attempt.success = True
    attempt.failure_reason = None

    session.commit()

    return JSONResponse(
        status_code=201,
        content={
            "success": True,
            "message": (
                "Registration successful. "
                "Please check your email to verify your account."
            ),
            "data": {
                "id": user.id,
                "email": user.email,
                "role": user.role.value,
            },
        },
    )

