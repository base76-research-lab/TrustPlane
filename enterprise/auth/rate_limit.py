from __future__ import annotations

import os
import time
from typing import Optional

# Redis-backed token bucket rate limiter.
# Falls back to in-memory if Redis is unavailable.

try:
    import redis.asyncio as aioredis
    _redis_available = True
except ImportError:
    _redis_available = False

_REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
_redis_client: Optional[object] = None


async def _get_redis():
    global _redis_client
    if not _redis_available:
        return None
    if _redis_client is None:
        try:
            _redis_client = aioredis.from_url(_REDIS_URL, decode_responses=True)
            await _redis_client.ping()
        except Exception:
            _redis_client = None
    return _redis_client


# In-memory fallback
_memory_buckets: dict[str, dict] = {}


def _parse_rate(rate_str: str) -> tuple[int, int]:
    """Parse '1000/day' -> (1000, 86400). Supports /day /hour /minute."""
    parts = rate_str.split("/")
    count = int(parts[0])
    unit = parts[1].lower() if len(parts) > 1 else "day"
    period = {"day": 86400, "hour": 3600, "minute": 60}.get(unit, 86400)
    return count, period


async def check_rate_limit(tenant_id: str, rate_str: str) -> tuple[bool, int]:
    """
    Returns (allowed, remaining).
    allowed=False means rate limit exceeded.
    """
    max_count, period = _parse_rate(rate_str)
    key = f"rl:{tenant_id}:{period}"

    r = await _get_redis()
    if r is not None:
        try:
            pipe = r.pipeline()
            now = int(time.time())
            window_start = now - period
            await pipe.zremrangebyscore(key, "-inf", window_start)
            await pipe.zadd(key, {str(now): now})
            await pipe.zcard(key)
            await pipe.expire(key, period)
            results = await pipe.execute()
            count = results[2]
            remaining = max(0, max_count - count)
            return count <= max_count, remaining
        except Exception:
            pass

    # In-memory fallback
    now = time.time()
    bucket = _memory_buckets.setdefault(key, {"count": 0, "reset_at": now + period})
    if now > bucket["reset_at"]:
        bucket["count"] = 0
        bucket["reset_at"] = now + period
    bucket["count"] += 1
    remaining = max(0, max_count - bucket["count"])
    return bucket["count"] <= max_count, remaining
