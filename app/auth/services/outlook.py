from datetime import datetime, timedelta, timezone

from sqlalchemy import and_, or_, select, update
from sqlalchemy.orm import Session

from app.auth.models.email_outbox import EmailOutbox

MAX_EMAIL_ATTEMPTS = 5
EMAIL_PROCESSING_LEASE = timedelta(minutes=5)

def claim_pending_email(
    session: Session,
) -> EmailOutbox | None:

    stmt = (
        select(EmailOutbox)
        .where(
            EmailOutbox.status == "pending",
            or_(EmailOutbox.next_attempt_at.is_(None), EmailOutbox.next_attempt_at <= datetime.now(timezone.utc)),
        )
        .order_by(EmailOutbox.created_at)
        .limit(1)
        .with_for_update(skip_locked=True)
    )

    email = session.scalar(stmt)

    if email is None:
        return None

    email.status = "processing"
    email.attempts += 1
    email.processing_at = datetime.now(timezone.utc)
    email.next_attempt_at = None

    session.commit()

    return email

def recover_stale_emails(session: Session) -> int:
    """Return expired processing leases to the queue, or fail exhausted rows."""
    cutoff = datetime.now(timezone.utc) - EMAIL_PROCESSING_LEASE
    stale = and_(EmailOutbox.status == "processing", EmailOutbox.processing_at < cutoff)
    session.execute(
        update(EmailOutbox)
        .where(stale, EmailOutbox.attempts >= MAX_EMAIL_ATTEMPTS)
        .values(status="failed", processing_at=None, last_error="Processing lease expired; retry limit reached")
    )
    result = session.execute(
        update(EmailOutbox)
        .where(stale, EmailOutbox.attempts < MAX_EMAIL_ATTEMPTS)
        .values(status="pending", processing_at=None, next_attempt_at=None,
                last_error="Previous worker stopped before completing delivery")
    )
    session.commit()
    return result.rowcount or 0

def get_email_queue_stats(session: Session) -> dict[str, int | float | None]:
    """Return status counts and age of the oldest eligible pending email."""
    from sqlalchemy import func

    counts = session.execute(
        select(EmailOutbox.status, func.count()).group_by(EmailOutbox.status)
    ).all()
    now = datetime.now(timezone.utc)
    oldest = session.scalar(
        select(func.min(EmailOutbox.created_at)).where(
            EmailOutbox.status == "pending",
            or_(EmailOutbox.next_attempt_at.is_(None), EmailOutbox.next_attempt_at <= now),
        )
    )
    stats: dict[str, int | float | None] = {"pending": 0, "processing": 0, "sent": 0, "failed": 0}
    stats.update({str(status): count for status, count in counts})
    stats["oldest_pending_age_seconds"] = max(0.0, (now - oldest).total_seconds()) if oldest else None
    return stats
