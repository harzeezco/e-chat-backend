import jwt

from datetime import datetime, timezone
from uuid import uuid4
from fastapi import Cookie, Depends, HTTPException
from fastapi.responses import JSONResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.models.user import User, UserStatus
from app.auth.models.refresh_token import RefreshToken
from app.auth.cookies import COOKIE_SECURE
from app.auth.services.jwt_access_token import (
    ACCESS_TOKEN_MINUTES,
    access_token,
    decode_refresh_token,
    refresh_token,
    REFRESH_TOKEN_DAYS
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
        now = datetime.now(timezone.utc)
        user_id = payload.get("sub")

        stored_token = session.scalar(
            select(RefreshToken).where(
                RefreshToken.jti == payload["jti"],
                RefreshToken.user_id == user_id,
                RefreshToken.revoked_at.is_(None),
                RefreshToken.expires_at > now
            ).with_for_update()
        )

        if stored_token is None:
            raise HTTPException(
                status_code=401,
                detail="Authentication required",
            )

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

    if stored_token.login_id is None:
        # A pre-migration refresh token has no reliable device history.
        if any(key in payload for key in ("login_id", "device_id", "new_device_at_login")):
            raise HTTPException(status_code=401, detail="Authentication required")
        login_context = {
            "login_id": str(uuid4()),
            "device_id": None,
            "new_device_at_login": None,
        }
    else:
        login_context = {
            "login_id": stored_token.login_id,
            "device_id": stored_token.device_id,
            "new_device_at_login": stored_token.new_device_at_login,
        }
        if any(payload.get(key) != value for key, value in login_context.items()):
            raise HTTPException(status_code=401, detail="Authentication required")

    new_access_token = access_token(user_id=user_id, **login_context)
    new_refresh_token = refresh_token(user_id=user_id, **login_context)
    new_refresh_claims = decode_refresh_token(token=new_refresh_token)

    stored_token.revoked_at = now
    stored_token.replaced_by_jti = new_refresh_claims["jti"]

    session.add(
        RefreshToken(
            jti=new_refresh_claims["jti"],
            user_id=user_id,
            **login_context,
            expires_at=datetime.fromtimestamp(
                new_refresh_claims["exp"],
                tz=timezone.utc,
            ),
        )
    )

    session.commit()

    response = JSONResponse(
        content={"success": True, "message": "Access token refreshed"}
    )

    response.set_cookie(
        key="access_token",
        value=new_access_token,
        httponly=True,
        secure=COOKIE_SECURE,
        samesite="lax",
        max_age=ACCESS_TOKEN_MINUTES * 60,
        path="/",
    )

    response.set_cookie(
        key="refresh_token",
        value=new_refresh_token,
        httponly=True,
        secure=COOKIE_SECURE,
        samesite="lax",
        max_age=REFRESH_TOKEN_DAYS * 24 * 60 * 60,
        path="/api/v1/auth",
    )

    return response
