"""FastAPI application entry point."""

import asyncio
import logging
import os
from contextlib import asynccontextmanager

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse, RedirectResponse

from app.config import settings
from app.database import async_session
from app.services.redis_client import close_redis, redis_ping
from app.routers import (
    admin,
    analysis,
    analytics,
    artist_network,
    auth,
    export,
    historical,
    library,
    playlist_analytics,
    playlists,
    privacy,
    profile,
    social,
    taste_evolution,
    temporal,
    wrapped,
)
from app.services.background_tasks import (
    compute_daily_aggregates,
    sync_recent_plays,
    _sync_user_recent_plays,
)
from app.services.data_retention import cleanup_expired_data
from app.services.spotify_client import SpotifyClient
from app.utils.rate_limiter import (
    APIRateLimiter,
    RateLimitError,
    SpotifyAuthError,
    SpotifyServerError,
    ThrottleError,
)

from app.middleware.request_context import (
    RequestContextFilter,
    RequestContextMiddleware,
)
from app.middleware.user_quota import UserQuotaMiddleware

# --- Structured logging setup ---
_root_logger = logging.getLogger()
_root_logger.setLevel(logging.INFO)

_context_filter = RequestContextFilter()

if settings.environment != "development":
    from pythonjsonlogger.json import JsonFormatter

    _json_formatter = JsonFormatter(
        fmt="%(asctime)s %(levelname)s %(name)s %(message)s %(request_id)s %(user_id)s",
        datefmt="%Y-%m-%dT%H:%M:%S%z",
        rename_fields={"asctime": "timestamp", "levelname": "level", "name": "logger"},
    )
    _handler = logging.StreamHandler()
    _handler.setFormatter(_json_formatter)
    _handler.addFilter(_context_filter)
    _root_logger.addHandler(_handler)
else:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    for h in _root_logger.handlers:
        h.addFilter(_context_filter)

logger = logging.getLogger(__name__)

scheduler = AsyncIOScheduler()


async def _startup_sync_recent_plays():
    """Sync ascolti recenti per tutti gli utenti all'avvio del backend.

    In dev mode il backend non gira 24/7 — al boot pagina all'indietro
    finche' non raggiunge l'ultimo ascolto gia' nel DB (max 20 pagine = 1000 brani
    come safety cap per evitare loop infiniti, anche se Spotify non ne ha cosi' tanti).
    """
    from sqlalchemy import select

    from app.models.user import User
    from app.services.api_budget import Priority

    await asyncio.sleep(5)  # Lascia che il backend si stabilizzi
    try:
        async with async_session() as db:
            result = await db.execute(select(User.id))
            user_ids = [row[0] for row in result.fetchall()]

        if not user_ids:
            return

        logger.info(
            "Startup sync: recupero ascolti recenti per %d utenti (fino a overlap con DB)",
            len(user_ids),
        )

        for uid in user_ids:
            try:
                async with async_session() as db:
                    client = SpotifyClient(
                        db, uid, priority=Priority.P1_BACKGROUND_SYNC
                    )
                    try:
                        await _sync_user_recent_plays(
                            db, uid, client, max_pages=20
                        )
                    finally:
                        await client.close()
            except Exception as exc:
                logger.warning("Startup sync user_id=%d fallito: %s", uid, exc)
            await asyncio.sleep(5)  # Stagger tra utenti

        logger.info("Startup sync completato")
    except Exception as exc:
        logger.warning("Startup sync fallito: %s", exc)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Backend avviato — database gestito da Alembic")
    if not settings.cookie_secure and not settings.frontend_url.startswith(
        "http://127"
    ):
        logger.warning(
            "SECURITY: cookie_secure=False su ambiente non-localhost. Impostare COOKIE_SECURE=true in produzione."
        )

    # APScheduler: sync ascolti recenti ogni 60 minuti
    # jitter=120 adds random 0-120s delay to prevent thundering herd on restart
    scheduler.add_job(
        sync_recent_plays,
        trigger=IntervalTrigger(minutes=60),
        id="sync_recent_plays",
        name="Sync ascolti recenti ogni 60 minuti",
        replace_existing=True,
        jitter=120,
    )
    # jitter=300 adds random 0-300s delay to the 02:00 job
    scheduler.add_job(
        compute_daily_aggregates,
        trigger=CronTrigger(hour=2, minute=0),
        id="compute_daily_aggregates",
        name="Calcolo aggregati giornalieri alle 02:00",
        replace_existing=True,
        jitter=300,
    )
    # Monthly cleanup of expired data (1st of month, 03:00)
    scheduler.add_job(
        cleanup_expired_data,
        trigger=CronTrigger(day=1, hour=3, minute=0),
        id="cleanup_expired_data",
        name="Pulizia dati scaduti mensile (1\u00b0 del mese, 03:00)",
        replace_existing=True,
        jitter=600,
    )
    scheduler.start()
    logger.info(
        "APScheduler avviato — sync_recent_plays ogni 60 minuti (jitter=120s), "
        "compute_daily_aggregates alle 02:00 (jitter=300s), "
        "cleanup_expired_data il 1\u00b0 del mese alle 03:00 (jitter=600s)"
    )

    # Startup sync: recupera ascolti recenti per tutti gli utenti (max 3 pagine = 150 brani)
    # Non-blocking: lancia come task asincrono, il backend è già pronto per le request
    asyncio.create_task(_startup_sync_recent_plays())

    yield

    scheduler.shutdown(wait=False)
    logger.info("APScheduler arrestato")
    await close_redis()
    logger.info("Redis chiuso")


class RateLimitHeaderMiddleware(BaseHTTPMiddleware):
    """Inject X-RateLimit-Usage and X-RateLimit-Reset headers into every /api/ response.

    Reads current usage from Redis via SpotifyClient.get_window_usage().
    Caches result for 2s to avoid Redis round-trip on every response.
    """

    _cached_usage: tuple[int, float] = (0, 0.0)
    _cached_at: float = 0.0
    _CACHE_TTL: float = 2.0

    async def dispatch(self, request, call_next):
        response = await call_next(request)
        if request.url.path.startswith("/api/"):
            import time as _time

            now = _time.monotonic()
            if now - self._cached_at > self._CACHE_TTL:
                current, reset = await SpotifyClient.get_window_usage()
                RateLimitHeaderMiddleware._cached_usage = (current, reset)
                RateLimitHeaderMiddleware._cached_at = now
            else:
                current, reset = self._cached_usage
            max_calls = SpotifyClient._MAX_CALLS_PER_WINDOW
            response.headers["X-RateLimit-Usage"] = f"{current}/{max_calls}"
            response.headers["X-RateLimit-Reset"] = str(reset)
        return response


app = FastAPI(
    title="Wrap",
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
    expose_headers=["X-RateLimit-Usage", "X-RateLimit-Reset"],
)

# Rate limit usage header (runs inside CORS — added after CORSMiddleware)
app.add_middleware(RateLimitHeaderMiddleware)

# Request context (request_id + user_id in logs — runs early, after rate limit headers)
app.add_middleware(RequestContextMiddleware)

# Per-user quota (runs after request context so user_id is available from cookie)
app.add_middleware(UserQuotaMiddleware)

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
app.include_router(privacy.router)
app.include_router(admin.router)


@app.get("/health")
async def health():
    """Health check con verifica database e Redis."""
    checks = {"database": "ok", "redis": "ok"}
    try:
        from sqlalchemy import text

        async with async_session() as session:
            await session.execute(text("SELECT 1"))
    except Exception as e:
        checks["database"] = "error"
        logger.error(f"Health check database failed: {e}")

    if not await redis_ping():
        checks["redis"] = "error"

    status = "ok" if all(v == "ok" for v in checks.values()) else "degraded"
    status_code = 200 if status == "ok" else 503
    return JSONResponse(
        content={"status": status, "checks": checks}, status_code=status_code
    )


@app.get("/health/detailed")
async def health_detailed(request: Request):
    """Diagnostica dettagliata — solo admin."""
    from datetime import datetime, timedelta, timezone

    from sqlalchemy import func, select, text

    from app.dependencies import get_session_user_id
    from app.models.user import SpotifyToken, User

    user_id = get_session_user_id(request)
    if not user_id:
        return JSONResponse(status_code=403, content={"detail": "Accesso negato"})

    async with async_session() as session:
        user = (
            await session.execute(select(User).where(User.id == user_id))
        ).scalar_one_or_none()
        if not user or not user.is_admin:
            return JSONResponse(status_code=403, content={"detail": "Accesso negato"})

    # DB ping
    checks: dict[str, str] = {"database": "ok", "redis": "ok"}
    try:
        async with async_session() as session:
            await session.execute(text("SELECT 1"))
    except Exception as e:
        checks["database"] = f"error: {e}"

    # Redis ping
    if not await redis_ping():
        checks["redis"] = "error"

    # Active users (token updated in last 24h)
    try:
        async with async_session() as session:
            cutoff = datetime.now(timezone.utc) - timedelta(hours=24)
            result = await session.execute(
                select(func.count())
                .select_from(SpotifyToken)
                .where(SpotifyToken.updated_at > cutoff)
            )
            active_users = result.scalar() or 0

            total_result = await session.execute(select(func.count()).select_from(User))
            total_users = total_result.scalar() or 0
    except Exception:
        active_users = -1
        total_users = -1

    # APScheduler jobs
    jobs_info = []
    for job in scheduler.get_jobs():
        jobs_info.append(
            {
                "id": job.id,
                "name": job.name,
                "next_run": str(job.next_run_time) if job.next_run_time else None,
            }
        )

    # Spotify reachability (lightweight check)
    spotify_reachable = False
    try:
        import httpx

        async with httpx.AsyncClient(timeout=5.0) as client:
            await client.get("https://api.spotify.com/v1/")
            spotify_reachable = True
    except Exception:
        spotify_reachable = False

    # Rate limit window
    current_calls, window_reset = await SpotifyClient.get_window_usage()
    max_calls = SpotifyClient._MAX_CALLS_PER_WINDOW

    status = "ok" if all(v == "ok" for v in checks.values()) else "degraded"
    return {
        "status": status,
        "checks": checks,
        "users": {"total": total_users, "active_24h": active_users},
        "scheduler": {"jobs": jobs_info},
        "spotify": {"reachable": spotify_reachable},
        "rate_limit": {
            "calls_in_window": current_calls,
            "max_calls": max_calls,
            "window_reset_seconds": window_reset,
        },
    }


@app.middleware("http")
async def api_version_redirect(request, call_next):
    """Redirect vecchi path /api/* a /api/v1/* per backward compatibility (308)."""
    path = request.url.path
    # Only redirect /api/ paths that aren't already /api/v1/
    if path.startswith("/api/") and not path.startswith("/api/v1/"):
        new_path = "/api/v1" + path[4:]  # /api/foo → /api/v1/foo
        query = str(request.url.query)
        url = new_path + ("?" + query if query else "")
        return RedirectResponse(url=url, status_code=308)
    return await call_next(request)
