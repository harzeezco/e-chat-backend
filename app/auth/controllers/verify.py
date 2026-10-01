from fastapi import Request
from fastapi.responses import JSONResponse
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.auth.models.user import User, UserStatus
from app.auth.services.audit_logs import create_audit_log
from app.auth.services.verify import delete_verification_token, get_verification_user_id


def verify(token: str, session: Session):
    try:
        user_id = get_verification_user_id(token=token)
        if user_id is None:
            return JSONResponse(
                status_code=400,
                content={"success": False, "code": 400,
                         "message": "Invalid or expired verification token", "data": None},
            )

        user = session.scalar(select(User).where(User.id == user_id))
        if user is None:
            return JSONResponse(
                status_code=404,
                content={"success": False, "code": 404, "message": "User not found", "data": None},
            )

        if user.status == UserStatus.ACTIVE:
            return JSONResponse(
                status_code=400,
                content={"success": False, "code": 400, "message": "User is already verified", "data": None},
            )

        user.status = UserStatus.ACTIVE
        create_audit_log(
            session,
            action="USER_VERIFIED",
            user_id=user.id,
            resource_type="user",
            resource_id=user.id,
        )
        session.commit()
    except SQLAlchemyError:
        session.rollback()
        return JSONResponse(
            status_code=500,
            content={"success": False, "code": 500,
                     "message": "Unable to verify account", "data": None},
        )
    except Exception:
        session.rollback()
        return JSONResponse(
            status_code=500,
            content={"success": False, "code": 500,
                     "message": "An unexpected error occurred", "data": None},
        )

    try:
        delete_verification_token(token=token)
    except Exception:
        return JSONResponse(
            status_code=500,
            content={"success": False, "code": 500,
                     "message": "Account was verified, but verification cleanup failed", "data": None},
        )

    return JSONResponse(
        status_code=200,
        content={"success": True, "code": 200, "message": "Email verified successfully",
                 "data": {"id": user.id, "email": user.email, "status": user.status.value}},
    )


