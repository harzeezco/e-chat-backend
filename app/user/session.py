import secrets
import redis.asyncio as redis


print(secrets.token_urlsafe(32))


def generate_session_token() -> str:
    return secrets.token_urlsafe(32)


async def create_session(
    redis_client: redis.Redis,
    user_id: str
) -> str:
    token = generate_session_token()

    await redis_client.setex(
        f"session:{token}",
        3600,
        user_id
    )

    return token
