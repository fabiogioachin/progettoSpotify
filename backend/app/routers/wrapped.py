"""Router per il Wrapped — recap delle statistiche di ascolto."""

import asyncio
import logging

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import require_auth
from app.services.artist_network import build_artist_network
from app.services.audio_analyzer import compute_profile
from app.services.spotify_client import SpotifyClient
from app.services.taste_evolution import compute_taste_evolution
from app.services.temporal_patterns import compute_temporal_patterns
from app.utils.rate_limiter import SpotifyAuthError, retry_with_backoff

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/wrapped", tags=["wrapped"])


async def _safe_fetch(label: str, coro):
    """Esegue una coroutine e restituisce (label, result) o (label, None) in caso di errore."""
    try:
        return label, await coro
    except SpotifyAuthError:
        raise
    except Exception as exc:
        logger.warning("Wrapped %s failed: %s", label, exc)
        return label, None


@router.get("")
async def get_wrapped(
    request: Request,
    user_id: int = Depends(require_auth),
    db: AsyncSession = Depends(get_db),
    time_range: str = Query("medium_term"),
):
    """Recap completo delle statistiche di ascolto dell'utente."""
    if time_range not in ("short_term", "medium_term", "long_term"):
        time_range = "medium_term"

    client = SpotifyClient(db, user_id)
    try:
        results = dict(
            await asyncio.gather(
                _safe_fetch(
                    "temporal",
                    compute_temporal_patterns(client, db=db, user_id=user_id),
                ),
                _safe_fetch("evolution", compute_taste_evolution(client)),
                _safe_fetch("profile", compute_profile(db, client, time_range)),
                _safe_fetch(
                    "top_tracks",
                    retry_with_backoff(
                        client.get_top_tracks, time_range=time_range, limit=10
                    ),
                ),
                _safe_fetch("network", build_artist_network(client)),
            )
        )
    except SpotifyAuthError:
        raise HTTPException(status_code=401, detail="Sessione scaduta")
    except Exception as exc:
        logger.exception("Errore wrapped: %s", exc)
        raise HTTPException(status_code=500, detail="Errore nel calcolo Wrapped")
    finally:
        await client.close()

    # Compute available slides based on data presence
    available = ["intro"]  # always shown

    top_tracks_data = results.get("top_tracks")
    if isinstance(top_tracks_data, dict):
        top_tracks_items = top_tracks_data.get("items", [])
    else:
        top_tracks_items = top_tracks_data if isinstance(top_tracks_data, list) else []

    if top_tracks_items:
        available.append("top_tracks")

    temporal = results.get("temporal")
    if temporal and temporal.get("total_plays", 0) > 0:
        available.extend(["listening_habits", "peak_hours"])

    evolution = results.get("evolution")
    if evolution:
        artists = evolution.get("artists", {})
        if artists.get("loyal") or artists.get("rising"):
            available.append("artist_evolution")

    profile = results.get("profile")
    if profile and profile.get("genres"):
        available.append("top_genres")

    network = results.get("network")
    if network and network.get("metrics", {}).get("cluster_count", 0) > 0:
        available.append("artist_network")

    available.append("outro")  # always shown

    return {
        "temporal": results.get("temporal"),
        "evolution": results.get("evolution"),
        "profile": results.get("profile"),
        "top_tracks": top_tracks_items,
        "network": results.get("network"),
        "available_slides": available,
    }
