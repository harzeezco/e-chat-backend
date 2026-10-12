import jwt

from datetime import datetime, timezone
from fastapi import Cookie, Depends, Request
from fastapi.responses import JSONResponse
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.database import get_db
from app.auth.models.refresh_token import RefreshToken
from app.auth.models.revoked_access_token import RevokedAccessToken
from app.auth.cookies import COOKIE_SECURE
from app.auth.services.jwt_access_token import (
    decode_access_token,
    decode_refresh_token,
)
from app.auth.services.audit_logs import create_audit_log


def logout(
    request: Request,
    access_cookie: str | None = Cookie(
        default=None,
        alias="access_token",
    ),
    refresh_cookie: str | None = Cookie(
        default=None,
        alias="refresh_token",
    ),
    session: Session = Depends(get_db),
):
    client_ip = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent")

    access_payload = None
    if access_cookie is not None:
        try:
            access_payload = decode_access_token(access_cookie)
        except jwt.InvalidTokenError:
            pass

    refresh_payload = None
    if refresh_cookie is not None:
        try:
            refresh_payload = decode_refresh_token(refresh_cookie)
        except jwt.InvalidTokenError:
            pass

    now = datetime.now(timezone.utc)

    try:

        if refresh_payload is not None:
            stored_refresh_token = session.scalar(
                select(RefreshToken)
                .where(
                    RefreshToken.jti == refresh_payload["jti"],
                    RefreshToken.user_id == refresh_payload["sub"],
                    RefreshToken.revoked_at.is_(None),
                )
                .with_for_update()
            )

            if stored_refresh_token is not None:
                stored_refresh_token.revoked_at = now

        if access_payload is not None:
            session.execute(
                pg_insert(RevokedAccessToken)
                .values(
                    jti=access_payload["jti"],
                    expires_at=datetime.fromtimestamp(
                        access_payload["exp"],
                        tz=timezone.utc,
                    ),
                )
                .on_conflict_do_nothing(
                    index_elements=[RevokedAccessToken.jti]
                )
            )

        session.commit()

    except SQLAlchemyError:
        session.rollback()
        raise

    user_id = (
        access_payload["sub"]
        if access_payload is not None
        else refresh_payload["sub"]
        if refresh_payload is not None
        else None
    )

    create_audit_log(
        session,
        action="USER_LOGOUT",
        user_id=user_id,
        resource_type="USER" if user_id else None,
        resource_id=user_id,
        ip_address=client_ip,
        user_agent=user_agent,
        event_data={
            "access_token_valid": access_payload is not None,
            "refresh_token_valid": refresh_payload is not None,
            "login_id": (
                access_payload or refresh_payload or {}
            ).get("login_id"),
            "device_id": (
                access_payload or refresh_payload or {}
            ).get("device_id"),
        },
    )
    
    session.commit()

    response = JSONResponse(
        content={
            "success": True,
            "message": "Logged out successful",
            "data": None,
        },
    )

    response.delete_cookie(
        key="access_token",
        path="/",
        secure=COOKIE_SECURE,
        httponly=True,
        samesite="lax",
    )
    response.delete_cookie(
        key="refresh_token",
        path="/api/v1/auth",
        secure=COOKIE_SECURE,
        httponly=True,
        samesite="lax",
    )

    return response
