import jwt

from fastapi import Cookie, Depends, HTTPException
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.auth.models.user import User, UserStatus
from app.auth.services.jwt_access_token import decode_access_token
from app.database import get_db


def get_current_user(
    access_cookie: str | None = Cookie(default=None, alias="access_token"),
    session: Session = Depends(get_db),
):
    if access_cookie is None:
        raise HTTPException(status_code=401, detail="Authentication required")

    try:
        payload = decode_access_token(access_cookie)
    except jwt.InvalidTokenError:
        raise HTTPException(
            status_code=401, detail="Invalid or expired access token")

    user_id = payload.get("sub")
    user = session.get(User, user_id) if user_id else None

    if user is None or user.status != UserStatus.ACTIVE:
        raise HTTPException(status_code=401, detail="Authentication required")

    return user
