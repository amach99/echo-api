"""
app/middleware/rate_limiter.py — Sliding-window rate limiter backed by Redis.

Post limits (from PRD §4):
  Human accounts:              2 posts/hour
  Business/Meme/Social Info:   5 posts/hour

Usage:
    from app.middleware.rate_limiter import rate_limit
    from app.models.user import AccountType

    @router.post("/posts")
    async def create_post(
        ...,
        _: None = Depends(rate_limit("post_create")),
    ):
        ...

The limiter degrades gracefully — if Redis is unavailable it logs a warning
and allows the request through (fail-open) rather than blocking all traffic.
"""

import logging
import time
from collections.abc import Callable, Coroutine
from typing import Any

from fastapi import Depends, HTTPException, Request, status
from redis.asyncio import Redis

from app.auth.dependencies import get_current_user
from app.models.user import AccountType, User
from app.redis_client import get_redis

logger = logging.getLogger(__name__)

# Post creation rate limits by account type
_POST_LIMITS: dict[AccountType, int] = {
    AccountType.HUMAN: 2,
    AccountType.BUSINESS: 5,
    AccountType.MEME: 5,
    AccountType.SOCIAL_INFO: 5,
}
_POST_WINDOW_SECONDS = 3600  # 1 hour


def post_rate_limit() -> Callable[..., Coroutine[Any, Any, None]]:
    """
    Dependency factory for post-creation rate limiting.
    Applies the correct per-account-type limit.
    """

    async def _check(
        request: Request,
        current_user: User = Depends(get_current_user),
        redis: Redis = Depends(get_redis),
    ) -> None:
        max_requests = _POST_LIMITS.get(current_user.account_type, 2)
        key = f"rate:posts:{current_user.user_id}"

        try:
            now = int(time.time())
            window_start = now - _POST_WINDOW_SECONDS

            pipe = redis.pipeline()
            # Remove expired entries, add current timestamp, count within window
            await pipe.zremrangebyscore(key, "-inf", window_start)
            await pipe.zadd(key, {str(now): now})
            await pipe.zcard(key)
            await pipe.expire(key, _POST_WINDOW_SECONDS)
            results = await pipe.execute()

            current_count: int = results[2]
            if current_count > max_requests:
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail={
                        "code": "RATE_LIMIT_EXCEEDED",
                        "message": f"Post limit of {max_requests}/hour reached. Try again later.",
                    },
                    headers={"Retry-After": str(_POST_WINDOW_SECONDS)},
                )
        except HTTPException:
            raise
        except Exception as exc:
            # Fail open — Redis unavailable should not block users
            logger.warning("Rate limiter Redis error (fail-open): %s", exc)

    return _check


def general_rate_limit(
    max_requests: int, window_seconds: int, scope: str = "general"
) -> Callable[..., Coroutine[Any, Any, None]]:
    """
    Generic rate limiter for any endpoint.

    Args:
        max_requests:   Maximum number of requests in the window.
        window_seconds: Window duration in seconds.
        scope:          Unique identifier for this limit (e.g. 'auth_login').
    """

    async def _check(
        request: Request,
        redis: Redis = Depends(get_redis),
    ) -> None:
        # Use IP for unauthenticated limits
        client_ip = request.client.host if request.client else "unknown"
        key = f"rate:{scope}:{client_ip}"

        try:
            now = int(time.time())
            window_start = now - window_seconds

            pipe = redis.pipeline()
            await pipe.zremrangebyscore(key, "-inf", window_start)
            await pipe.zadd(key, {str(now): now})
            await pipe.zcard(key)
            await pipe.expire(key, window_seconds)
            results = await pipe.execute()

            current_count: int = results[2]
            if current_count > max_requests:
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail={
                        "code": "RATE_LIMIT_EXCEEDED",
                        "message": "Too many requests. Please slow down.",
                    },
                    headers={"Retry-After": str(window_seconds)},
                )
        except HTTPException:
            raise
        except Exception as exc:
            logger.warning("Rate limiter Redis error (fail-open): %s", exc)

    return _check
