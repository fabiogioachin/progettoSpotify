"""Router per playlist e confronto."""

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import require_auth
from app.routers.library import _get_or_fetch_features
from app.schemas import PlaylistListResponse, PlaylistComparisonResponse
from app.services.spotify_client import SpotifyClient
from app.utils.rate_limiter import SpotifyAuthError, retry_with_backoff

router = APIRouter(prefix="/api/playlists", tags=["playlists"])


@router.get("", response_model=PlaylistListResponse)
async def get_playlists(
    request: Request,
    limit: int = Query(default=50, ge=1, le=50),
    offset: int = Query(default=0, ge=0),
    user_id: int = Depends(require_auth),
    db: AsyncSession = Depends(get_db),
):
    """Lista playlist dell'utente."""
    client = SpotifyClient(db, user_id)

    try:
        data = await retry_with_backoff(client.get_playlists, limit=limit, offset=offset)
    except SpotifyAuthError:
        raise HTTPException(status_code=401, detail="Sessione scaduta")
    finally:
        await client.close()

    playlists = []
    for item in data.get("items", []):
        if not item:
            continue
        playlists.append({
            "id": item["id"],
            "name": item.get("name", ""),
            "description": item.get("description", ""),
            "image": (item.get("images", [{}])[0].get("url") if item.get("images") else None),
            "track_count": item.get("tracks", {}).get("total", 0),
            "owner": item.get("owner", {}).get("display_name", ""),
        })

    return {"playlists": playlists, "total": data.get("total", 0)}


@router.get("/compare", response_model=PlaylistComparisonResponse)
async def compare_playlists(
    request: Request,
    ids: str = Query(default="", min_length=1),
    user_id: int = Depends(require_auth),
    db: AsyncSession = Depends(get_db),
):
    """Confronta audio features di 2-4 playlist."""
    playlist_ids = [pid.strip() for pid in ids.split(",") if pid.strip()]

    if len(playlist_ids) < 2 or len(playlist_ids) > 4:
        raise HTTPException(status_code=400, detail="Seleziona da 2 a 4 playlist")

    client = SpotifyClient(db, user_id)
    results = []

    try:
        for pid in playlist_ids:
            # Recupera tracce della playlist
            all_tracks = []
            offset = 0
            while True:
                data = await retry_with_backoff(
                    client.get_playlist_tracks, pid, limit=100, offset=offset
                )
                items = data.get("items", [])
                for item in items:
                    t = item.get("track")
                    if t and t.get("id"):
                        all_tracks.append(t["id"])
                if len(items) < 100 or len(all_tracks) >= 200:
                    break
                offset += 100

            # Audio features
            features = await _get_or_fetch_features(db, client, all_tracks[:200])

            # Calcola medie
            if features:
                keys = ["danceability", "energy", "valence", "acousticness",
                        "instrumentalness", "liveness", "speechiness", "tempo"]
                averages = {}
                for key in keys:
                    vals = [f[key] for f in features.values() if f.get(key) is not None]
                    averages[key] = round(sum(vals) / len(vals), 3) if vals else 0

                results.append({
                    "playlist_id": pid,
                    "track_count": len(all_tracks),
                    "analyzed_count": len(features),
                    "averages": averages,
                })
            else:
                results.append({
                    "playlist_id": pid,
                    "track_count": len(all_tracks),
                    "analyzed_count": 0,
                    "averages": {},
                })
    except SpotifyAuthError:
        raise HTTPException(status_code=401, detail="Sessione scaduta")
    finally:
        await client.close()

    return {"comparisons": results}
