import jwt
from dataclasses import dataclass

from fastapi import Cookie, Depends, HTTPException
from sqlalchemy.orm import Session

from app.auth.models.user import User, UserStatus
from app.auth.models.revoked_access_token import RevokedAccessToken
from app.auth.services.jwt_access_token import decode_access_token
from app.database import get_db


@dataclass(frozen=True)
class AuthenticatedLogin:
    user: User
    login_id: str | None
    device_id: str | None
    new_device_at_login: bool | None


def get_current_login(
    access_cookie: str | None = Cookie(default=None, alias="access_token"),
    session: Session = Depends(get_db),
) -> AuthenticatedLogin:
    if access_cookie is None:
        raise HTTPException(status_code=401, detail="Authentication required")

    try:
        payload = decode_access_token(access_cookie)
        
        
    except jwt.InvalidTokenError:
        raise HTTPException(
            status_code=401, detail="Invalid or expired access token")
        
        
    if session.get(RevokedAccessToken, payload["jti"]) is not None:
        raise HTTPException(
            status_code=401,
            detail="Authentication required",
        )
        
    user_id = payload.get("sub")
    user = session.get(User, user_id) if user_id else None

    if user is None or user.status != UserStatus.ACTIVE:
        raise HTTPException(status_code=401, detail="Authentication required")

    return AuthenticatedLogin(
        user=user,
        login_id=payload.get("login_id"),
        device_id=payload.get("device_id"),
        new_device_at_login=payload.get("new_device_at_login"),
    )


def get_current_user(
    current_login: AuthenticatedLogin = Depends(get_current_login),
) -> User:
    return current_login.user
