from app.lib.redis_client import redis_client

VERIFICATION_TTL = 600


def store_verification_token(token: str, user_id: str) -> None:
    key = f"verification:{token}"

    redis_client.set(
        key,
        user_id,
        ex=VERIFICATION_TTL,
    )


def get_verification_user_id(token: str) -> str | None | bytes:
    key = f"verification:{token}"

    user_id = redis_client.get(key)

    return user_id


def delete_verification_token(token: str) -> None:
    key = f"verification:{token}"

    redis_client.delete(key)
