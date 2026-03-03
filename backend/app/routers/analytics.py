"""Router per analisi e insight musicali."""

from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import require_auth
from app.services.audio_analyzer import (
    compute_profile,
    compute_trends,
    get_historical_snapshots,
    save_snapshot,
)
from app.services.discovery import discover
from app.services.spotify_client import SpotifyClient
from app.utils.rate_limiter import SpotifyAuthError

router = APIRouter(prefix="/api/analytics", tags=["analytics"])


@router.get("/features")
async def get_audio_features_profile(
    request: Request,
    time_range: Literal["short_term", "medium_term", "long_term"] = Query(default="medium_term"),
    user_id: int = Depends(require_auth),
    db: AsyncSession = Depends(get_db),
):
    """Profilo audio features dell'utente."""
    client = SpotifyClient(db, user_id)

    try:
        profile = await compute_profile(db, client, time_range)
        # Salva snapshot
        await save_snapshot(db, user_id, time_range, profile)
    except SpotifyAuthError:
        raise HTTPException(status_code=401, detail="Sessione scaduta")
    finally:
        await client.close()

    return profile


@router.get("/trends")
async def get_trends(
    request: Request,
    user_id: int = Depends(require_auth),
    db: AsyncSession = Depends(get_db),
):
    """Trend audio features per tutti i periodi."""
    client = SpotifyClient(db, user_id)

    try:
        trends = await compute_trends(db, client, user_id)
        historical = await get_historical_snapshots(db, user_id)
    except SpotifyAuthError:
        raise HTTPException(status_code=401, detail="Sessione scaduta")
    finally:
        await client.close()

    return {"current": trends, "historical": historical}


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
    except SpotifyAuthError:
        raise HTTPException(status_code=401, detail="Sessione scaduta")
    finally:
        await client.close()

    return results
