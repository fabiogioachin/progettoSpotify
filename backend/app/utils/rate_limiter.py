import asyncio
import logging

logger = logging.getLogger(__name__)


async def retry_with_backoff(coro_func, *args, max_retries: int = 3, base_delay: float = 1.0, **kwargs):
    """Esegue una coroutine con backoff esponenziale su errori 429/5xx."""
    for attempt in range(max_retries + 1):
        try:
            return await coro_func(*args, **kwargs)
        except RateLimitError as e:
            if attempt == max_retries:
                raise
            delay = base_delay * (2 ** attempt)
            retry_after = e.retry_after or delay
            logger.warning(f"Rate limited, retry in {retry_after}s (attempt {attempt + 1})")
            await asyncio.sleep(retry_after)
        except SpotifyServerError:
            if attempt == max_retries:
                raise
            delay = base_delay * (2 ** attempt)
            logger.warning(f"Server error, retry in {delay}s (attempt {attempt + 1})")
            await asyncio.sleep(delay)


class RateLimitError(Exception):
    def __init__(self, retry_after: float | None = None):
        self.retry_after = retry_after
        super().__init__(f"Rate limited. Retry after {retry_after}s")


class SpotifyServerError(Exception):
    pass


class SpotifyAuthError(Exception):
    pass


# ---- API Rate Limiter Middleware ----

import time
from collections import defaultdict

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse


class APIRateLimiter(BaseHTTPMiddleware):
    """Sliding window rate limiter per utente/IP."""

    def __init__(self, app, requests_per_minute: int = 60):
        super().__init__(app)
        self.rpm = requests_per_minute
        self._requests: dict[str, list[float]] = defaultdict(list)

    async def dispatch(self, request, call_next):
        # Rate limit by session cookie (user) or IP as fallback
        key = request.cookies.get("session") or (request.client.host if request.client else "unknown")
        now = time.time()
        window = 60.0

        # Clean old entries
        self._requests[key] = [t for t in self._requests[key] if now - t < window]

        if len(self._requests[key]) >= self.rpm:
            return JSONResponse(
                status_code=429,
                content={"detail": "Troppe richieste. Riprova tra poco."},
            )

        self._requests[key].append(now)
        return await call_next(request)
