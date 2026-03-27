"""Router per il profilo utente con metriche aggregate."""

import logging

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import require_auth
from app.models.listening_history import UserProfileMetrics
from app.services.personality import compute_archetype
from app.services.profile_metrics import compute_profile_metrics, get_recent_daily_stats
from app.services.spotify_client import SpotifyClient
from app.services.taste_map import compute_taste_map
from app.utils.json_utils import sanitize_nans
from app.utils.rate_limiter import (
    RateLimitError,
    SpotifyAuthError,
    SpotifyServerError,
    retry_with_backoff,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/profile", tags=["profile"])


async def _safe_fetch(label: str, coro):
    try:
        return label, await coro
    except SpotifyAuthError:
        raise
    except Exception as exc:
        logger.warning("Profile %s failed: %s", label, exc)
        return label, None


@router.get("")
async def get_profile(
    request: Request,
    user_id: int = Depends(require_auth),
    db: AsyncSession = Depends(get_db),
):
    """Profilo utente con metriche aggregate, personalità e statistiche giornaliere."""
    client = SpotifyClient(db, user_id)
    try:
        # SQLAlchemy async sessions do NOT support concurrent operations.
        # compute_profile_metrics and compute_taste_map both use db for reads,
        # so we cannot run them in the same asyncio.gather. Strategy:
        # 1. Fetch user profile (Spotify-only, no direct db reads) concurrently
        #    with metrics (heaviest, does Spotify + db reads sequentially)
        # 2. Then taste_map (Spotify + pure compute) — sequential after metrics
        # 3. Then daily stats (db-only read) — sequential after taste_map
        _, metrics_result = await _safe_fetch(
            "metrics", compute_profile_metrics(db, client, user_id)
        )
        _, user_result = await _safe_fetch("user", retry_with_backoff(client.get_me))
        _, taste_map_result = await _safe_fetch(
            "taste_map", compute_taste_map(db, client, user_id)
        )
    except (SpotifyAuthError, RateLimitError, SpotifyServerError):
        raise  # Handled by global exception handlers in main.py
    except Exception as exc:
        logger.exception("Errore profilo: %s", exc)
        raise HTTPException(
            status_code=500, detail="Errore nel caricamento del profilo"
        )
    finally:
        await client.close()

    # Daily stats: sequential DB read to avoid concurrent session use
    try:
        daily_stats = await get_recent_daily_stats(db, user_id, days=30) or []
    except Exception as exc:
        logger.warning("Profile daily stats failed: %s", exc)
        daily_stats = []

    metrics = metrics_result
    user_data = user_result

    # Personality archetype
    personality = compute_archetype(metrics) if metrics else None

    # Check if metrics exist in DB (for has_metrics flag)
    existing_metrics = (
        await db.execute(
            select(UserProfileMetrics).where(UserProfileMetrics.user_id == user_id)
        )
    ).scalar_one_or_none()

    # User info
    user_info = None
    if user_data:
        images = user_data.get("images", [])
        user_info = {
            "display_name": user_data.get("display_name", ""),
            "avatar_url": images[0]["url"] if images else None,
            "country": user_data.get("country", ""),
        }

    taste_map = taste_map_result

    return sanitize_nans(
        {
            "user": user_info,
            "metrics": metrics,
            "personality": personality,
            "daily_stats": daily_stats,
            "has_metrics": existing_metrics is not None or metrics is not None,
            "taste_map": taste_map,
        }
    )
