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
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.auth.controllers.login import login
from app.auth.models.audit_log import AuditLog
from app.auth.models.login_attempt import LoginAttempt
from app.auth.models.refresh_token import RefreshToken
from app.auth.models.user import User, UserRole, UserStatus
from app.auth.schemas.login import LoginRequest
from app.security.models.user_device import UserDevice


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


if __name__ == "__main__":
    unittest.main()