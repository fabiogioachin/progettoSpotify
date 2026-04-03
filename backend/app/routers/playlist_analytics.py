"""Router per analisi approfondita delle playlist (progressive loading)."""

import asyncio
import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import async_session
from app.dependencies import require_auth
from app.models.playlist_metadata import PlaylistMetadata
from app.schemas import PlaylistTaskStartResponse, PlaylistTaskStatusResponse
from app.services.playlist_analytics import (
    _compute_overlap_matrix,
    _compute_size_histogram,
    _compute_freshness,
    _compute_staleness,
    _empty_result,
)
from app.services.playlist_tasks import create_task, find_completed_task, get_task
from app.services.spotify_client import SpotifyClient
from app.utils.rate_limiter import (
    RateLimitError,
    SpotifyAuthError,
    ThrottleError,
    retry_with_backoff,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/playlist-analytics", tags=["playlist-analytics"])

# Max consecutive throttle retries per phase before aborting
_MAX_THROTTLE_RETRIES = 3


@router.post("", response_model=PlaylistTaskStartResponse)
async def start_playlist_analytics(
    user_id: int = Depends(require_auth),
):
    """Avvia analisi playlist in background. Restituisce task_id per polling."""
    # Reuse a completed task still within TTL
    existing = find_completed_task(user_id)
    if existing:
        logger.info(
            "Riuso task esistente %s per user_id=%d", existing["task_id"], user_id
        )
        return {
            "task_id": existing["task_id"],
            "total_playlists": existing["total_playlists"],
        }

    try:
        task = create_task(
            user_id=user_id,
            task_type="analytics",
            total_playlists=0,  # updated after listing phase
        )
    except ValueError as exc:
        raise HTTPException(status_code=429, detail=str(exc))

    asyncio.create_task(_run_analytics_task(task["task_id"], user_id))

    return {"task_id": task["task_id"], "total_playlists": 0}


@router.get("/{task_id}", response_model=PlaylistTaskStatusResponse)
async def get_analytics_status(
    task_id: str,
    user_id: int = Depends(require_auth),
):
    """Polling stato analisi playlist con verifica ownership."""
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


async def _upsert_playlist_count(
    db: AsyncSession,
    user_id: int,
    playlist_id: str,
    track_count: int,
) -> None:
    """Upsert a single playlist's track count to the DB cache."""
    try:
        stmt = pg_insert(PlaylistMetadata).values(
            user_id=user_id,
            playlist_id=playlist_id,
            track_count=track_count,
            updated_at=datetime.now(timezone.utc),
        ).on_conflict_do_update(
            constraint="uq_playlist_metadata_user_pid",
            set_={
                "track_count": track_count,
                "updated_at": datetime.now(timezone.utc),
            },
        )
        await db.execute(stmt)
        await db.commit()
    except Exception as exc:
        logger.warning("Playlist count upsert failed for %s: %s", playlist_id, exc)
        try:
            await db.rollback()
        except Exception:
            pass


async def _run_analytics_task(task_id: str, user_id: int) -> None:
    """Background worker per analisi playlist progressiva.

    Phases: listing -> analyzing -> computing
    """
    from app.services.playlist_tasks import _playlist_tasks

    task = _playlist_tasks.get(task_id)
    if not task:
        return

    task["status"] = "processing"
    task["phase"] = "listing"

    client = None
    try:
        async with async_session() as db:
            client = SpotifyClient(db, user_id)

            # --- Phase 1: listing — fetch all playlists (paginated) ---
            all_playlists = []
            offset = 0
            throttle_count = 0

            while True:
                try:
                    data = await retry_with_backoff(
                        client.get_playlists, limit=50, offset=offset
                    )
                    items = data.get("items", [])
                    all_playlists.extend(items)
                    if len(items) < 50:
                        break
                    offset += 50
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

            if not all_playlists:
                task["status"] = "completed"
                task["results"] = _empty_result()
                return

            # Filter to user's own playlists (skip followed playlists by others)
            try:
                me = await client.get_me()
                my_spotify_id = me.get("id", "")
                my_playlists = [
                    p
                    for p in all_playlists
                    if p.get("owner", {}).get("id") == my_spotify_id
                ]
                logger.info(
                    "Playlist analytics: %d playlist totali, %d dell'utente (filtrate %d seguite)",
                    len(all_playlists),
                    len(my_playlists),
                    len(all_playlists) - len(my_playlists),
                )
            except Exception as exc:
                logger.warning(
                    "Impossibile ottenere profilo utente per filtraggio playlist, uso tutte: %s",
                    exc,
                )
                my_playlists = all_playlists

            if not my_playlists:
                task["status"] = "completed"
                task["results"] = _empty_result()
                return

            # Summary stats
            public_count = sum(1 for p in my_playlists if p.get("public"))
            private_count = len(my_playlists) - public_count
            collaborative_count = sum(
                1 for p in my_playlists if p.get("collaborative")
            )

            # Dev mode fix: use DB cache for track counts, fetch remaining sequentially
            raw_sizes = {
                p["id"]: p.get("tracks", {}).get("total", 0) for p in my_playlists
            }
            zero_count_pids = [pid for pid, sz in raw_sizes.items() if sz == 0]

            if zero_count_pids:
                # Check DB cache first
                try:
                    result = await db.execute(
                        select(PlaylistMetadata.playlist_id, PlaylistMetadata.track_count)
                        .where(
                            PlaylistMetadata.user_id == user_id,
                            PlaylistMetadata.playlist_id.in_(zero_count_pids),
                        )
                    )
                    for row in result.fetchall():
                        if row.track_count and row.track_count > 0:
                            raw_sizes[row.playlist_id] = row.track_count
                except Exception as exc:
                    logger.warning("DB cache read for track counts failed: %s", exc)

                # Remaining zeros: fetch sequentially with delay (not in burst)
                still_zero = [pid for pid in zero_count_pids if raw_sizes.get(pid, 0) == 0]
                count_throttle = 0
                for pid in still_zero[:20]:  # cap at 20
                    try:
                        count_data = await retry_with_backoff(
                            client.get_playlist_items, pid, limit=1, offset=0
                        )
                        total = count_data.get("total", 0)
                        if total > 0:
                            raw_sizes[pid] = total
                            # Upsert to DB cache
                            await _upsert_playlist_count(db, user_id, pid, total)
                    except SpotifyAuthError:
                        task["status"] = "error"
                        task["error_detail"] = "Sessione scaduta"
                        return
                    except (ThrottleError, RateLimitError) as exc:
                        count_throttle += 1
                        if count_throttle > _MAX_THROTTLE_RETRIES:
                            break  # stop trying, use what we have
                        wait_secs = min(getattr(exc, "retry_after", 10) or 10, 35)
                        task["status"] = "waiting"
                        task["waiting_seconds"] = int(wait_secs)
                        await asyncio.sleep(wait_secs)
                        task["status"] = "processing"
                        task["waiting_seconds"] = 0
                    except Exception:
                        pass  # keep raw_sizes[pid] = 0
                    await asyncio.sleep(1)  # sequential with delay

            sizes = [raw_sizes.get(p["id"], 0) for p in my_playlists]

            # Set partial results after listing (summary + size_distribution)
            size_distribution = _compute_size_histogram(sizes)
            task["total_playlists"] = len(my_playlists)
            task["results"] = {
                "summary": {
                    "total_playlists": len(my_playlists),
                    "public_count": public_count,
                    "private_count": private_count,
                    "collaborative_count": collaborative_count,
                    "avg_size": round(sum(sizes) / len(sizes), 1) if sizes else 0,
                    "total_tracks": sum(sizes),
                },
                "size_distribution": size_distribution,
                "playlists": [],
                "overlap_matrix": {"labels": [], "matrix": []},
            }

            # --- Phase 2: analyzing — fetch tracks per playlist ---
            task["phase"] = "analyzing"

            playlists_sorted = sorted(
                my_playlists,
                key=lambda p: raw_sizes.get(p["id"], 0),
                reverse=False,  # Smallest first → quick results, big playlists last
            )
            playlists_to_analyze = playlists_sorted[:50]

            playlist_tracks: dict[str, set] = {}
            playlist_details: list[dict] = []

            for idx, playlist in enumerate(playlists_to_analyze):
                pid = playlist["id"]
                track_ids: list[str] = []
                artists: set[str] = set()
                release_dates: list[str] = []
                added_dates: list[str] = []

                throttle_count = 0
                fetched = False

                while not fetched:
                    try:
                        pl_offset = 0
                        # Reset accumulators on retry
                        track_ids = []
                        artists = set()
                        release_dates = []
                        added_dates = []
                        while True:
                            items_data = await retry_with_backoff(
                                client.get_playlist_items,
                                pid,
                                limit=50,
                                offset=pl_offset,
                            )
                            items = items_data.get("items", [])
                            for item in items:
                                track = item.get("item") or item.get("track")
                                if not track or not track.get("id"):
                                    continue
                                track_ids.append(track["id"])
                                for a in track.get("artists", []):
                                    if a.get("id"):
                                        artists.add(a["id"])
                                album = track.get("album", {})
                                rd = album.get("release_date")
                                if rd:
                                    release_dates.append(rd)
                                added_at = item.get("added_at")
                                if added_at:
                                    added_dates.append(added_at)
                            if not items_data.get("next") or len(items) < 50:
                                break
                            pl_offset += 50
                        fetched = True
                    except SpotifyAuthError:
                        task["status"] = "error"
                        task["error_detail"] = "Sessione scaduta"
                        return
                    except (ThrottleError, RateLimitError) as exc:
                        throttle_count += 1
                        if throttle_count > _MAX_THROTTLE_RETRIES:
                            # Skip this playlist, continue with next
                            logger.warning(
                                "Analytics: skipping playlist %s after %d throttle retries",
                                pid, _MAX_THROTTLE_RETRIES,
                            )
                            fetched = True  # move to next playlist
                            break
                        wait_secs = min(getattr(exc, "retry_after", 10) or 10, 35)
                        task["status"] = "waiting"
                        task["waiting_seconds"] = int(wait_secs)
                        await asyncio.sleep(wait_secs)
                        task["status"] = "processing"
                        task["waiting_seconds"] = 0
                    except Exception as exc:
                        logger.warning("Errore fetch playlist %s: %s", pid, exc)
                        fetched = True  # skip this playlist

                playlist_tracks[pid] = set(track_ids)

                artist_concentration = round(
                    min(len(artists) / max(len(track_ids), 1), 1.0), 2
                )
                freshness = _compute_freshness(release_dates)
                staleness = _compute_staleness(added_dates)

                images = playlist.get("images", [])
                playlist_details.append(
                    {
                        "id": pid,
                        "name": playlist.get("name", ""),
                        "image": images[0]["url"] if images else None,
                        "track_count": len(track_ids),
                        "unique_artists": len(artists),
                        "artist_concentration": artist_concentration,
                        "freshness_year": freshness,
                        "staleness_days": staleness,
                        "is_public": playlist.get("public", False),
                        "is_collaborative": playlist.get("collaborative", False),
                    }
                )
                task["completed_playlists"] = idx + 1
                # Aggressive partial results: append each playlist as it completes
                task["results"]["playlists"] = list(playlist_details)

            # --- Phase 3: computing (pure compute) ---
            task["phase"] = "computing"

            # Update sizes with actual fetched track counts
            actual_counts = {d["id"]: d["track_count"] for d in playlist_details}
            sizes = [
                actual_counts.get(p["id"], p.get("tracks", {}).get("total", 0))
                for p in my_playlists
            ]

            overlap_matrix = _compute_overlap_matrix(playlist_details, playlist_tracks)
            size_distribution = _compute_size_histogram(sizes)

            task["status"] = "completed"
            task["results"] = {
                "summary": {
                    "total_playlists": len(my_playlists),
                    "public_count": public_count,
                    "private_count": private_count,
                    "collaborative_count": collaborative_count,
                    "avg_size": round(sum(sizes) / len(sizes), 1) if sizes else 0,
                    "total_tracks": sum(sizes),
                },
                "size_distribution": size_distribution,
                "playlists": playlist_details,
                "overlap_matrix": overlap_matrix,
            }

    except SpotifyAuthError:
        task["status"] = "error"
        task["error_detail"] = "Sessione scaduta"
    except Exception as exc:
        logger.exception("Errore imprevisto nell'analytics task %s: %s", task_id, exc)
        task["status"] = "error"
        task["error_detail"] = "Errore nell'analisi delle playlist"
    finally:
        if client:
            await client.close()
