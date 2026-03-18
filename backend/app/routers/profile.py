"""Router per il profilo utente con metriche aggregate."""

import asyncio
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
from app.utils.rate_limiter import (
    RateLimitError,
    SpotifyAuthError,
    SpotifyServerError,
    retry_with_backoff,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/profile", tags=["profile"])


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
        results = dict(
            await asyncio.gather(
                _safe_fetch("metrics", compute_profile_metrics(db, client, user_id)),
                _safe_fetch("user", retry_with_backoff(client.get_me)),
                _safe_fetch("daily", get_recent_daily_stats(db, user_id, days=30)),
                _safe_fetch("taste_map", compute_taste_map(db, client, user_id)),
            )
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

    metrics = results.get("metrics")
    user_data = results.get("user")
    daily_stats = results.get("daily") or []

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

    taste_map = results.get("taste_map")

    return {
        "user": user_info,
        "metrics": metrics,
        "personality": personality,
        "daily_stats": daily_stats,
        "has_metrics": existing_metrics is not None or metrics is not None,
        "taste_map": taste_map,
    }
