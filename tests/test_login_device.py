"""Login persists a new device before its refresh token references it."""

import os
import unittest
from http.cookies import SimpleCookie
from unittest.mock import patch

os.environ.setdefault("DB_DSN", "sqlite://")
os.environ.setdefault("JWT_SECRET_KEY", "test-only-login-device-secret-key-123")
os.environ.setdefault("JWT_ALGORITHM", "HS256")

from fastapi import Request
from sqlalchemy import create_engine, event, func, select
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.auth.controllers.login import login
from app.auth.controllers.logout import logout
from app.auth.controllers.refresh import refresh_session
from app.auth.models.audit_log import AuditLog
from app.auth.models.login_attempt import LoginAttempt
from app.auth.models.refresh_token import RefreshToken
from app.auth.models.revoked_access_token import RevokedAccessToken
from app.auth.models.user import User, UserRole, UserStatus
from app.auth.schemas.login import LoginRequest
from app.security.models.user_device import UserDevice
from app.security.models.security_event import SecurityEvent
from app.security.events import SecurityEventType


class LoginDeviceTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine(
            "sqlite://",
            poolclass=StaticPool,
            connect_args={"check_same_thread": False},
        )

        @event.listens_for(self.engine, "connect")
        def enable_foreign_keys(connection, _record):
            connection.execute("PRAGMA foreign_keys=ON")

        for table in (
            User.__table__,
            UserDevice.__table__,
            LoginAttempt.__table__,
            AuditLog.__table__,
            RefreshToken.__table__,
            RevokedAccessToken.__table__,
            SecurityEvent.__table__,
        ):
            table.create(self.engine)
        self.session = sessionmaker(bind=self.engine)()
        self.addCleanup(self.engine.dispose)
        self.addCleanup(self.session.close)
        self.user = User(
            id="usr_device_test",
            email="device@example.com",
            password_hash="unused",
            role=UserRole.CUSTOMER,
            status=UserStatus.ACTIVE,
        )
        self.session.add(self.user)
        self.session.commit()

    def request(self, device_key=None):
        headers = [(b"user-agent", b"test-browser")]
        if device_key:
            headers.append((b"cookie", f"device_key={device_key}".encode()))
        return Request({
            "type": "http",
            "method": "POST",
            "path": "/api/v1/auth/login",
            "headers": headers,
            "client": ("127.0.0.1", 12345),
        })

    @staticmethod
    def cookie(response, name):
        for header in response.headers.getlist("set-cookie"):
            parsed = SimpleCookie()
            parsed.load(header)
            if name in parsed:
                return parsed[name].value
        return None

    def test_new_device_and_known_device_login(self):
        credentials = LoginRequest(email=self.user.email, password="correct-password")
        with patch("app.auth.controllers.login.login_rate_limit.check", return_value=(True, 1)), patch(
            "app.auth.controllers.login.verify_password_hash", return_value=True
        ):
            first = login(self.request(), credentials, self.session)
            self.assertEqual(first.status_code, 200)
            device_key = self.cookie(first, "device_key")
            self.assertIsNotNone(device_key)
            device = self.session.scalar(select(UserDevice))
            self.assertEqual(self.session.scalar(select(RefreshToken)).device_id, device.id)
            self.assertEqual(self.session.scalar(select(func.count()).select_from(UserDevice)), 1)

            second = login(self.request(device_key), credentials, self.session)
            self.assertEqual(second.status_code, 200)
            self.assertIsNone(self.cookie(second, "device_key"))
            self.assertEqual(self.session.scalar(select(func.count()).select_from(UserDevice)), 1)
            self.assertEqual(self.session.scalar(select(func.count()).select_from(RefreshToken)), 2)
            login_events = self.session.scalars(
                select(SecurityEvent)
                .where(SecurityEvent.event_type == SecurityEventType.LOGIN_SUCCESS)
                .order_by(SecurityEvent.created_at, SecurityEvent.id)
            ).all()
            self.assertEqual(sorted(event.event_data["new_device"] for event in login_events), [False, True])


    def test_failed_login_records_event(self):
        credentials = LoginRequest(email=self.user.email, password="wrong-password")
        with patch("app.auth.controllers.login.login_rate_limit.check", return_value=(True, 1)), patch(
            "app.auth.controllers.login.verify_password_hash", return_value=False
        ):
            response = login(self.request(), credentials, self.session)
        self.assertEqual(response.status_code, 401)
        security_event = self.session.scalar(select(SecurityEvent))
        attempt = self.session.scalar(select(LoginAttempt))
        self.assertEqual(security_event.event_type, SecurityEventType.LOGIN_FAILED)
        self.assertEqual(security_event.user_id, self.user.id)
        self.assertEqual(security_event.event_data["login_attempt_id"], attempt.id)
        self.assertIsNone(security_event.login_id)

    def test_login_refresh_logout_event_timeline(self):
        credentials = LoginRequest(email=self.user.email, password="correct-password")
        with patch("app.auth.controllers.login.login_rate_limit.check", return_value=(True, 1)), patch(
            "app.auth.controllers.login.verify_password_hash", return_value=True
        ):
            response = login(self.request(), credentials, self.session)
        access_cookie = self.cookie(response, "access_token")
        refresh_cookie = self.cookie(response, "refresh_token")
        refreshed = refresh_session(self.request(), refresh_cookie, self.session)
        with patch("app.auth.controllers.logout.pg_insert", sqlite_insert):
            logged_out = logout(
                self.request(),
                self.cookie(refreshed, "access_token"),
                self.cookie(refreshed, "refresh_token"),
                self.session,
            )
        self.assertEqual(logged_out.status_code, 200)
        events = self.session.scalars(select(SecurityEvent).order_by(SecurityEvent.created_at, SecurityEvent.id)).all()
        event_types = {item.event_type for item in events}
        self.assertEqual(event_types, {
            SecurityEventType.LOGIN_SUCCESS,
            SecurityEventType.SESSION_CREATED,
            SecurityEventType.SESSION_REFRESHED,
            SecurityEventType.SESSION_REVOKED,
            SecurityEventType.LOGOUT,
        })
        self.assertEqual(len({item.login_id for item in events}), 1)
        self.assertEqual(len({item.device_id for item in events}), 1)
        self.assertTrue(all(item.user_id == self.user.id for item in events))
        self.assertEqual(self.session.scalar(select(func.count()).select_from(AuditLog)), 2)
        self.assertIsNotNone(access_cookie)


if __name__ == "__main__":
    unittest.main()