import os
import jwt

from dotenv import load_dotenv
from datetime import datetime, timezone, timedelta
from uuid import uuid4

load_dotenv()

SECRET_KEY = os.getenv("JWT_SECRET_KEY")
ALGORITHM = os.getenv("JWT_ALGORITHM")
ACCESS_TOKEN_MINUTES = int(os.getenv("ACCESS_TOKEN_MINUTES", "15"))

REFRESH_TOKEN_DAYS = int(os.getenv("REFRESH_TOKEN_DAYS", "5"))

ISSUER = "ai-fintech-operation-lab"
AUDIENCE = "ai-fintech-api"


def _create_token(user_id: str, token_type: str, expires_delta: timedelta):
    now = datetime.now(timezone.utc)

    payload = {
        "sub": user_id,
        "jti": str(uuid4()),
        "token_type": token_type,
        "iat": now,
        "exp": now + expires_delta,
        "iss": ISSUER,
        "aud": AUDIENCE
    }

    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)

def access_token(user_id) -> str:
    return _create_token(
        user_id=user_id,
        token_type="access",
        expires_delta=timedelta(minutes=ACCESS_TOKEN_MINUTES)
    )

def refresh_token(user_id) -> str:
    return _create_token(
        user_id=user_id,
        token_type="refresh",
        expires_delta=timedelta(days=REFRESH_TOKEN_DAYS)
    )

def decode_refresh_token(token: str) -> dict:
    payload = jwt.decode(
        token,
        SECRET_KEY,
        algorithms=[ALGORITHM],
        issuer=ISSUER,
        audience=AUDIENCE,
        options={
            "require": [
                "sub",
                "jti",
                "token_type",
                "iat",
                "exp",
                "iss",
                "aud"
            ]
        }
    )

    if payload.get("token_type") != "refresh":
        raise jwt.InvalidTokenError("Expected a refresh token")

    return payload


def decode_access_token(token: str) -> dict:
    payload = jwt.decode(
        token,
        SECRET_KEY,
        algorithms=[ALGORITHM],
        issuer=ISSUER,
        audience=AUDIENCE,
        options={
             "require": [
                 "sub",
                 "jti",
                 "token_type",
                 "iat",
                 "exp",
                 "iss",
                 "aud"
             ]
         }

        )

    if payload.get("token_type") != "access":
            raise jwt.InvalidTokenError("Expected a access token")

    return payload
