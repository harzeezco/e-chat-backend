from app.lib.redis_client import redis_client


class RateLimiter():
    def __init__(self, limit: int, window_seconds: int) -> None:
        self.limit = limit
        self.window_seconds = window_seconds

    def check(self, key: str) -> tuple[bool, int]:
        count = redis_client.incr(key)

        if count == 1:
            redis_client.expire(key, self.window_seconds)

        allowed = count <= self.limit

        return allowed, count
