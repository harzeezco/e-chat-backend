import os


# Local development uses HTTP. Set COOKIE_SECURE=true wherever HTTPS serves the API.
COOKIE_SECURE = os.getenv("COOKIE_SECURE", "false").lower() == "true"
