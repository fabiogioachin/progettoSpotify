"""Router per analisi e insight musicali."""

import logging
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import require_auth
from app.services.audio_analyzer import compute_trends
from app.services.data_bundle import RequestDataBundle
from app.services.discovery import discover
from app.services.spotify_client import SpotifyClient
from app.utils.json_utils import sanitize_nans
from app.utils.rate_limiter import RateLimitError, SpotifyAuthError, SpotifyServerError

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/analytics", tags=["analytics"])


@router.get("/trends")
async def get_trends(
    request: Request,
    user_id: int = Depends(require_auth),
    db: AsyncSession = Depends(get_db),
):
    """Trend audio features per tutti i periodi."""
    client = SpotifyClient(db, user_id)
    bundle = RequestDataBundle(client)

    try:
        await bundle.prefetch(artists=False, tracks=True)
        trends = await compute_trends(db, client, user_id, bundle=bundle)
    except (SpotifyAuthError, RateLimitError, SpotifyServerError):
        raise  # Handled by global exception handlers in main.py
    except Exception as exc:
        logger.error("Errore compute_trends: %s", exc)
        raise HTTPException(status_code=500, detail="Errore nel calcolo dei trend")
    finally:
        await client.close()

    return sanitize_nans({"current": trends})


@router.get("/discovery")
async def get_discovery(
    request: Request,
    user_id: int = Depends(require_auth),
    db: AsyncSession = Depends(get_db),
):
    """Scopri nuovi brani e artisti."""
    client = SpotifyClient(db, user_id)

    try:
        results = await discover(db, client)
    except (SpotifyAuthError, RateLimitError, SpotifyServerError):
        raise  # Handled by global exception handlers in main.py
    except Exception as exc:
        logger.error("Errore discovery: %s", exc)
        raise HTTPException(status_code=500, detail="Errore nelle raccomandazioni")
    finally:
        await client.close()

    return sanitize_nans(results)
