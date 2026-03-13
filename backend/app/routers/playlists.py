"""Router per playlist e confronto."""

import asyncio
import logging
import re
from collections import Counter

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import require_auth
from app.services.audio_analyzer import get_or_fetch_features
from app.schemas import PlaylistListResponse, PlaylistComparisonResponse
from app.services.spotify_client import SpotifyClient
from app.utils.rate_limiter import (
    RateLimitError,
    SpotifyAuthError,
    SpotifyServerError,
    retry_with_backoff,
)

logger = logging.getLogger(__name__)

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
    except Exception as exc:
        logger.error("Errore nel caricamento playlist: %s", exc)
        raise HTTPException(status_code=500, detail="Errore nel caricamento delle playlist")
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
    """Confronta playlist con dati sempre disponibili + audio features opzionali."""
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
        # --- Phase 1: fetch tracks for all playlists (sequential, 2 calls per playlist) ---
        playlist_data_map: dict[str, dict] = {}  # pid → {name, tracks, track_ids}
        for pid in playlist_ids:
            all_tracks: list[dict] = []
            track_ids: list[str] = []
            playlist_name = ""
            try:
                playlist_data = await retry_with_backoff(
                    client.get, f"/playlists/{pid}"
                )
                playlist_name = playlist_data.get("name", "")

                offset = 0
                while True:
                    items_data = await retry_with_backoff(
                        client.get, f"/playlists/{pid}/items",
                        limit=50, offset=offset,
                    )
                    items = items_data.get("items", [])
                    for item in items:
                        t = item.get("item") or item.get("track")
                        if t and t.get("id"):
                            all_tracks.append(t)
                            track_ids.append(t["id"])
                    if not items_data.get("next") or len(items) < 50:
                        break
                    offset += 50
            except SpotifyAuthError:
                raise
            except Exception:
                logger.warning("Failed to fetch playlist %s", pid)

            logger.info("Playlist %s (%s): %d tracks fetched", pid, playlist_name, len(all_tracks))
            playlist_data_map[pid] = {
                "name": playlist_name,
                "tracks": all_tracks,
                "track_ids": track_ids,
            }

        # --- Phase 2: collect all unique artist IDs across ALL playlists, fetch genres once ---
        global_artist_ids: set[str] = set()
        for pdata in playlist_data_map.values():
            for t in pdata["tracks"]:
                for a in t.get("artists", []):
                    if a.get("id"):
                        global_artist_ids.add(a["id"])

        # Fetch genres for unique artists (deduplicated, single pass)
        artist_genres_cache: dict[str, list[str]] = {}
        artist_list = list(global_artist_ids)[:20]  # global cap across all playlists
        sem_artists = asyncio.Semaphore(2)

        async def _fetch_artist_genres(aid: str) -> tuple[str, list[str]]:
            async with sem_artists:
                try:
                    artist = await retry_with_backoff(client.get_artist, aid)
                    return aid, artist.get("genres", [])
                except SpotifyAuthError:
                    raise
                except Exception:
                    return aid, []

        genre_results = await asyncio.gather(
            *[_fetch_artist_genres(aid) for aid in artist_list],
            return_exceptions=True,
        )
        for gr in genre_results:
            if isinstance(gr, tuple):
                artist_genres_cache[gr[0]] = gr[1]

        # --- Phase 3: build results per playlist using cached data ---
        for pid in playlist_ids:
            pdata = playlist_data_map[pid]
            all_tracks = pdata["tracks"]
            track_ids = pdata["track_ids"]

            # Popularity stats
            popularities = [t.get("popularity", 0) for t in all_tracks]
            if popularities:
                popularity_stats = {
                    "avg": round(sum(popularities) / len(popularities), 1),
                    "min": min(popularities),
                    "max": max(popularities),
                }
            else:
                popularity_stats = {"avg": 0.0, "min": 0.0, "max": 0.0}

            # Top tracks by popularity
            sorted_tracks = sorted(all_tracks, key=lambda t: t.get("popularity", 0), reverse=True)
            top_tracks = []
            for t in sorted_tracks[:5]:
                artist_name = t.get("artists", [{}])[0].get("name", "Sconosciuto") if t.get("artists") else "Sconosciuto"
                top_tracks.append({
                    "name": t.get("name", ""),
                    "artist": artist_name,
                    "popularity": t.get("popularity", 0),
                })

            # Genre distribution (from cached artist genres)
            playlist_genres: list[str] = []
            for t in all_tracks:
                for a in t.get("artists", []):
                    aid = a.get("id")
                    if aid and aid in artist_genres_cache:
                        playlist_genres.extend(artist_genres_cache[aid])

            genre_distribution: dict[str, float] = {}
            if playlist_genres:
                counter = Counter(playlist_genres)
                total = sum(counter.values())
                genre_distribution = {
                    genre: round(count / total * 100, 1)
                    for genre, count in counter.most_common(10)
                }

            # Audio features (from cache only)
            averages: dict[str, float] = {}
            analyzed_count = 0
            try:
                features = await get_or_fetch_features(db, track_ids[:200])
                if features:
                    keys = ["danceability", "energy", "valence", "acousticness",
                            "instrumentalness", "liveness", "speechiness", "tempo"]
                    for key in keys:
                        vals = [f[key] for f in features.values() if f.get(key) is not None]
                        averages[key] = round(sum(vals) / len(vals), 3) if vals else 0.0
                    analyzed_count = len(features)
            except Exception:
                logger.warning("Failed to fetch audio features for playlist %s", pid)

            results.append({
                "playlist_id": pid,
                "playlist_name": pdata["name"],
                "track_count": len(all_tracks),
                "analyzed_count": analyzed_count,
                "averages": averages,
                "popularity_stats": popularity_stats,
                "genre_distribution": genre_distribution,
                "top_tracks": top_tracks,
            })
    except SpotifyAuthError:
        raise HTTPException(status_code=401, detail="Sessione scaduta")
    except RateLimitError as e:
        raise HTTPException(
            status_code=429,
            detail="Troppe richieste a Spotify, riprova tra poco",
            headers={"Retry-After": str(int(e.retry_after or 5))},
        )
    except SpotifyServerError:
        raise HTTPException(status_code=502, detail="Spotify non disponibile, riprova tra poco")
    except Exception as exc:
        logger.exception("Errore imprevisto nel confronto playlist: %s", exc)
        raise HTTPException(status_code=500, detail="Errore durante il confronto delle playlist")
    finally:
        await client.close()

    return {"comparisons": results}
