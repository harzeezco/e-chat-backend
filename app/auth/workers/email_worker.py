from datetime import datetime, timedelta, timezone
import logging
import time

from app.database import SessionLocal
from app.auth.services.outlook import (
    MAX_EMAIL_ATTEMPTS,
    claim_pending_email,
    get_email_queue_stats,
    recover_stale_emails,
)
from app.auth.services.email_send import send_email

logger = logging.getLogger(__name__)
QUEUE_STATS_INTERVAL_SECONDS = 60
_last_stats_log = 0.0


def processing_pending_email() -> bool:
    """Return whether a pending email was claimed and processed."""
    with SessionLocal() as session:
        try:
            email = claim_pending_email(session=session)
            if email is None:
                return False

            # Keep database loading errors outside the delivery error handler.
            to, subject, body = email.to_email, email.subject, email.body
            try:
                send_email(to=to, subject=subject, body=body)
            except Exception as exc:
                email.last_error = str(exc)
                email.processing_at = None
                if email.attempts >= MAX_EMAIL_ATTEMPTS:
                    email.status = "failed"
                    email.next_attempt_at = None
                else:
                    delay_seconds = min(300, 2 ** email.attempts)
                    email.status = "pending"
                    email.next_attempt_at = datetime.now(timezone.utc) + timedelta(seconds=delay_seconds)
                logger.warning(
                    "Email delivery failed id=%s attempt=%s status=%s error=%s",
                    email.id, email.attempts, email.status, exc,
                )
            else:
                email.status = "sent"
                email.sent_at = datetime.now(timezone.utc)
                email.last_error = None
                email.processing_at = None
                email.next_attempt_at = None

            session.commit()
            return True
        except Exception:
            session.rollback()
            raise

def run_worker() -> None:
    """Drain available work, pausing only when idle or after an error."""
    global _last_stats_log
    while True:
        try:
            if time.monotonic() - _last_stats_log >= QUEUE_STATS_INTERVAL_SECONDS:
                with SessionLocal() as session:
                    recovered = recover_stale_emails(session)
                    if recovered:
                        logger.warning("Recovered %s stale email claims", recovered)
                    logger.info("Email queue stats: %s", get_email_queue_stats(session))
                _last_stats_log = time.monotonic()
            processed = processing_pending_email()
        except Exception:
            logger.exception("Email worker iteration failed")
            time.sleep(2)
            continue

        if not processed:
            time.sleep(2)


if __name__ == "__main__":
    run_worker()
