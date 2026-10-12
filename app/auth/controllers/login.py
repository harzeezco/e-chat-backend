import hashlib
import secrets
from datetime import datetime, timezone
from uuid import uuid4

from fastapi import Depends, Request
from fastapi.responses import JSONResponse
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.auth.models.login_attempt import LoginAttempt
from app.auth.models.refresh_token import RefreshToken
from app.auth.models.user import User, UserStatus
from app.auth.cookies import COOKIE_SECURE
from app.auth.schemas.login import LoginRequest
from app.auth.services.audit_logs import create_audit_log
from app.auth.services.create_email_outbox import create_email_outbox
from app.auth.services.jwt_access_token import (
    ACCESS_TOKEN_MINUTES,
    REFRESH_TOKEN_DAYS,
    access_token,
    decode_refresh_token,
    refresh_token,
)
from app.auth.services.verify import (
    delete_verification_token,
    store_verification_token,
)
from app.auth.utils.generate_id import generate_id
from app.auth.utils.password import verify_password_hash
from app.auth.utils.rate_limiter import RateLimiter
from app.database import get_db
from app.security.models.user_device import UserDevice
from app.security.events import SecurityEventType, create_security_event


login_rate_limit = RateLimiter(limit=5, window_seconds=60)

DEVICE_COOKIE_MAX_AGE = 180 * 24 * 60 * 60


def _error(status_code: int, message: str) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={
            "success": False,
            "message": message,
            "data": None,
        },
    )


def _record_failed_login(session: Session, attempt: LoginAttempt, user_id: str | None = None) -> None:
    session.add(attempt)
    create_security_event(
        session,
        event_type=SecurityEventType.LOGIN_FAILED,
        user_id=user_id,
        ip_address=attempt.ip_address,
        user_agent=attempt.user_agent,
        event_data={"login_attempt_id": attempt.id, "reason": attempt.failure_reason},
    )
    session.commit()


def login(
    request: Request,
    data: LoginRequest,
    session: Session = Depends(get_db),
):
    client_ip = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent")

    allowed, _count = login_rate_limit.check(
        f"rate_limit:login:{client_ip}"
    )

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
        _record_failed_login(session, attempt)
        return _error(
            429,
            "Too many login attempts. Please try again later.",
        )

    if len(data.password) < 6:
        attempt.failure_reason = "Password is less than 6"
        _record_failed_login(session, attempt)
        return _error(400, "Password must be greater than 6")

    existing_user = session.scalar(
        select(User).where(User.email == data.email)
    )

    if existing_user is None:
        attempt.failure_reason = "User not found"
        _record_failed_login(session, attempt)
        return _error(401, "Email or password not available")

    if not verify_password_hash(
        data.password,
        existing_user.password_hash,
    ):
        attempt.failure_reason = "Password is not valid"
        _record_failed_login(session, attempt, existing_user.id)
        return _error(401, "Email or password not available")

    if existing_user.status == UserStatus.PENDING:
        attempt.failure_reason = "User is pending"
        _record_failed_login(session, attempt, existing_user.id)

        verification_token = generate_id(16)
        store_verification_token(
            token=verification_token,
            user_id=existing_user.id,
        )

        verification_url = (
            "http://localhost:8000/api/v1/verify"
            f"?token={verification_token}"
        )

        try:
            create_email_outbox(
                session=session,
                to_email=existing_user.email,
                subject="Verify your account",
                body=(
                    "Welcome!\n\n"
                    "Please verify your account by clicking the link below:\n\n"
                    f"{verification_url}\n\n"
                    "This link will expire in 10 minutes."
                ),
            )
            session.commit()
        except SQLAlchemyError:
            session.rollback()
            delete_verification_token(token=verification_token)
            raise

        return _error(403, "Check your mail to verify your account")

    if existing_user.status != UserStatus.ACTIVE:
        attempt.failure_reason = "User is not active"
        _record_failed_login(session, attempt, existing_user.id)
        return _error(403, "Email or password not available")

    # Authentication has succeeded. Device recognition starts here.
    device_cookie = request.cookies.get("device_key")
    device = None

    if device_cookie and len(device_cookie) <= 128:
        identifier_hash = hashlib.sha256(
            device_cookie.encode("utf-8")
        ).hexdigest()

        device = session.scalar(
            select(UserDevice).where(
                UserDevice.user_id == existing_user.id,
                UserDevice.identifier_hash == identifier_hash,
            )
        )

    new_device = device is None
    new_device_cookie = None

    if new_device:
        # Replace missing or unknown values with one generated by the server.
        new_device_cookie = secrets.token_urlsafe(32)

        device = UserDevice(
            id=f"dev_{generate_id(16)}",
            user_id=existing_user.id,
            identifier_hash=hashlib.sha256(
                new_device_cookie.encode("utf-8")
            ).hexdigest(),
        )
        session.add(device)
        # Insert the device before its ID is referenced by the refresh token.
        # Flush keeps both rows in the same transaction.
        session.flush()
    else:
        device.last_seen_at = datetime.now(timezone.utc)

    attempt.success = True
    session.add(attempt)

    # One ID follows this login through every refresh-token rotation.
    login_id = str(uuid4())
    login_context = {
        "login_id": login_id,
        "device_id": device.id,
        "new_device_at_login": new_device,
    }
    access_jwt = access_token(existing_user.id, **login_context)
    refresh_jwt = refresh_token(existing_user.id, **login_context)
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
            "device_id": device.id,
            "new_device": new_device,
            "login_id": login_id,
        },
    )

    create_security_event(
        session,
        event_type=SecurityEventType.LOGIN_SUCCESS,
        user_id=existing_user.id,
        login_id=login_id,
        device_id=device.id,
        ip_address=client_ip,
        user_agent=user_agent,
        event_data={"login_attempt_id": attempt.id, "new_device": new_device},
    )
    create_security_event(
        session,
        event_type=SecurityEventType.SESSION_CREATED,
        user_id=existing_user.id,
        login_id=login_id,
        device_id=device.id,
        ip_address=client_ip,
        user_agent=user_agent,
        event_data={"new_device": new_device},
    )

    session.add(
        RefreshToken(
            jti=refresh_claims["jti"],
            user_id=existing_user.id,
            **login_context,
            expires_at=datetime.fromtimestamp(
                refresh_claims["exp"],
                tz=timezone.utc,
            ),
        )
    )

    # Save the successful attempt, device, audit log, and refresh token
    # together. No cookies are returned if this commit fails.
    try:
        session.commit()
    except SQLAlchemyError:
        session.rollback()
        raise

    response = JSONResponse(
        status_code=200,
        content={
            "success": True,
            "message": "Login successful, welcome back",
            "data": None,
        },
    )

    response.set_cookie(
        key="access_token",
        value=access_jwt,
        httponly=True,
        secure=COOKIE_SECURE,
        samesite="lax",
        max_age=ACCESS_TOKEN_MINUTES * 60,
        path="/",
    )

    if new_device_cookie is not None:
        response.set_cookie(
            key="device_key",
            value=new_device_cookie,
            httponly=True,
            secure=COOKIE_SECURE,
            samesite="lax",
            max_age=DEVICE_COOKIE_MAX_AGE,
            path="/",
        )

    response.set_cookie(
        key="refresh_token",
        value=refresh_jwt,
        httponly=True,
        secure=COOKIE_SECURE,
        samesite="lax",
        max_age=REFRESH_TOKEN_DAYS * 24 * 60 * 60,
        path="/api/v1/auth",
    )

    return response
