from sqlalchemy.orm import Session
from app.auth.utils.generate_id import generate_id
from app.auth.models.audit_log import AuditLog


def create_audit_log(
    session: Session,
    *,
    action: str,
    user_id: str | None = None,
    resource_type: str | None = None,
    resource_id: str | None = None,
    ip_address: str | None = None,
    user_agent: str | None = None,
    event_data: dict | None = None,
):
    audit_log = AuditLog(
        id=f"audit_{generate_id(8)}",
        user_id=user_id,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        ip_address=ip_address,
        user_agent=user_agent,
        event_data=event_data,
    )

    session.add(audit_log)

    return audit_log
