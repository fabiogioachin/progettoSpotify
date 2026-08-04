"""Router per dati libreria Spotify dell'utente."""

import asyncio
import logging
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import require_auth
from app.models.listening_history import RecentPlay
from app.schemas import TopPlayedResponse, TopTracksResponse
from app.services.audio_analyzer import get_or_fetch_features
from app.services.popularity_cache import read_popularity_cache
from app.services.spotify_client import SpotifyClient
from app.services.temporal_patterns import get_first_play_date
from app.services.track_metadata import fetch_missing_images, read_track_images
from app.utils.rate_limiter import (
    RateLimitError,
    SpotifyAuthError,
    SpotifyServerError,
    retry_with_backoff,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/library", tags=["library"])

# "all" e' None, non un numero: la classifica sugli ascolti veri non ha motivo di
# fermarsi a una scadenza, e un tetto silenzioso taglierebbe lo storico piu' vecchio.
_PLAYED_DAYS_MAP: dict[str, int | None] = {
    "7d": 7,
    "30d": 30,
    "90d": 90,
    "1y": 365,
    "all": None,
}


def _as_utc_iso(dt: datetime | None) -> str | None:
    """Le date lette dal DB possono arrivare senza fuso: qui valgono sempre UTC."""
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.isoformat()


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


@router.get("/top-played", response_model=TopPlayedResponse)
async def get_top_played(
    range: Literal["7d", "30d", "90d", "1y", "all"] = Query(default="30d"),
    limit: int = Query(default=50, ge=1, le=100),
    user_id: int = Depends(require_auth),
    db: AsyncSession = Depends(get_db),
):
    """Classifica dei brani costruita sugli ascolti registrati, non su Spotify.

    Conta quante volte ogni brano compare in recent_plays nel periodo scelto.
    E' una classifica di ascolti veri: due brani a pari merito si ordinano per
    tempo totale ascoltato e poi per ultimo ascolto. Nessuna chiamata a Spotify,
    si legge solo il database.
    """
    days = _PLAYED_DAYS_MAP[range]
    filters = [RecentPlay.user_id == user_id]
    if days is not None:
        filters.append(
            RecentPlay.played_at >= datetime.now(timezone.utc) - timedelta(days=days)
        )

    play_count = func.count().label("play_count")
    result = await db.execute(
        select(
            RecentPlay.track_spotify_id,
            func.max(RecentPlay.track_name).label("track_name"),
            func.max(RecentPlay.artist_name).label("artist_name"),
            func.max(RecentPlay.artist_spotify_id).label("artist_spotify_id"),
            func.max(RecentPlay.duration_ms).label("duration_ms"),
            func.coalesce(func.sum(RecentPlay.duration_ms), 0).label("total_ms"),
            func.min(RecentPlay.played_at).label("first_played_at"),
            func.max(RecentPlay.played_at).label("last_played_at"),
            play_count,
        )
        .where(*filters)
        .group_by(RecentPlay.track_spotify_id)
        .order_by(play_count.desc(), desc("total_ms"), desc("last_played_at"))
        .limit(limit)
    )
    rows = result.all()

    tracks = [
        {
            "id": row.track_spotify_id,
            "name": row.track_name,
            "artist": row.artist_name,
            "artist_id": row.artist_spotify_id,
            "album_image": None,
            "preview_url": None,
            "popularity": None,
            "duration_ms": row.duration_ms or 0,
            "play_count": row.play_count,
            "total_ms": row.total_ms or 0,
            "first_played_at": _as_utc_iso(row.first_played_at),
            "last_played_at": _as_utc_iso(row.last_played_at),
        }
        for row in rows
    ]

    # Popularity, copertine e audio features: solo cache DB, zero chiamate a Spotify.
    await read_popularity_cache(tracks, db)
    track_ids = [t["id"] for t in tracks]
    features_map = await get_or_fetch_features(db, track_ids)
    images_map = await read_track_images(db, track_ids)
    for track in tracks:
        feat = features_map.get(track["id"])
        if feat:
            track["features"] = feat
        meta = images_map.get(track["id"])
        if meta:
            track["album_image"] = meta["album_image"]
            track["preview_url"] = meta["preview_url"]

    # Le copertine che mancano si recuperano dopo, una chiamata per brano: la
    # risposta parte subito e la pagina le ritrova quando ricarica.
    missing = [t["id"] for t in tracks if t["id"] not in images_map]
    if missing:
        asyncio.create_task(fetch_missing_images(user_id, missing))

    # Quanti brani distinti e quanti ascolti totali ci sono nel periodo: servono
    # a dire "50 brani su 312" invece di lasciar credere che la lista sia tutto.
    totals = (
        await db.execute(
            select(
                func.count(func.distinct(RecentPlay.track_spotify_id)),
                func.count(),
            ).where(*filters)
        )
    ).one()

    return {
        "tracks": tracks,
        "total": totals[0],
        "range": range,
        "total_plays": totals[1],
        "images_pending": len(missing),
        "first_play_date": await get_first_play_date(db, user_id),
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
