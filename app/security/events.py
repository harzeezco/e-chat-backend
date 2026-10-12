"""Persist security facts in the caller's transaction."""

from enum import StrEnum

from sqlalchemy.orm import Session

from app.auth.utils.generate_id import generate_id
from app.security.models.security_event import SecurityEvent


class SecurityEventType(StrEnum):
    LOGIN_FAILED = "LOGIN_FAILED"
    LOGIN_SUCCESS = "LOGIN_SUCCESS"
    SESSION_CREATED = "SESSION_CREATED"
    SESSION_REFRESHED = "SESSION_REFRESHED"
    SESSION_REVOKED = "SESSION_REVOKED"
    LOGOUT = "LOGOUT"


def create_security_event(
    session: Session,
    *,
    event_type: SecurityEventType,
    user_id: str | None = None,
    login_id: str | None = None,
    device_id: str | None = None,
    ip_address: str | None = None,
    user_agent: str | None = None,
    resource_type: str | None = None,
    resource_id: str | None = None,
    event_data: dict | None = None,
) -> SecurityEvent:
    """Stage an event; the caller commits it with the state it describes."""
    event = SecurityEvent(
        id=f"sev_{generate_id(16)}",
        event_type=event_type.value,
        user_id=user_id,
        login_id=login_id,
        device_id=device_id,
        ip_address=ip_address,
        user_agent=user_agent,
        resource_type=resource_type,
        resource_id=resource_id,
        event_data=event_data,
    )
    session.add(event)
    return event