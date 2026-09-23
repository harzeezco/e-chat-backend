from fastapi import APIRouter, Depends, Request
from .schemas import RegisterRequest
from sqlalchemy.orm import Session
from sqlalchemy import select
from app.database import get_db
from .user import User, UserRole, UserStatus
from .registration_attempt import RegistrationAttempt
from .password import hash_password
import secrets
from sqlalchemy.exc import IntegrityError


def generate_user_id() -> str:
    return f"usr_{secrets.token_hex(8)}"


def generate_registration_attempt_id() -> str:
    return f"reg_{secrets.token_hex(8)}"


def register(
    data: RegisterRequest,
    request: Request,
    session: Session = Depends(get_db)
):
    user_agent = request.headers.get("user-agent")
    client_ip = request.client.host if request.client else None

    attempt = RegistrationAttempt(
        id=generate_registration_attempt_id(),
        email=data.email,
        ip_address=client_ip,
        user_agent=user_agent,
        success=False
    )

    session.add(attempt)

    existing_user = session.scalar(
        select(User).where(User.email == data.email)
    )

    if existing_user:
        attempt.failure_reason = "email_exists"
        session.commit()

        return {
            "success": False,
            "code": 409,
            "message": "Invalid email or password",
            "data": []
        }

    hashed_password = hash_password(data.password)

    user = User(
        id=generate_user_id(),
        email=data.email,
        password_hash=hashed_password,
        role=UserRole.CUSTOMER,
        status=UserStatus.PENDING
    )

    try:
        session.add(user)
        session.commit()
        session.refresh(user)

    except IntegrityError:
        session.rollback()
        return {
            "success": False,
            "code": 409,
            "message": "Invalid email or password",
            "data": []
        }

    attempt.success = True
    session.commit()

    return {
        "success": True,
        "code": 201,
        "message": "Registration successful",
        "data": {
            "id": user.id,
            "email": user.email,
            "role": user.role.value,
        },
    }
