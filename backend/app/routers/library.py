"""Router per dati libreria Spotify dell'utente."""

import logging
from collections import defaultdict
from datetime import timezone
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import require_auth
from app.models.listening_history import RecentPlay
from app.schemas import TopTracksResponse
from app.services.audio_analyzer import get_or_fetch_features
from app.services.popularity_cache import read_popularity_cache
from app.services.spotify_client import SpotifyClient
from app.services.temporal_patterns import get_first_play_date
from app.utils.rate_limiter import (
    RateLimitError,
    SpotifyAuthError,
    SpotifyServerError,
    retry_with_backoff,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/library", tags=["library"])


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


@router.get("/recent-summary")
async def get_recent_summary(
    user_id: int = Depends(require_auth),
    db: AsyncSession = Depends(get_db),
):
    """Vista aggregata degli ascolti per brano (senza duplicati).

    Aggrega recent_plays per track_spotify_id con play_count,
    consecutive_days, last_played_at, first_played_at.
    Restituisce anche first_play_date (data del primo ascolto registrato).
    """
    result = await db.execute(
        select(RecentPlay)
        .where(RecentPlay.user_id == user_id)
        .order_by(RecentPlay.played_at.desc())
    )
    rows = result.scalars().all()

    if not rows:
        return {"tracks": [], "first_play_date": None, "total_plays": 0}

    # Raggruppa per brano in Python (dataset piccolo, max ~10K righe)
    tracks_map: dict[str, list] = defaultdict(list)
    for row in rows:
        dt = row.played_at
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        tracks_map[row.track_spotify_id].append(
            {
                "track_name": row.track_name,
                "artist_name": row.artist_name,
                "datetime": dt,
            }
        )

    tracks_out = []

    for track_id, plays in tracks_map.items():
        plays.sort(key=lambda x: x["datetime"], reverse=True)
        last_played = plays[0]["datetime"]
        first_played = plays[-1]["datetime"]

        # Giorni consecutivi più recenti in cui il brano è stato ascoltato
        unique_dates = sorted(
            set(p["datetime"].date() for p in plays), reverse=True
        )
        consecutive = 1 if unique_dates else 0
        for i in range(1, len(unique_dates)):
            if (unique_dates[i - 1] - unique_dates[i]).days == 1:
                consecutive += 1
            else:
                break

        tracks_out.append(
            {
                "track_spotify_id": track_id,
                "track_name": plays[0]["track_name"],
                "artist_name": plays[0]["artist_name"],
                "play_count": len(plays),
                "consecutive_days": consecutive,
                "last_played_at": last_played.isoformat(),
                "first_played_at": first_played.isoformat(),
            }
        )

    # Ordina per ultimo ascolto (più recente prima)
    tracks_out.sort(key=lambda x: x["last_played_at"], reverse=True)

    first_play_date = await get_first_play_date(db, user_id)

    return {
        "tracks": tracks_out,
        "first_play_date": first_play_date,
        "total_plays": len(rows),
    }
