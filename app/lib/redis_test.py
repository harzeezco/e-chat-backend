from app.lib.redis_client import redis_client
from app.user.utils.rate_limiter import RateLimiter


key = "rate_limit:test:user"

registration_limiter = RateLimiter(
    limit=5,
    window_seconds=60,
)

redis_client.delete(key)

for i in range(7):
    allowed, count = registration_limiter.check(key)

    print(
        f"request={i + 1} "
        f"count={count} "
        f"allowed={allowed}"
    )
