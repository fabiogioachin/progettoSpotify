import asyncio
import logging
import time
import uuid

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from app.services.redis_client import get_redis

logger = logging.getLogger(__name__)


async def retry_with_backoff(
    coro_func,
    *args,
    max_retries: int = 3,
    base_delay: float = 1.0,
    max_retry_after: float = 30.0,
    **kwargs,
):
    """Esegue una coroutine con backoff esponenziale su errori 429/5xx."""
    for attempt in range(max_retries + 1):
        try:
            return await coro_func(*args, **kwargs)
        except RateLimitError as e:
            if isinstance(e, ThrottleError):
                raise  # Non ritentare — il frontend gestisce il countdown
            if attempt == max_retries:
                raise
            delay = base_delay * (2**attempt)
            retry_after = e.retry_after or delay
            if retry_after > max_retry_after:
                logger.warning(
                    "Rate limited with retry_after=%.0fs (exceeds cap of %.0fs) — failing immediately",
                    retry_after,
                    max_retry_after,
                )
                raise
            logger.warning(
                "Rate limited, retry in %ss (attempt %d)", retry_after, attempt + 1
            )
            await asyncio.sleep(retry_after)
        except SpotifyServerError:
            if attempt == max_retries:
                raise
            delay = base_delay * (2**attempt)
            logger.warning(
                "Server error, retry in %ss (attempt %d)", delay, attempt + 1
            )
            await asyncio.sleep(delay)


class RateLimitError(Exception):
    def __init__(self, retry_after: float | None = None):
        self.retry_after = retry_after
        super().__init__(f"Rate limited. Retry after {retry_after}s")


class ThrottleError(RateLimitError):
    """Self-imposed rate limit — budget API quasi esaurito."""

    pass


class SpotifyServerError(Exception):
    pass


class SpotifyAuthError(Exception):
    pass


async def gather_in_chunks(coros, chunk_size=4):
    """Esegue coroutine in batch sequenziali per limitare i burst."""
    results = []
    for i in range(0, len(coros), chunk_size):
        chunk = coros[i : i + chunk_size]
        results.extend(await asyncio.gather(*chunk, return_exceptions=True))
    return results


class APIRateLimiter(BaseHTTPMiddleware):
    """Sliding window rate limiter per utente/IP — backed by Redis sorted sets.

    Graceful degradation: if Redis is down, requests are allowed (fail-open).
    """

    # Paths exempted from rate limiting (lightweight, essential endpoints)
    EXEMPT_PATHS = {"/auth/me", "/health"}

    _REDIS_KEY_PREFIX = "ratelimit:api:"
    _KEY_TTL = 120  # seconds — auto-cleanup for stale IP keys

    def __init__(self, app, requests_per_minute: int = 120):
        super().__init__(app)
        self.rpm = requests_per_minute
        self._window = 60.0

    async def dispatch(self, request, call_next):
        # Skip rate limiting for lightweight/essential endpoints
        if request.url.path in self.EXEMPT_PATHS:
            return await call_next(request)

        # Use IP as key — ProxyHeadersMiddleware already rewrites request.client.host
        # when BEHIND_PROXY=true, so we always use request.client.host (no manual
        # X-Forwarded-For parsing, which would allow rate limit bypass via spoofing)
        ip = request.client.host if request.client else "unknown"

        try:
            r = get_redis()
            redis_key = f"{self._REDIS_KEY_PREFIX}{ip}"
            now = time.time()
            window_start = now - self._window
            call_id = uuid.uuid4().hex

            pipe = r.pipeline(transaction=True)
            # Cleanup expired entries
            pipe.zremrangebyscore(redis_key, 0, window_start)
            # Get current entries in window
            pipe.zrangebyscore(redis_key, window_start, "+inf", withscores=True)
            # Add this request
            pipe.zadd(redis_key, {call_id: now})
            # Set TTL for auto-cleanup
            pipe.expire(redis_key, self._KEY_TTL)
            results = await pipe.execute()

            # results[1] is list of (member, score) tuples in window before adding
            entries = results[1]
            if len(entries) >= self.rpm:
                # Over limit — remove the entry we just added
                try:
                    await r.zrem(redis_key, call_id)
                except Exception:
                    pass
                oldest_score = entries[0][1] if entries else now
                retry_after = int(self._window - (now - oldest_score)) + 1
                return JSONResponse(
                    status_code=429,
                    content={"detail": "Troppe richieste. Riprova tra poco."},
                    headers={"Retry-After": str(max(1, retry_after))},
                )
        except Exception:
            # Fail-open: Redis down → allow the request
            logger.warning(
                "Redis non disponibile per API rate limiter — fail-open per %s",
                ip,
            )

        return await call_next(request)
