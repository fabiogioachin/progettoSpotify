"""Router per dati libreria Spotify dell'utente."""

import logging
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import require_auth
from app.schemas import TopTracksResponse
from app.services.audio_analyzer import get_or_fetch_features
from app.services.popularity_cache import read_popularity_cache
from app.services.spotify_client import SpotifyClient
from app.utils.rate_limiter import (
    RateLimitError,
    SpotifyAuthError,
    SpotifyServerError,
    retry_with_backoff,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/library", tags=["library"])


@router.get("/top", response_model=TopTracksResponse)
async def get_top_tracks(
    request: Request,
    time_range: Literal["short_term", "medium_term", "long_term"] = Query(
        default="medium_term"
    ),
    limit: int = Query(default=50, ge=1, le=50),
    user_id: int = Depends(require_auth),
    db: AsyncSession = Depends(get_db),
):
    """Top brani dell'utente per periodo."""
    client = SpotifyClient(db, user_id)

    try:
        data = await retry_with_backoff(
            client.get_top_tracks, time_range=time_range, limit=50
        )

        tracks = []
        track_ids = []
        for item in data.get("items", []):
            track_ids.append(item["id"])
            tracks.append(
                {
                    "id": item["id"],
                    "name": item["name"],
                    "artist": item["artists"][0]["name"]
                    if item.get("artists")
                    else "Sconosciuto",
                    "artist_id": item["artists"][0]["id"]
                    if item.get("artists")
                    else None,
                    "album": item.get("album", {}).get("name", ""),
                    "album_image": (
                        item.get("album", {}).get("images", [{}])[0].get("url")
                        if item.get("album", {}).get("images")
                        else None
                    ),
                    "popularity": item.get("popularity", 0),
                    "duration_ms": item.get("duration_ms", 0),
                    "preview_url": item.get("preview_url"),
                }
            )

        # Popularity: leggi dalla cache DB (zero API calls)
        await read_popularity_cache(tracks, db)

        # Recupera audio features (solo cache DB — API deprecata)
        features_map = await get_or_fetch_features(db, track_ids)

        for track in tracks:
            feat = features_map.get(track["id"])
            if feat:
                track["features"] = feat

    except (SpotifyAuthError, RateLimitError, SpotifyServerError):
        raise  # Handled by global exception handlers in main.py
    except Exception as exc:
        logger.error("Errore nel caricamento top tracks: %s", exc)
        raise HTTPException(status_code=500, detail="Errore nel caricamento dei brani")
    finally:
        await client.close()

    # Slice to requested limit (always fetch 50 for cache alignment)
    tracks = tracks[:limit]

    return {
        "tracks": tracks,
        "total": data.get("total", len(tracks)),
        "time_range": time_range,
    }
