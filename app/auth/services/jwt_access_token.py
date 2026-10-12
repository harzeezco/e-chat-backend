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


LOGIN_CONTEXT_CLAIMS = ("login_id", "device_id", "new_device_at_login")


def _create_token(
    user_id: str,
    token_type: str,
    expires_delta: timedelta,
    *,
    login_id: str,
    device_id: str | None,
    new_device_at_login: bool | None,
):
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

    payload.update(
        login_id=login_id,
        device_id=device_id,
        new_device_at_login=new_device_at_login,
    )

    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)

def access_token(
    user_id: str,
    *,
    login_id: str,
    device_id: str | None,
    new_device_at_login: bool | None,
) -> str:
    return _create_token(
        user_id=user_id,
        token_type="access",
        expires_delta=timedelta(minutes=ACCESS_TOKEN_MINUTES),
        login_id=login_id,
        device_id=device_id,
        new_device_at_login=new_device_at_login,
    )

def refresh_token(
    user_id: str,
    *,
    login_id: str,
    device_id: str | None,
    new_device_at_login: bool | None,
) -> str:
    return _create_token(
        user_id=user_id,
        token_type="refresh",
        expires_delta=timedelta(days=REFRESH_TOKEN_DAYS),
        login_id=login_id,
        device_id=device_id,
        new_device_at_login=new_device_at_login,
    )


def _validate_login_context(payload: dict) -> None:
    # Tokens issued before this feature have none of these claims. Treat
    # their device context as unknown until they expire or are refreshed.
    present = [name in payload for name in LOGIN_CONTEXT_CLAIMS]
    if not any(present):
        return
    if not all(present):
        raise jwt.InvalidTokenError("Incomplete login context")

    if not isinstance(payload["login_id"], str) or not payload["login_id"]:
        raise jwt.InvalidTokenError("Invalid login ID")

    device_id = payload["device_id"]
    new_device = payload["new_device_at_login"]
    if device_id is not None and (not isinstance(device_id, str) or not device_id):
        raise jwt.InvalidTokenError("Invalid device ID")
    if new_device is not None and type(new_device) is not bool:
        raise jwt.InvalidTokenError("Invalid device status")
    if device_id is None and new_device is not None:
        raise jwt.InvalidTokenError("Device status requires a device ID")

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

    _validate_login_context(payload)

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
            raise jwt.InvalidTokenError("Expected an access token")

    _validate_login_context(payload)

    return payload
