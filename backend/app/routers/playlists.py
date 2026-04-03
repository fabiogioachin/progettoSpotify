"""Router per playlist e confronto progressivo."""

import asyncio
import logging
import re
from collections import Counter
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import async_session, get_db
from app.dependencies import require_auth
from app.models.playlist_metadata import PlaylistMetadata
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
    retry_with_backoff,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/playlists", tags=["playlists"])

# Max consecutive throttle retries per playlist before aborting
_MAX_THROTTLE_RETRIES = 3


# ---------------------------------------------------------------------------
# Helper: upsert playlist metadata to DB cache
# ---------------------------------------------------------------------------

async def _upsert_playlist_metadata(
    db: AsyncSession,
    user_id: int,
    playlist_id: str,
    track_count: int,
    name: str = "",
    image_url: str | None = None,
    is_owner: bool = True,
) -> None:
    """Upsert playlist metadata to DB cache. Non-blocking — swallows errors."""
    try:
        stmt = pg_insert(PlaylistMetadata).values(
            user_id=user_id,
            playlist_id=playlist_id,
            track_count=track_count,
            name=name,
            image_url=image_url,
            is_owner=is_owner,
            updated_at=datetime.now(timezone.utc),
        ).on_conflict_do_update(
            constraint="uq_playlist_metadata_user_pid",
            set_={
                "track_count": track_count,
                "name": name,
                "image_url": image_url,
                "is_owner": is_owner,
                "updated_at": datetime.now(timezone.utc),
            },
        )
        await db.execute(stmt)
        await db.commit()
    except Exception as exc:
        logger.warning("Playlist metadata upsert failed for %s: %s", playlist_id, exc)
        try:
            await db.rollback()
        except Exception:
            pass


# ---------------------------------------------------------------------------
# Background task: fetch remaining zero-count playlist track counts
# ---------------------------------------------------------------------------

async def _bg_fetch_remaining_counts(
    user_id: int,
    zero_pids: list[dict],
) -> None:
    """Background task: fetch track counts sequentially with delay, upsert to DB.

    Uses dedicated DB session and SpotifyClient (not request-scoped).
    """
    if not zero_pids:
        return

    logger.info(
        "BG playlist count fetch: %d playlist per user_id=%d",
        len(zero_pids), user_id,
    )

    try:
        async with async_session() as db:
            client = SpotifyClient(db, user_id)
            try:
                for i, pinfo in enumerate(zero_pids):
                    pid = pinfo["id"]
                    fetched = False
                    for attempt in range(3):
                        try:
                            meta = await retry_with_backoff(
                                client.get_playlist_items, pid, limit=1, offset=0
                            )
                            total = meta.get("total") if meta else None
                            if total and total > 0:
                                await _upsert_playlist_metadata(
                                    db,
                                    user_id=user_id,
                                    playlist_id=pid,
                                    track_count=total,
                                    name=pinfo.get("name", ""),
                                    image_url=pinfo.get("image"),
                                    is_owner=pinfo.get("is_owner", True),
                                )
                            fetched = True
                            break
                        except SpotifyAuthError:
                            logger.warning("BG playlist count: auth expired, stopping")
                            return
                        except (ThrottleError, RateLimitError) as exc:
                            wait = min(getattr(exc, "retry_after", 10) or 10, 35)
                            logger.info(
                                "BG playlist count: throttled at %d/%d (attempt %d/3), waiting %ds",
                                i + 1, len(zero_pids), attempt + 1, wait,
                            )
                            await asyncio.sleep(wait)
                        except Exception as exc:
                            logger.warning("BG playlist count failed for %s: %s", pid, exc)
                            break
                    if not fetched:
                        logger.warning("BG playlist count: gave up on %s after 3 attempts", pid)
                    await asyncio.sleep(2)  # Sequential with 2s delay
            finally:
                await client.close()
    except Exception as exc:
        logger.warning("BG playlist count fetch failed: %s", exc)

    logger.info("BG playlist count fetch completato per user_id=%d", user_id)


# ---------------------------------------------------------------------------
# GET /api/v1/playlists — list playlists with DB-cached track counts
# ---------------------------------------------------------------------------

@router.get("", response_model=PlaylistListResponse)
async def get_playlists(
    request: Request,
    limit: int = Query(default=50, ge=1, le=50),
    offset: int = Query(default=0, ge=0),
    user_id: int = Depends(require_auth),
    db: AsyncSession = Depends(get_db),
):
    """Lista playlist dell'utente con track count da cache DB."""
    client = SpotifyClient(db, user_id)

    try:
        # Get user's Spotify ID to determine playlist ownership
        user_result = await db.execute(select(User).where(User.id == user_id))
        user = user_result.scalar_one_or_none()
        user_spotify_id = user.spotify_id if user else None

        # Step 1: Fetch playlist list from Spotify API (1 call)
        data = await retry_with_backoff(
            client.get_playlists, limit=limit, offset=offset
        )

        # Step 2: Read ALL PlaylistMetadata rows for this user from DB
        cached_result = await db.execute(
            select(PlaylistMetadata).where(PlaylistMetadata.user_id == user_id)
        )
        cached_map: dict[str, PlaylistMetadata] = {
            row.playlist_id: row for row in cached_result.scalars().all()
        }

        playlists = []
        to_upsert = []  # Playlists with real counts to persist
        still_zero = []  # Playlists with no count from API or DB

        for item in data.get("items", []):
            if not item:
                continue

            pid = item["id"]
            api_count = item.get("tracks", {}).get("total", 0)
            is_owner = (
                user_spotify_id is not None
                and item.get("owner", {}).get("id") == user_spotify_id
            )
            name = item.get("name", "")
            image = (
                item.get("images", [{}])[0].get("url")
                if item.get("images")
                else None
            )

            # Step 3: Determine best-known track count
            if api_count > 0:
                # Spotify gave us a real count — use it
                track_count = api_count
                to_upsert.append({
                    "playlist_id": pid,
                    "track_count": api_count,
                    "name": name,
                    "image_url": image,
                    "is_owner": is_owner,
                })
            elif pid in cached_map and cached_map[pid].track_count > 0:
                # DB cache has a previously fetched count
                track_count = cached_map[pid].track_count
            else:
                # No data from API or DB
                track_count = 0
                still_zero.append({
                    "id": pid,
                    "name": name,
                    "image": image,
                    "is_owner": is_owner,
                })

            playlists.append(
                {
                    "id": pid,
                    "name": name,
                    "description": item.get("description", ""),
                    "image": image,
                    "track_count": track_count,
                    "owner": item.get("owner", {}).get("display_name", ""),
                    "is_owner": is_owner,
                }
            )

        # Step 4: Upsert metadata for playlists with real counts (non-blocking)
        if to_upsert:
            try:
                rows = [
                    {
                        "user_id": user_id,
                        "playlist_id": r["playlist_id"],
                        "track_count": r["track_count"],
                        "name": r["name"],
                        "image_url": r["image_url"],
                        "is_owner": r["is_owner"],
                        "updated_at": datetime.now(timezone.utc),
                    }
                    for r in to_upsert
                ]
                stmt = pg_insert(PlaylistMetadata).values(rows)
                stmt = stmt.on_conflict_do_update(
                    constraint="uq_playlist_metadata_user_pid",
                    set_={
                        "track_count": stmt.excluded.track_count,
                        "name": stmt.excluded.name,
                        "image_url": stmt.excluded.image_url,
                        "is_owner": stmt.excluded.is_owner,
                        "updated_at": stmt.excluded.updated_at,
                    },
                )
                await db.execute(stmt)
                await db.commit()
            except Exception as exc:
                logger.warning("Bulk playlist metadata upsert failed: %s", exc)
                try:
                    await db.rollback()
                except Exception:
                    pass

        # Step 5-6: Launch background task for remaining zeros
        if still_zero:
            logger.info(
                "Launching BG task: %d playlist con track_count=0 per user_id=%d",
                len(still_zero), user_id,
            )
            asyncio.create_task(_bg_fetch_remaining_counts(user_id, still_zero))

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
# GET /api/v1/playlists/counts — lightweight DB-only endpoint
# ---------------------------------------------------------------------------

@router.get("/counts")
async def get_playlist_counts(
    user_id: int = Depends(require_auth),
    db: AsyncSession = Depends(get_db),
):
    """Restituisce track count cachati dal DB. Zero chiamate API."""
    result = await db.execute(
        select(PlaylistMetadata.playlist_id, PlaylistMetadata.track_count)
        .where(PlaylistMetadata.user_id == user_id)
    )
    counts = {row.playlist_id: row.track_count for row in result.fetchall()}
    return {"counts": counts}


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
