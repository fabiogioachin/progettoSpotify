"""FastAPI application entry point."""

import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.responses import JSONResponse

from app.config import settings
from app.database import async_session, init_db
from app.routers import analytics, auth, export, library, playlists
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
    yield


app = FastAPI(
    title="Spotify Listening Intelligence",
    description="Dashboard di analisi musicale personale",
    version="1.0.0",
    lifespan=lifespan,
)

# Rate Limiter (prima di CORS per intercettare richieste eccessive)
app.add_middleware(APIRateLimiter, requests_per_minute=60)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_url],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routers
app.include_router(auth.router)
app.include_router(library.router)
app.include_router(playlists.router)
app.include_router(analytics.router)
app.include_router(export.router)


@app.get("/health")
async def health():
    """Health check con verifica database."""
    checks = {"database": "ok"}
    try:
        from sqlalchemy import text
        async with async_session() as session:
            await session.execute(text("SELECT 1"))
    except Exception as e:
        checks["database"] = f"error: {str(e)}"

    status = "ok" if all(v == "ok" for v in checks.values()) else "degraded"
    status_code = 200 if status == "ok" else 503
    return JSONResponse(content={"status": status, "checks": checks}, status_code=status_code)
