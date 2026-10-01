from sqlalchemy.orm import Session

from app.auth.utils.generate_id import generate_id
from app.auth.models.email_outbox import EmailOutbox


def create_email_outbox(
    session: Session,
    *,
    to_email: str,
    subject: str,
    body: str,
) -> EmailOutbox:

    email = EmailOutbox(
        id=f"email_{generate_id(8)}",
        to_email=to_email,
        subject=subject,
        body=body,
        status="pending",
        attempts=0,
    )

    session.add(email)

    return email
