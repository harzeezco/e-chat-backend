import os
import redis
from dotenv import load_dotenv

load_dotenv()
REDIS_DSN = os.getenv("REDIS_DSN",
                      "redis://localhost:6379/0",)


redis_client = redis.Redis.from_url(
    REDIS_DSN,
    decode_responses=True
)
