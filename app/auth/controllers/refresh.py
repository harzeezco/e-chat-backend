import jwt

from fastapi import Cookie, Depends, HTTPException
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.auth.models.user import User, UserStatus
from app.auth.services.jwt_access_token import (
    ACCESS_TOKEN_MINUTES,
    access_token,
    decode_refresh_token
)
from app.database import get_db


def refresh_session(refresh_cookie: str | None = Cookie(default=None, alias="refresh_token"), session: Session = Depends(get_db)):
    if refresh_cookie is None:
        raise HTTPException(
            status_code=401,
            detail="Refresh token required",

        )

    try:
        payload = decode_refresh_token(refresh_cookie)
    except jwt.InvalidTokenError:
        raise HTTPException(
            status_code=401,
            detail="Invalid or expired refresh token",
        )

    user_id = payload.get("sub")
    user = session.get(User, user_id) if user_id else None

    if user is None or user.status != UserStatus.ACTIVE:
        raise HTTPException(status_code=401, detail="Authentication required",
                            )

    new_access_token = access_token(user_id=user_id)

    response = JSONResponse(
        content={"success": True, "message": "Access token refreshed"}
    )

    response.set_cookie(
        key="access_token",
        value=new_access_token,
        httponly=True,
        secure=False,  # Local HTTP only; use True with HTTPS.
        samesite="lax",
        max_age=ACCESS_TOKEN_MINUTES * 60,
        path="/",
    )

    return response
