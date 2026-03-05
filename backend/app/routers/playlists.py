"""Router per playlist e confronto."""

import re

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import require_auth
from app.services.audio_analyzer import get_or_fetch_features
from app.schemas import (
    PlaylistListResponse,
    PlaylistComparisonResponse,
    PlaylistTracksResponse,
)
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


@router.get("/{playlist_id}/tracks", response_model=PlaylistTracksResponse)
async def get_playlist_tracks(
    playlist_id: str,
    request: Request,
    limit: int = Query(default=100, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    user_id: int = Depends(require_auth),
    db: AsyncSession = Depends(get_db),
):
    """Brani di una singola playlist."""
    if not re.match(r"^[a-zA-Z0-9]{1,50}$", playlist_id):
        raise HTTPException(status_code=400, detail="Formato playlist ID non valido")

    client = SpotifyClient(db, user_id)
    try:
        data = await retry_with_backoff(
            client.get_playlist_tracks, playlist_id, limit=limit, offset=offset
        )
    except SpotifyAuthError:
        raise HTTPException(status_code=401, detail="Sessione scaduta")
    finally:
        await client.close()

    tracks = []
    for item in data.get("items", []):
        t = item.get("track")
        if not t or not t.get("id"):
            continue
        tracks.append({
            "id": t["id"],
            "name": t.get("name", ""),
            "artist": t["artists"][0]["name"] if t.get("artists") else "",
            "album": t.get("album", {}).get("name", ""),
            "album_image": (t.get("album", {}).get("images", [{}])[0].get("url")
                            if t.get("album", {}).get("images") else None),
            "popularity": t.get("popularity", 0),
            "duration_ms": t.get("duration_ms", 0),
        })

    return {
        "tracks": tracks,
        "total": data.get("total", len(tracks)),
        "playlist_id": playlist_id,
    }


@router.get("/compare", response_model=PlaylistComparisonResponse)
async def compare_playlists(
    request: Request,
    ids: str = Query(default="", min_length=1),
    user_id: int = Depends(require_auth),
    db: AsyncSession = Depends(get_db),
):
    """Confronta 2-4 playlist con brani, popolarita', generi e audio features."""
    playlist_ids = [pid.strip() for pid in ids.split(",") if pid.strip()]

    if len(playlist_ids) < 2 or len(playlist_ids) > 4:
        raise HTTPException(status_code=400, detail="Seleziona da 2 a 4 playlist")

    # Validazione formato Spotify playlist ID
    for pid in playlist_ids:
        if not re.match(r"^[a-zA-Z0-9]{1,50}$", pid):
            raise HTTPException(status_code=400, detail="Formato playlist ID non valido")

    client = SpotifyClient(db, user_id)
    results = []

    try:
        for pid in playlist_ids:
            # Recupera tracce della playlist (con metadati)
            all_tracks_data = []
            all_track_ids = []
            offset = 0
            while True:
                data = await retry_with_backoff(
                    client.get_playlist_tracks, pid, limit=100, offset=offset
                )
                items = data.get("items", [])
                for item in items:
                    t = item.get("track")
                    if not t or not t.get("id"):
                        continue
                    all_track_ids.append(t["id"])
                    all_tracks_data.append(t)
                if len(items) < 100 or len(all_track_ids) >= 200:
                    break
                offset += 100

            # Top tracks (i 10 piu' popolari)
            top_tracks = sorted(all_tracks_data, key=lambda t: t.get("popularity", 0), reverse=True)[:10]
            top_tracks_list = []
            for t in top_tracks:
                top_tracks_list.append({
                    "id": t["id"],
                    "name": t.get("name", ""),
                    "artist": t["artists"][0]["name"] if t.get("artists") else "",
                    "album": t.get("album", {}).get("name", ""),
                    "album_image": (t.get("album", {}).get("images", [{}])[0].get("url")
                                    if t.get("album", {}).get("images") else None),
                    "popularity": t.get("popularity", 0),
                    "duration_ms": t.get("duration_ms", 0),
                })

            # Popularity stats
            pops = [t.get("popularity", 0) for t in all_tracks_data]
            popularity_stats = {}
            if pops:
                popularity_stats = {
                    "avg": round(sum(pops) / len(pops), 1),
                    "min": min(pops),
                    "max": max(pops),
                }

            # Genre distribution (dagli artisti dei brani)
            artist_ids = set()
            for t in all_tracks_data:
                for a in t.get("artists", []):
                    if a.get("id"):
                        artist_ids.add(a["id"])

            genre_distribution = {}
            if artist_ids:
                from collections import Counter
                genre_counter = Counter()
                artist_list = list(artist_ids)
                for i in range(0, len(artist_list), 50):
                    batch = artist_list[i:i + 50]
                    try:
                        resp = await retry_with_backoff(client.get_artists, batch)
                        for artist in resp.get("artists", []):
                            if artist and artist.get("genres"):
                                genre_counter.update(artist["genres"])
                    except Exception:
                        pass
                total_g = sum(genre_counter.values())
                if total_g:
                    genre_distribution = {
                        g: round(c / total_g * 100, 1)
                        for g, c in genre_counter.most_common(8)
                    }

            # Audio features
            features = await get_or_fetch_features(db, client, all_track_ids[:200])

            averages = {}
            if features:
                keys = ["danceability", "energy", "valence", "acousticness",
                        "instrumentalness", "liveness", "speechiness", "tempo"]
                for key in keys:
                    vals = [f[key] for f in features.values() if f.get(key) is not None]
                    averages[key] = round(sum(vals) / len(vals), 3) if vals else 0

            results.append({
                "playlist_id": pid,
                "track_count": len(all_track_ids),
                "analyzed_count": len(features),
                "averages": averages,
                "top_tracks": top_tracks_list,
                "popularity_stats": popularity_stats,
                "genre_distribution": genre_distribution,
            })
    except SpotifyAuthError:
        raise HTTPException(status_code=401, detail="Sessione scaduta")
    finally:
        await client.close()

    return {"comparisons": results}
