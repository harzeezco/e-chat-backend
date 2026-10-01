"""Worker lifecycle checks; SQLite does not validate PostgreSQL row locks."""
import os
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

os.environ["DB_DSN"] = "sqlite://"

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.auth.models.email_outbox import EmailOutbox
from app.auth.services.email_send import send_email
from app.auth.workers import email_worker


class EmailWorkerTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite://")
        EmailOutbox.__table__.create(self.engine)
        self.sessions = sessionmaker(bind=self.engine)
        self.factory = patch.object(email_worker, "SessionLocal", self.sessions)
        self.factory.start()
        self.addCleanup(self.factory.stop)
        self.addCleanup(self.engine.dispose)

    def enqueue(self, key="one", status="pending", age=0):
        with self.sessions() as session:
            session.add(EmailOutbox(
                id=key, to_email="test@example.com", subject="Verify", body="Link",
                status=status, attempts=0,
                created_at=datetime.now(timezone.utc) - timedelta(seconds=age),
            ))
            session.commit()

    def test_empty_queue(self):
        with patch.object(email_worker, "send_email") as send:
            processed = email_worker.processing_pending_email()
        self.assertFalse(processed)
        send.assert_not_called()

    def test_oldest_pending_sent_and_claim_committed_before_delivery(self):
        self.enqueue("processing", "processing", age=30)
        self.enqueue("oldest", age=20)
        self.enqueue("newest", age=10)

        def deliver(**kwargs):
            with self.sessions() as session:
                row = session.get(EmailOutbox, "oldest")
                self.assertEqual((row.status, row.attempts), ("processing", 1))

        with patch.object(email_worker, "send_email", side_effect=deliver) as send:
            processed = email_worker.processing_pending_email()
        self.assertTrue(processed)
        send.assert_called_once()
        with self.sessions() as session:
            row = session.get(EmailOutbox, "oldest")
            self.assertEqual((row.status, row.attempts), ("sent", 1))
            self.assertIsNotNone(row.sent_at)
            self.assertIsNone(row.last_error)
            self.assertEqual(session.get(EmailOutbox, "newest").status, "pending")
            self.assertEqual(session.get(EmailOutbox, "processing").attempts, 0)

    def test_delivery_failure_is_persisted_without_automatic_retry(self):
        self.enqueue()
        with patch.object(email_worker, "send_email", side_effect=OSError("SMTP unavailable")) as send:
            processed = email_worker.processing_pending_email()
            next_processed = email_worker.processing_pending_email()
        self.assertTrue(processed)
        self.assertFalse(next_processed)
        send.assert_called_once()
        with self.sessions() as session:
            row = session.get(EmailOutbox, "one")
            self.assertEqual((row.status, row.attempts), ("failed", 1))
            self.assertEqual(row.last_error, "SMTP unavailable")
            self.assertIsNone(row.sent_at)

    def test_completion_commit_failure_leaves_claim_processing(self):
        self.enqueue()
        original_commit = self.sessions.class_.commit
        commits = 0

        def commit(session):
            nonlocal commits
            commits += 1
            if commits == 2:
                raise RuntimeError("database unavailable")
            return original_commit(session)

        with patch.object(self.sessions.class_, "commit", commit):
            with patch.object(email_worker, "send_email") as send:
                with self.assertRaisesRegex(RuntimeError, "database unavailable"):
                    email_worker.processing_pending_email()
        send.assert_called_once()
        with self.sessions() as session:
            row = session.get(EmailOutbox, "one")
            self.assertEqual((row.status, row.attempts), ("processing", 1))
            self.assertIsNone(row.sent_at)

    def test_sender_builds_independent_messages(self):
        with patch("app.auth.services.email_send.smtplib.SMTP") as smtp:
            send_email("first@example.com", "First", "One")
            send_email("second@example.com", "Second", "Two")
        calls = smtp.return_value.__enter__.return_value.send_message.call_args_list
        first, second = [call.args[0] for call in calls]
        self.assertIsNot(first, second)
        self.assertEqual(first["To"], "first@example.com")
        self.assertEqual(second["To"], "second@example.com")

    def test_worker_loop_continues_after_one_iteration_fails(self):
        with patch.object(
            email_worker, "processing_pending_email",
            side_effect=[RuntimeError("database unavailable"), False],
        ) as process:
            with patch.object(email_worker.time, "sleep", side_effect=[None, RuntimeError("stop")]):
                with patch.object(email_worker.logger, "exception") as log_error:
                    with self.assertRaisesRegex(RuntimeError, "stop"):
                        email_worker.run_worker()
        self.assertEqual(process.call_count, 2)
        log_error.assert_called_once_with("Email worker iteration failed")

    def test_worker_loop_drains_available_emails_before_sleeping(self):
        with patch.object(
            email_worker, "processing_pending_email", side_effect=[True, True, False]
        ) as process:
            with patch.object(
                email_worker.time, "sleep", side_effect=RuntimeError("stop")
            ) as sleep:
                with self.assertRaisesRegex(RuntimeError, "stop"):
                    email_worker.run_worker()

        self.assertEqual(process.call_count, 3)
        sleep.assert_called_once_with(2)


if __name__ == "__main__":
    unittest.main()
