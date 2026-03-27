"""Per-user rate limiting middleware.

Redis sorted set per user: ratelimit:user:{user_id}:pages
Sliding 1-minute window.
Limits by tier: free=30/min, premium=60/min, admin=unlimited.
Fail-open on Redis errors.
"""

import logging
import time

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

logger = logging.getLogger(__name__)


class UserQuotaMiddleware(BaseHTTPMiddleware):
    """Per-user rate limiting on /api/v1/ requests."""

    TIER_LIMITS: dict[str, int | None] = {
        "free": 30,
        "premium": 60,
        "admin": None,
    }
    WINDOW_SECONDS: int = 60

    async def dispatch(self, request: Request, call_next):
        # Only check /api/v1/ paths
        if not request.url.path.startswith("/api/v1/"):
            return await call_next(request)

        # Extract user_id from session cookie (best-effort)
        from app.dependencies import get_session_user_id

        user_id = get_session_user_id(request)
        if not user_id:
            return await call_next(request)

        try:
            from app.services.redis_client import get_redis

            redis = get_redis()

            # Get tier from Redis cache, or default to "free"
            tier_key = f"user:tier:{user_id}"
            tier = await redis.get(tier_key)
            if tier is None:
                # Lookup from DB, cache for 5 min
                from sqlalchemy import select

                from app.database import async_session
                from app.models.user import User

                async with async_session() as session:
                    row = (
                        await session.execute(
                            select(User.tier, User.is_admin).where(User.id == user_id)
                        )
                    ).first()
                    if row:
                        tier = "admin" if row.is_admin else (row.tier or "free")
                    else:
                        tier = "free"
                await redis.set(tier_key, tier, ex=300)

            limit = self.TIER_LIMITS.get(tier)
            if limit is None:  # admin — unlimited
                return await call_next(request)

            # Sliding window check
            now = time.time()
            window_key = f"ratelimit:user:{user_id}:pages"
            pipe = redis.pipeline()
            pipe.zremrangebyscore(window_key, 0, now - self.WINDOW_SECONDS)
            pipe.zcard(window_key)
            pipe.zadd(window_key, {str(now): now})
            pipe.expire(window_key, self.WINDOW_SECONDS + 10)
            results = await pipe.execute()
            current_count = results[1]

            if current_count >= limit:
                return JSONResponse(
                    status_code=429,
                    content={"detail": "Troppe richieste per il tuo account"},
                    headers={"Retry-After": str(self.WINDOW_SECONDS)},
                )
        except Exception:
            # Fail-open on Redis errors
            pass

        return await call_next(request)
