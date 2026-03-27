"""Router per playlist e confronto progressivo."""

import asyncio
import logging
import re
from collections import Counter

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import async_session, get_db
from app.dependencies import require_auth
from app.models.user import User
from app.schemas import (
    PlaylistCompareRequest,
    PlaylistListResponse,
    PlaylistTaskStartResponse,
    PlaylistTaskStatusResponse,
)
from app.services.audio_analyzer import get_or_fetch_features
from app.services.genre_cache import get_artist_genres_cached
from app.services.playlist_tasks import create_task, get_task
from app.services.popularity_cache import read_popularity_cache
from app.services.spotify_client import SpotifyClient
from app.utils.rate_limiter import (
    RateLimitError,
    SpotifyAuthError,
    SpotifyServerError,
    ThrottleError,
    gather_in_chunks,
    retry_with_backoff,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/playlists", tags=["playlists"])

# Max consecutive throttle retries per playlist before aborting
_MAX_THROTTLE_RETRIES = 3


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
        # Get user's Spotify ID to determine playlist ownership
        user_result = await db.execute(select(User).where(User.id == user_id))
        user = user_result.scalar_one_or_none()
        user_spotify_id = user.spotify_id if user else None

        data = await retry_with_backoff(
            client.get_playlists, limit=limit, offset=offset
        )

        playlists = []
        for item in data.get("items", []):
            if not item:
                continue
            playlists.append(
                {
                    "id": item["id"],
                    "name": item.get("name", ""),
                    "description": item.get("description", ""),
                    "image": (
                        item.get("images", [{}])[0].get("url")
                        if item.get("images")
                        else None
                    ),
                    "track_count": item.get("tracks", {}).get("total", 0),
                    "owner": item.get("owner", {}).get("display_name", ""),
                    "is_owner": (
                        user_spotify_id is not None
                        and item.get("owner", {}).get("id") == user_spotify_id
                    ),
                }
            )

        # Fallback: track_count può essere 0 se /me/playlists non restituisce
        # tracks.total in dev mode. Fetch metadata individuale per quelle playlist.
        # Limitato a 10 per non esaurire il budget API — le altre restano a 0
        # e il conteggio reale arriva quando l'utente le apre in compare/analytics.
        zero_count = [p for p in playlists if p["track_count"] == 0]
        if zero_count:
            to_fix = zero_count[:10]
            logger.info(
                "Track count fallback: fixing %d/%d playlist con count=0",
                len(to_fix),
                len(zero_count),
            )

            async def _fetch_playlist_meta(p: dict) -> None:
                try:
                    meta = await retry_with_backoff(
                        client.get_playlist_items, p["id"], limit=1, offset=0
                    )
                    total = meta.get("total") if meta else None
                    if total is not None:
                        p["track_count"] = total
                except SpotifyAuthError:
                    raise
                except Exception as exc:
                    logger.warning(
                        "Fallback track count failed for %s: %s", p["id"], exc
                    )

            meta_results = await gather_in_chunks(
                [_fetch_playlist_meta(p) for p in to_fix],
                chunk_size=2,
            )
            for r in meta_results:
                if isinstance(r, SpotifyAuthError):
                    raise r

        return {"playlists": playlists, "total": data.get("total", 0)}
    except (SpotifyAuthError, RateLimitError, SpotifyServerError):
        raise  # Handled by global exception handlers in main.py
    except Exception as exc:
        logger.error("Errore nel caricamento playlist: %s", exc)
        raise HTTPException(
            status_code=500, detail="Errore nel caricamento delle playlist"
        )
    finally:
        await client.close()


# ---------------------------------------------------------------------------
# Compare: POST-start / GET-poll progressive loading
# ---------------------------------------------------------------------------


@router.post("/compare", response_model=PlaylistTaskStartResponse)
async def start_compare(
    body: PlaylistCompareRequest,
    user_id: int = Depends(require_auth),
):
    """Avvia confronto playlist in background. Restituisce task_id per polling."""
    playlist_ids = [pid.strip() for pid in body.playlist_ids if pid.strip()]

    if len(playlist_ids) < 2 or len(playlist_ids) > 4:
        raise HTTPException(status_code=400, detail="Seleziona da 2 a 4 playlist")

    for pid in playlist_ids:
        if not re.match(r"^[a-zA-Z0-9]{1,50}$", pid):
            raise HTTPException(
                status_code=400, detail="Formato playlist ID non valido"
            )

    try:
        task = create_task(
            user_id=user_id,
            task_type="compare",
            total_playlists=len(playlist_ids),
            playlist_ids=playlist_ids,
        )
    except ValueError as exc:
        raise HTTPException(status_code=429, detail=str(exc))

    asyncio.create_task(_run_compare_task(task["task_id"], playlist_ids, user_id))

    return {"task_id": task["task_id"], "total_playlists": len(playlist_ids)}


@router.get("/compare/{task_id}", response_model=PlaylistTaskStatusResponse)
async def get_compare_status(
    task_id: str,
    user_id: int = Depends(require_auth),
):
    """Polling stato confronto playlist con verifica ownership."""
    task = get_task(task_id, user_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task non trovato")

    return {
        "task_id": task["task_id"],
        "status": task["status"],
        "phase": task["phase"],
        "total_playlists": task["total_playlists"],
        "completed_playlists": task["completed_playlists"],
        "waiting_seconds": task["waiting_seconds"],
        "error_detail": task["error_detail"],
        "results": task["results"],
    }


async def _run_compare_task(
    task_id: str, playlist_ids: list[str], user_id: int
) -> None:
    """Background worker per il confronto playlist progressivo.

    Usa sessione DB e SpotifyClient dedicati (mai riusare quelli del request handler).
    """
    from app.services.playlist_tasks import _playlist_tasks

    task = _playlist_tasks.get(task_id)
    if not task:
        return

    task["status"] = "processing"
    task["phase"] = "fetching_tracks"

    client = None
    try:
        async with async_session() as db:
            client = SpotifyClient(db, user_id)

            # --- Phase 1: fetch tracks per playlist (sequenziale, per progress) ---
            playlist_data_map: dict[str, dict] = {}
            for i, pid in enumerate(playlist_ids):
                all_tracks: list[dict] = []
                track_ids: list[str] = []
                playlist_name = ""
                api_total = 0

                throttle_count = 0
                fetched = False

                while not fetched:
                    try:
                        playlist_data = await retry_with_backoff(
                            client.get, f"/playlists/{pid}"
                        )
                        playlist_name = playlist_data.get("name", "")

                        offset = 0
                        while True:
                            items_data = await retry_with_backoff(
                                client.get_playlist_items,
                                pid,
                                limit=50,
                                offset=offset,
                            )
                            if offset == 0:
                                api_total = items_data.get("total", 0)
                            items = items_data.get("items", [])
                            for item in items:
                                t = item.get("item") or item.get("track")
                                if t and t.get("id"):
                                    all_tracks.append(t)
                                    track_ids.append(t["id"])
                            if not items_data.get("next") or len(items) < 50:
                                break
                            offset += 50
                        fetched = True
                    except SpotifyAuthError:
                        task["status"] = "error"
                        task["error_detail"] = "Sessione scaduta"
                        return
                    except (ThrottleError, RateLimitError) as exc:
                        throttle_count += 1
                        if throttle_count > _MAX_THROTTLE_RETRIES:
                            task["status"] = "error"
                            task["error_detail"] = (
                                "Troppe richieste a Spotify. Riprova tra qualche minuto."
                            )
                            return
                        wait_secs = min(getattr(exc, "retry_after", 10) or 10, 35)
                        task["status"] = "waiting"
                        task["waiting_seconds"] = int(wait_secs)
                        await asyncio.sleep(wait_secs)
                        task["status"] = "processing"
                        task["waiting_seconds"] = 0
                    except Exception as exc:
                        logger.warning("Failed to fetch playlist %s: %s", pid, exc)
                        fetched = True  # skip this playlist, continue

                logger.info(
                    "Playlist %s (%s): %d tracks fetched (API total: %d)",
                    pid,
                    playlist_name,
                    len(all_tracks),
                    api_total,
                )
                playlist_data_map[pid] = {
                    "name": playlist_name,
                    "tracks": all_tracks,
                    "track_ids": track_ids,
                    "api_total": max(api_total, len(all_tracks)),
                }
                task["completed_playlists"] = i + 1

            # --- Phase 1b: popularity from DB cache (zero API calls) ---
            all_compare_tracks = []
            for pdata in playlist_data_map.values():
                all_compare_tracks.extend(pdata["tracks"])
            try:
                await read_popularity_cache(all_compare_tracks, db)
            except Exception as exc:
                logger.warning("Popularity cache read failed: %s", exc)

            # --- Phase 2: genre fetch (deduplicated) ---
            task["phase"] = "fetching_genres"
            global_artist_ids: set[str] = set()
            for pdata in playlist_data_map.values():
                for t in pdata["tracks"]:
                    for a in t.get("artists", []):
                        if a.get("id"):
                            global_artist_ids.add(a["id"])

            try:
                artist_genres_cache = await get_artist_genres_cached(
                    db, client, list(global_artist_ids)
                )
            except SpotifyAuthError:
                task["status"] = "error"
                task["error_detail"] = "Sessione scaduta"
                return
            except (ThrottleError, RateLimitError):
                # Genre fetch throttled — continue with empty genres
                logger.warning("Genre fetch throttled during compare task %s", task_id)
                artist_genres_cache = {}
            except Exception as exc:
                logger.warning("Genre fetch failed: %s", exc)
                artist_genres_cache = {}

            # --- Phase 3: compute results (pure compute, no API calls) ---
            task["phase"] = "computing"
            results = []

            for pid in playlist_ids:
                pdata = playlist_data_map.get(pid)
                if not pdata:
                    continue
                all_tracks_pl = pdata["tracks"]
                track_ids_pl = pdata["track_ids"]

                # Popularity stats
                popularities = [t.get("popularity", 0) for t in all_tracks_pl]
                if popularities:
                    popularity_stats = {
                        "avg": round(sum(popularities) / len(popularities), 1),
                        "min": min(popularities),
                        "max": max(popularities),
                    }
                else:
                    popularity_stats = {"avg": 0.0, "min": 0.0, "max": 0.0}

                # Top tracks by popularity
                sorted_tracks = sorted(
                    all_tracks_pl,
                    key=lambda t: t.get("popularity", 0),
                    reverse=True,
                )
                top_tracks = []
                for t in sorted_tracks[:5]:
                    artist_name = (
                        t.get("artists", [{}])[0].get("name", "Sconosciuto")
                        if t.get("artists")
                        else "Sconosciuto"
                    )
                    top_tracks.append(
                        {
                            "name": t.get("name", ""),
                            "artist": artist_name,
                            "popularity": t.get("popularity", 0),
                        }
                    )

                # Genre distribution
                playlist_genres: list[str] = []
                for t in all_tracks_pl:
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

                # Audio features (from cache only, no API calls)
                averages: dict[str, float] = {}
                analyzed_count = 0
                try:
                    features = await get_or_fetch_features(db, track_ids_pl[:200])
                    if features:
                        keys = [
                            "danceability",
                            "energy",
                            "valence",
                            "acousticness",
                            "instrumentalness",
                            "liveness",
                            "speechiness",
                            "tempo",
                        ]
                        for key in keys:
                            vals = [
                                f[key]
                                for f in features.values()
                                if f.get(key) is not None
                            ]
                            averages[key] = (
                                round(sum(vals) / len(vals), 3) if vals else 0.0
                            )
                        analyzed_count = len(features)
                except Exception:
                    logger.warning(
                        "Failed to fetch audio features for playlist %s", pid
                    )

                results.append(
                    {
                        "playlist_id": pid,
                        "playlist_name": pdata["name"],
                        "track_count": pdata.get("api_total", len(all_tracks_pl)),
                        "analyzed_count": analyzed_count,
                        "averages": averages,
                        "popularity_stats": popularity_stats,
                        "genre_distribution": genre_distribution,
                        "top_tracks": top_tracks,
                    }
                )

            task["status"] = "completed"
            task["results"] = {"comparisons": results}

    except SpotifyAuthError:
        task["status"] = "error"
        task["error_detail"] = "Sessione scaduta"
    except Exception as exc:
        logger.exception("Errore imprevisto nel compare task %s: %s", task_id, exc)
        task["status"] = "error"
        task["error_detail"] = "Errore durante il confronto delle playlist"
    finally:
        if client:
            await client.close()
