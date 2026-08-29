"""
extensions.py — Shared Flask extensions & utilities
====================================================
Centralizes objects that both app.py and blueprint routes need,
avoiding circular imports.
"""

from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from cachetools import TTLCache
from config import Config

# Rate limiting — prevents DoS on heavy endpoints
# Initialized without app; app binding happens in app.py via init_app()
limiter = Limiter(
    get_remote_address,
    default_limits=[Config.RATELIMIT_DEFAULT],
    storage_uri="memory://",
)

# Preview cache — in-memory TTL cache keyed by MD5 of request body
# Each Gunicorn worker has its own cache (good enough for dev/single-node prod).
# Swap to Redis-backed cache for multi-node production.
preview_cache: TTLCache = TTLCache(
    maxsize=Config.PREVIEW_CACHE_SIZE,
    ttl=Config.PREVIEW_CACHE_TTL,
)


def _to_float(value) -> float:
    """Safely convert a value to float, handling currency symbols and commas."""
    if not value:
        return 0.0
    cleaned = str(value).replace(',', '').replace('₹', '').strip()
    try:
        return float(cleaned)
    except ValueError:
        return 0.0
