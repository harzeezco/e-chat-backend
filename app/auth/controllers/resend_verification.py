import hashlib

from fastapi import Depends, Request
from fastapi.responses import JSONResponse
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.auth.models.user import User, UserStatus
from app.auth.services.create_email_outbox import create_email_outbox
from app.auth.services.verify import store_verification_token, delete_verification_token
from app.auth.utils.generate_id import generate_id
from app.auth.utils.rate_limiter import RateLimiter
from app.auth.schemas.resend_verification import ResendVerificationRequest
from app.database import get_db

ip_limiter = RateLimiter(limit=5, window_seconds=60)
email_limiter = RateLimiter(limit=3, window_seconds=600)
GENERIC_MESSAGE = "If the account is pending verification, a verification email will be sent."

def resend_verification(
    data: ResendVerificationRequest,
    request: Request,
    session: Session = Depends(get_db),
) -> JSONResponse:
    client_ip = request.client.host if request.client else "unknown"
    normalized_email = str(data.email).strip().casefold()

    ip_allowed, _ = ip_limiter.check(f"rate_limit:verification_resend:ip:{client_ip}")
    email_key = hashlib.sha256(normalized_email.encode("utf-8")).hexdigest()
    email_allowed, _ = email_limiter.check(f"rate_limit:verification_resend:email:{email_key}")

    if ip_allowed and email_allowed:
        user = session.scalar(select(User).where(func.lower(User.email) == normalized_email))
        if user is not None and user.status == UserStatus.PENDING:
            token = generate_id(16)
            try:
                store_verification_token(token, user.id)
                create_email_outbox(
                    session=session,
                    to_email=user.email,
                    subject="Verify your account",
                    body=(
                        "Please verify your account by opening this link:\n\n"
                        f"http://localhost:8000/api/v1/verify?token={token}\n\n"
                        "This link expires in 10 minutes."
                    ),
                )
                session.commit()
            except Exception:
                session.rollback()
                try:
                    delete_verification_token(token)
                except Exception:
                    pass
                raise

    return JSONResponse(
        status_code=202,
        content={"success": True, "message": GENERIC_MESSAGE},
    )


