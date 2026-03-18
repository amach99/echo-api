"""
app/redis_client.py — Async Redis connection pool.

Used for:
  - Feed caching (Life + Pulse feeds)
  - Rate limiting counters
  - Stories TTL (Phase 2)
  - Session/JWT denylist
"""

from collections.abc import AsyncGenerator

import redis.asyncio as aioredis
from redis.asyncio import Redis

from app.config import get_settings

settings = get_settings()

# Module-level pool — initialised once at app startup
_redis_pool: Redis | None = None


async def init_redis() -> None:
    """Call once at app startup (lifespan event)."""
    global _redis_pool
    _redis_pool = aioredis.from_url(
        settings.REDIS_URL,
        encoding="utf-8",
        decode_responses=True,
        max_connections=20,
    )
    # Verify connectivity
    await _redis_pool.ping()


async def close_redis() -> None:
    """Call once at app shutdown (lifespan event)."""
    global _redis_pool
    if _redis_pool:
        await _redis_pool.aclose()
        _redis_pool = None


async def get_redis() -> AsyncGenerator[Redis, None]:
    """FastAPI dependency — yields the shared Redis client."""
    if _redis_pool is None:
        raise RuntimeError("Redis pool not initialised. Call init_redis() at startup.")
    yield _redis_pool
