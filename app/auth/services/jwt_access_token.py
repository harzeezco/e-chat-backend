import os
import jwt

from dotenv import load_dotenv
from datetime import datetime, timezone, timedelta

load_dotenv()

SECRET_KEY = os.getenv("JWT_SECRET_KEY")
ALGORITHM = os.getenv("JWT_ALGORITHM")
ACCESS_TOKEN_MINUTES = int(os.getenv("JWT_EXPIRE_MINUTES"))


def access_token(user_id) -> str:
    now = datetime.now(timezone.utc)

    payload = {
        "sub": user_id,
        "iat": now,
        "exp": now + timedelta(minutes=ACCESS_TOKEN_MINUTES),
        "iss": "ai-fintech-operation-lab",
        "aud": "ai-fintech-api"
    }

    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)
