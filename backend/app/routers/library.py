"""Router per dati libreria Spotify dell'utente."""

import logging
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import require_auth
from app.schemas import TopTracksResponse, RecentTracksResponse, SavedTracksResponse
from app.services.audio_analyzer import get_or_fetch_features
from app.services.spotify_client import SpotifyClient
from app.utils.rate_limiter import SpotifyAuthError, retry_with_backoff

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
            client.get_top_tracks, time_range=time_range, limit=limit
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

        # Recupera audio features (solo cache DB — API deprecata)
        features_map = await get_or_fetch_features(db, track_ids)

        for track in tracks:
            feat = features_map.get(track["id"])
            if feat:
                track["features"] = feat

    except SpotifyAuthError:
        raise HTTPException(status_code=401, detail="Sessione scaduta")
    except Exception as exc:
        logger.error("Errore nel caricamento top tracks: %s", exc)
        raise HTTPException(status_code=500, detail="Errore nel caricamento dei brani")
    finally:
        await client.close()

    return {
        "tracks": tracks,
        "total": data.get("total", len(tracks)),
        "time_range": time_range,
    }


@router.get("/recent", response_model=RecentTracksResponse)
async def get_recent_tracks(
    request: Request,
    limit: int = Query(default=50, ge=1, le=50),
    user_id: int = Depends(require_auth),
    db: AsyncSession = Depends(get_db),
):
    """Brani ascoltati di recente."""
    client = SpotifyClient(db, user_id)

    try:
        data = await retry_with_backoff(client.get_recently_played, limit=limit)
    except SpotifyAuthError:
        raise HTTPException(status_code=401, detail="Sessione scaduta")
    except Exception as exc:
        logger.error("Errore nel caricamento brani recenti: %s", exc)
        raise HTTPException(
            status_code=500, detail="Errore nel caricamento dei brani recenti"
        )
    finally:
        await client.close()

    tracks = []
    for item in data.get("items", []):
        t = item.get("track", {})
        tracks.append(
            {
                "id": t.get("id"),
                "name": t.get("name"),
                "artist": t["artists"][0]["name"]
                if t.get("artists")
                else "Sconosciuto",
                "album": t.get("album", {}).get("name", ""),
                "album_image": (
                    t.get("album", {}).get("images", [{}])[0].get("url")
                    if t.get("album", {}).get("images")
                    else None
                ),
                "played_at": item.get("played_at"),
            }
        )

    return {"tracks": tracks}


@router.get("/saved", response_model=SavedTracksResponse)
async def get_saved_tracks(
    request: Request,
    limit: int = Query(default=50, ge=1, le=50),
    offset: int = Query(default=0, ge=0),
    user_id: int = Depends(require_auth),
    db: AsyncSession = Depends(get_db),
):
    """Brani salvati nella libreria."""
    client = SpotifyClient(db, user_id)

    try:
        data = await retry_with_backoff(
            client.get_saved_tracks, limit=limit, offset=offset
        )
    except SpotifyAuthError:
        raise HTTPException(status_code=401, detail="Sessione scaduta")
    except Exception as exc:
        logger.error("Errore nel caricamento brani salvati: %s", exc)
        raise HTTPException(
            status_code=500, detail="Errore nel caricamento dei brani salvati"
        )
    finally:
        await client.close()

    tracks = []
    for item in data.get("items", []):
        t = item.get("track", {})
        if not t or not t.get("id"):
            continue
        tracks.append(
            {
                "id": t["id"],
                "name": t.get("name"),
                "artist": t["artists"][0]["name"]
                if t.get("artists")
                else "Sconosciuto",
                "artist_id": t["artists"][0]["id"] if t.get("artists") else None,
                "album": t.get("album", {}).get("name", ""),
                "album_image": (
                    t.get("album", {}).get("images", [{}])[0].get("url")
                    if t.get("album", {}).get("images")
                    else None
                ),
                "popularity": t.get("popularity", 0),
                "added_at": item.get("added_at"),
            }
        )

    return {"tracks": tracks, "total": data.get("total", 0), "offset": offset}
