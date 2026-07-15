import time
import uuid

from fastapi import Depends
from redis.asyncio import Redis

from app.config import get_settings
from app.core.exceptions import RateLimitExceededError
from app.core.security import get_current_tenant_id_dep

_redis: Redis | None = None


def get_redis() -> Redis:
    global _redis
    if _redis is None:
        _redis = Redis.from_url(get_settings().redis_url)
    return _redis


async def enforce_rate_limit(tenant_id: uuid.UUID) -> None:
    """Fixed-window per-tenant rate limit backed by Redis INCR/EXPIRE. Simpler than
    a true token bucket and sufficient to bound abuse; revisit if burst smoothing
    across window boundaries becomes a real requirement."""
    settings = get_settings()
    redis = get_redis()
    window = int(time.time() // 60)
    key = f"ratelimit:{tenant_id}:{window}"

    count = await redis.incr(key)
    if count == 1:
        await redis.expire(key, 60)
    if count > settings.rate_limit_requests_per_minute:
        raise RateLimitExceededError("Rate limit exceeded, try again later")


async def rate_limit_dependency(tenant_id: uuid.UUID = Depends(get_current_tenant_id_dep)) -> None:
    await enforce_rate_limit(tenant_id)
