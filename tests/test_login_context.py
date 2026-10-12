"""Checks that login context survives refresh-token rotation."""

import os
import unittest
from datetime import datetime, timedelta, timezone
from http.cookies import SimpleCookie
from uuid import uuid4

os.environ.setdefault("DB_DSN", "sqlite://")
os.environ.setdefault("JWT_SECRET_KEY", "test-only-login-context-secret")
os.environ.setdefault("JWT_ALGORITHM", "HS256")

import jwt
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.auth.controllers.refresh import refresh_session
from app.auth.dependencies import get_current_login
from app.auth.models.refresh_token import RefreshToken
from app.auth.models.revoked_access_token import RevokedAccessToken
from app.auth.models.user import User, UserRole, UserStatus
from app.auth.services.jwt_access_token import (
    ALGORITHM,
    AUDIENCE,
    ISSUER,
    SECRET_KEY,
    access_token,
    decode_access_token,
    decode_refresh_token,
    refresh_token,
)
from app.security.models.user_device import UserDevice


class LoginContextTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine(
            "sqlite://",
            poolclass=StaticPool,
            connect_args={"check_same_thread": False},
        )
        for table in (
            User.__table__,
            UserDevice.__table__,
            RefreshToken.__table__,
            RevokedAccessToken.__table__,
        ):
            table.create(self.engine)
        self.session = sessionmaker(bind=self.engine)()
        self.addCleanup(self.engine.dispose)
        self.addCleanup(self.session.close)

        self.user = User(
            id="usr_login_context",
            email="context@example.com",
            password_hash="unused",
            role=UserRole.CUSTOMER,
            status=UserStatus.ACTIVE,
        )
        self.device = UserDevice(
            id="dev_login_context",
            user_id=self.user.id,
            identifier_hash="a" * 64,
        )
        self.session.add_all((self.user, self.device))
        self.session.commit()

    def cookie(self, response, name):
        for header in response.headers.getlist("set-cookie"):
            parsed = SimpleCookie()
            parsed.load(header)
            if name in parsed:
                return parsed[name].value
        self.fail(f"Missing {name} cookie")

    def test_refresh_preserves_original_login_context(self):
        context = {
            "login_id": str(uuid4()),
            "device_id": self.device.id,
            "new_device_at_login": True,
        }
        old_access = access_token(self.user.id, **context)
        old_refresh = refresh_token(self.user.id, **context)
        old_claims = decode_refresh_token(old_refresh)
        authenticated = get_current_login(
            access_cookie=old_access,
            session=self.session,
        )
        self.assertEqual(authenticated.login_id, context["login_id"])
        self.assertTrue(authenticated.new_device_at_login)

        self.session.add(
            RefreshToken(
                jti=old_claims["jti"],
                user_id=self.user.id,
                **context,
                expires_at=datetime.fromtimestamp(old_claims["exp"], timezone.utc),
            )
        )
        self.session.commit()

        response = refresh_session(refresh_cookie=old_refresh, session=self.session)
        access_claims = decode_access_token(self.cookie(response, "access_token"))
        refresh_claims = decode_refresh_token(self.cookie(response, "refresh_token"))
        for claims in (access_claims, refresh_claims):
            for name, value in context.items():
                self.assertEqual(claims[name], value)

        old_row = self.session.get(RefreshToken, old_claims["jti"])
        new_row = self.session.get(RefreshToken, refresh_claims["jti"])
        self.assertIsNotNone(old_row.revoked_at)
        self.assertEqual(old_row.replaced_by_jti, refresh_claims["jti"])
        self.assertEqual(new_row.login_id, context["login_id"])
        self.assertEqual(new_row.device_id, context["device_id"])
        self.assertTrue(new_row.new_device_at_login)

    def test_refresh_rejects_context_mismatch(self):
        token = refresh_token(
            self.user.id,
            login_id=str(uuid4()),
            device_id=self.device.id,
            new_device_at_login=False,
        )
        claims = decode_refresh_token(token)
        self.session.add(
            RefreshToken(
                jti=claims["jti"],
                user_id=self.user.id,
                login_id=str(uuid4()),
                device_id=self.device.id,
                new_device_at_login=False,
                expires_at=datetime.fromtimestamp(claims["exp"], timezone.utc),
            )
        )
        self.session.commit()

        with self.assertRaises(HTTPException) as error:
            refresh_session(refresh_cookie=token, session=self.session)
        self.assertEqual(error.exception.status_code, 401)
        self.assertIsNone(self.session.get(RefreshToken, claims["jti"]).revoked_at)

    def test_old_refresh_token_gets_unknown_device_context(self):
        now = datetime.now(timezone.utc)
        old_token = jwt.encode(
            {
                "sub": self.user.id,
                "jti": str(uuid4()),
                "token_type": "refresh",
                "iat": now,
                "exp": now + timedelta(days=1),
                "iss": ISSUER,
                "aud": AUDIENCE,
            },
            SECRET_KEY,
            algorithm=ALGORITHM,
        )
        old_claims = decode_refresh_token(old_token)
        self.session.add(
            RefreshToken(
                jti=old_claims["jti"],
                user_id=self.user.id,
                expires_at=datetime.fromtimestamp(old_claims["exp"], timezone.utc),
            )
        )
        self.session.commit()

        response = refresh_session(refresh_cookie=old_token, session=self.session)
        new_claims = decode_refresh_token(self.cookie(response, "refresh_token"))
        self.assertTrue(new_claims["login_id"])
        self.assertIsNone(new_claims["device_id"])
        self.assertIsNone(new_claims["new_device_at_login"])


if __name__ == "__main__":
    unittest.main()
