"""FastAPI application entry point."""

import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.responses import JSONResponse

from app.config import settings
from app.database import async_session, init_db
from app.routers import (
    analytics,
    artist_network,
    auth,
    export,
    historical,
    library,
    playlist_analytics,
    playlists,
    taste_evolution,
    temporal,
)
from app.utils.rate_limiter import APIRateLimiter

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Assicura che la directory data esista
    os.makedirs("data", exist_ok=True)
    await init_db()
    logger.info("Database inizializzato")
    if not settings.cookie_secure and not settings.frontend_url.startswith("http://127"):
        logger.warning("SECURITY: cookie_secure=False su ambiente non-localhost. Impostare COOKIE_SECURE=true in produzione.")
    yield


app = FastAPI(
    title="Spotify Listening Intelligence",
    description="Dashboard di analisi musicale personale",
    version="1.0.0",
    lifespan=lifespan,
)

# Rate Limiter (prima di CORS per intercettare richieste eccessive)
app.add_middleware(APIRateLimiter, requests_per_minute=120)

# CORS (restrict methods and headers to what the app actually uses)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_url],
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)

# Routers
app.include_router(auth.router)
app.include_router(library.router)
app.include_router(playlists.router)
app.include_router(analytics.router)
app.include_router(export.router)
app.include_router(taste_evolution.router)
app.include_router(temporal.router)
app.include_router(artist_network.router)
app.include_router(playlist_analytics.router)
app.include_router(historical.router)


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
    return JSONResponse(content={"status": status, "checks": checks}, status_code=status_code)
