"""FastAPI application entry point."""

import logging
import os
import time
from contextlib import asynccontextmanager

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from app.config import settings
from app.database import async_session, init_db
from app.routers import (
    analysis,
    analytics,
    artist_network,
    auth,
    export,
    historical,
    library,
    playlist_analytics,
    playlists,
    profile,
    social,
    taste_evolution,
    temporal,
    wrapped,
)
from app.services.background_tasks import compute_daily_aggregates, sync_recent_plays
from app.services.spotify_client import SpotifyClient
from app.utils.rate_limiter import (
    APIRateLimiter,
    RateLimitError,
    SpotifyAuthError,
    SpotifyServerError,
    ThrottleError,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

scheduler = AsyncIOScheduler()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Assicura che la directory data esista
    os.makedirs("data", exist_ok=True)
    await init_db()
    logger.info("Database inizializzato")
    if not settings.cookie_secure and not settings.frontend_url.startswith(
        "http://127"
    ):
        logger.warning(
            "SECURITY: cookie_secure=False su ambiente non-localhost. Impostare COOKIE_SECURE=true in produzione."
        )

    # APScheduler: sync ascolti recenti ogni 60 minuti
    scheduler.add_job(
        sync_recent_plays,
        trigger=IntervalTrigger(minutes=60),
        id="sync_recent_plays",
        name="Sync ascolti recenti ogni 60 minuti",
        replace_existing=True,
    )
    scheduler.add_job(
        compute_daily_aggregates,
        trigger=CronTrigger(hour=2, minute=0),
        id="compute_daily_aggregates",
        name="Calcolo aggregati giornalieri alle 02:00",
        replace_existing=True,
    )
    scheduler.start()
    logger.info(
        "APScheduler avviato — sync_recent_plays ogni 60 minuti, compute_daily_aggregates alle 02:00"
    )

    yield

    scheduler.shutdown(wait=False)
    logger.info("APScheduler arrestato")


class RateLimitHeaderMiddleware(BaseHTTPMiddleware):
    """Inject X-RateLimit-Usage header into every /api/ response."""

    async def dispatch(self, request, call_next):
        response = await call_next(request)
        if request.url.path.startswith("/api/"):
            now = time.monotonic()
            current = sum(
                1
                for t in SpotifyClient._call_timestamps
                if t > now - SpotifyClient._WINDOW_SIZE
            )
            max_calls = SpotifyClient._MAX_CALLS_PER_WINDOW
            response.headers["X-RateLimit-Usage"] = f"{current}/{max_calls}"
        return response


app = FastAPI(
    title="Spotify Listening Intelligence",
    description="Dashboard di analisi musicale personale",
    version="1.0.0",
    lifespan=lifespan,
)


@app.exception_handler(SpotifyAuthError)
async def spotify_auth_exception_handler(request, exc: SpotifyAuthError):
    """Token scaduto/corrotto → 401, il frontend redirige al login."""
    logger.warning("SpotifyAuthError: %s", exc)
    return JSONResponse(
        status_code=401,
        content={"detail": "Sessione scaduta"},
    )


@app.exception_handler(RateLimitError)
async def rate_limit_exception_handler(request, exc: RateLimitError):
    """Propaga i 429 di Spotify al frontend con il corretto Retry-After."""
    retry_after = round(exc.retry_after or 5, 1)
    is_throttle = isinstance(exc, ThrottleError)
    logger.warning(
        "Rate limit propagato al frontend: Retry-After=%.0fs, throttled=%s",
        retry_after,
        is_throttle,
    )
    return JSONResponse(
        status_code=429,
        content={
            "detail": {
                "message": f"Troppe richieste. Riprova tra {int(retry_after)} secondi.",
                "throttled": is_throttle,
                "retry_after": retry_after,
            }
        },
        headers={"Retry-After": str(int(retry_after))},
    )


@app.exception_handler(SpotifyServerError)
async def spotify_server_exception_handler(request, exc: SpotifyServerError):
    """Errore transitorio lato Spotify → 502."""
    logger.warning("SpotifyServerError: %s", exc)
    return JSONResponse(
        status_code=502,
        content={"detail": "Spotify non disponibile al momento"},
    )


# Proxy support: trust X-Forwarded-For when behind a reverse proxy
if os.getenv("BEHIND_PROXY", "").lower() == "true":
    from uvicorn.middleware.proxy_headers import ProxyHeadersMiddleware

    app.add_middleware(ProxyHeadersMiddleware, trusted_hosts=["*"])

# Rate Limiter (prima di CORS per intercettare richieste eccessive)
app.add_middleware(APIRateLimiter, requests_per_minute=120)

# CORS (restrict methods and headers to what the app actually uses)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_url],
    allow_credentials=True,
    allow_methods=["GET", "POST", "DELETE"],
    allow_headers=["Content-Type"],
    expose_headers=["X-RateLimit-Usage"],
)

# Rate limit usage header (runs inside CORS — added after CORSMiddleware)
app.add_middleware(RateLimitHeaderMiddleware)

# Routers
app.include_router(auth.router)
app.include_router(analysis.router)
app.include_router(library.router)
app.include_router(playlists.router)
app.include_router(analytics.router)
app.include_router(export.router)
app.include_router(taste_evolution.router)
app.include_router(temporal.router)
app.include_router(artist_network.router)
app.include_router(playlist_analytics.router)
app.include_router(historical.router)
app.include_router(wrapped.router)
app.include_router(profile.router)
app.include_router(social.router)


@app.get("/health")
async def health():
    """Health check con verifica database."""
    checks = {"database": "ok"}
    try:
        from sqlalchemy import text

        async with async_session() as session:
            await session.execute(text("SELECT 1"))
    except Exception as e:
        checks["database"] = "error"
        logger.error(f"Health check database failed: {e}")

    status = "ok" if all(v == "ok" for v in checks.values()) else "degraded"
    status_code = 200 if status == "ok" else 503
    return JSONResponse(
        content={"status": status, "checks": checks}, status_code=status_code
    )


@app.get("/api/rate-limit-status")
async def rate_limit_status():
    """Stato corrente del budget API Spotify (sliding window)."""
    now = time.monotonic()
    current = sum(
        1
        for t in SpotifyClient._call_timestamps
        if t > now - SpotifyClient._WINDOW_SIZE
    )
    max_calls = SpotifyClient._MAX_CALLS_PER_WINDOW
    cooldown_remaining = max(0, SpotifyClient._cooldown_until - now)
    return {
        "calls_in_window": current,
        "max_calls": max_calls,
        "window_seconds": SpotifyClient._WINDOW_SIZE,
        "usage_pct": round(current / max_calls * 100, 1) if max_calls else 0,
        "cooldown_remaining": round(cooldown_remaining, 1),
    }
