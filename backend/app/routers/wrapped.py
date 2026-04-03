"""Router per il Wrapped — recap delle statistiche di ascolto.

Supports both:
- POST "" + GET "/{task_id}" (async task pattern, preferred)
- GET "" (legacy blocking, deprecated)
"""

import asyncio
import logging

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import async_session, get_db
from app.dependencies import require_auth
from app.services import wrapped_tasks
from app.services.artist_network import build_artist_network
from app.services.audio_analyzer import compute_profile
from app.services.data_bundle import RequestDataBundle
from app.services.spotify_client import SpotifyClient
from app.services.taste_evolution import compute_taste_evolution
from app.services.temporal_patterns import compute_temporal_patterns
from app.utils.json_utils import sanitize_nans
from app.utils.rate_limiter import (
    RateLimitError,
    SpotifyAuthError,
    SpotifyServerError,
    ThrottleError,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/wrapped", tags=["wrapped"])


async def _safe_fetch(label: str, coro):
    """Esegue una coroutine e restituisce (label, result) o (label, None) in caso di errore."""
    try:
        return label, await coro
    except SpotifyAuthError:
        raise
    except Exception as exc:
        logger.warning("Wrapped %s failed: %s", label, exc)
        return label, None


@router.get("")
async def get_wrapped(
    request: Request,
    user_id: int = Depends(require_auth),
    db: AsyncSession = Depends(get_db),
    time_range: str = Query("medium_term"),
):
    """Recap completo delle statistiche di ascolto dell'utente (blocking, deprecated)."""
    logger.info("Deprecation: GET /wrapped senza task_id — usare POST + GET/{task_id}")
    if time_range not in ("short_term", "medium_term", "long_term"):
        time_range = "medium_term"

    client = SpotifyClient(db, user_id)
    bundle = RequestDataBundle(client)
    try:
        # Pre-fetch all data in parallel (7 API calls instead of 13)
        await bundle.prefetch(artists=True, tracks=True, recent=True)

        results = dict(
            await asyncio.gather(
                _safe_fetch(
                    "temporal",
                    compute_temporal_patterns(client, db=db, user_id=user_id),
                ),
                _safe_fetch(
                    "evolution", compute_taste_evolution(client, bundle=bundle)
                ),
                _safe_fetch(
                    "profile", compute_profile(db, client, time_range, bundle=bundle)
                ),
                _safe_fetch(
                    "top_tracks",
                    bundle.get_top_tracks(time_range=time_range),
                ),
                _safe_fetch("network", build_artist_network(client, bundle=bundle)),
            )
        )
    except (SpotifyAuthError, RateLimitError, SpotifyServerError):
        raise  # Handled by global exception handlers in main.py
    except Exception as exc:
        logger.exception("Errore wrapped: %s", exc)
        raise HTTPException(status_code=500, detail="Errore nel calcolo Wrapped")
    finally:
        await client.close()

    # Compute available slides based on data presence
    available = ["intro"]  # always shown

    top_tracks_data = results.get("top_tracks")
    if isinstance(top_tracks_data, dict):
        top_tracks_items = top_tracks_data.get("items", [])[:10]
    else:
        top_tracks_items = (
            top_tracks_data[:10] if isinstance(top_tracks_data, list) else []
        )

    if top_tracks_items:
        available.append("top_tracks")

    temporal = results.get("temporal")
    if temporal and temporal.get("total_plays", 0) > 0:
        available.extend(["listening_habits", "peak_hours"])

    evolution = results.get("evolution")
    if evolution:
        artists = evolution.get("artists", {})
        if artists.get("loyal") or artists.get("rising"):
            available.append("artist_evolution")

    profile = results.get("profile")
    if profile and profile.get("genres"):
        available.append("top_genres")

    network = results.get("network")
    if network and network.get("metrics", {}).get("cluster_count", 0) > 0:
        available.append("artist_network")

    available.append("outro")  # always shown

    return sanitize_nans(
        {
            "temporal": results.get("temporal"),
            "evolution": results.get("evolution"),
            "profile": results.get("profile"),
            "top_tracks": top_tracks_items,
            "network": results.get("network"),
            "available_slides": available,
        }
    )


# ---------------------------------------------------------------------------
# Async POST/poll pattern (preferred)
# ---------------------------------------------------------------------------


@router.post("")
async def start_wrapped(
    request: Request,
    user_id: int = Depends(require_auth),
    time_range: str = Query("medium_term"),
):
    """Avvia il calcolo Wrapped in background e restituisce un task_id per il polling."""
    if time_range not in ("short_term", "medium_term", "long_term"):
        time_range = "medium_term"

    # Reuse a completed task for the same user/time_range still within TTL
    existing = wrapped_tasks.find_completed_task(user_id, time_range)
    if existing:
        logger.info(
            "Riuso task wrapped esistente %s per user_id=%d time_range=%s",
            existing["task_id"],
            user_id,
            time_range,
        )
        return {
            "task_id": existing["task_id"],
            "total_services": existing["total_services"],
        }

    task = wrapped_tasks.create_task(user_id, time_range)
    asyncio.create_task(_run_wrapped_task(task["task_id"], user_id, time_range))
    return {"task_id": task["task_id"], "total_services": task["total_services"]}


@router.get("/{task_id}")
async def get_wrapped_status(
    task_id: str,
    request: Request,
    user_id: int = Depends(require_auth),
):
    """Restituisce lo stato corrente e i risultati progressivi del task Wrapped."""
    task = wrapped_tasks.get_task(task_id, user_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task non trovato")
    return {
        "task_id": task["task_id"],
        "status": task["status"],
        "phase": task["phase"],
        "completed_services": task["completed_services"],
        "total_services": task["total_services"],
        "waiting_seconds": task["waiting_seconds"],
        "error_detail": task["error_detail"],
        "results": sanitize_nans(task["results"]) if task["results"] else None,
    }


async def _run_wrapped_task(task_id: str, user_id: int, time_range: str):
    """Background computation of Wrapped slides — updates task progressively."""
    from app.services.wrapped_tasks import _wrapped_tasks

    task = _wrapped_tasks.get(task_id)
    if not task:
        return

    task["status"] = "processing"
    client = None
    try:
        async with async_session() as db:
            client = SpotifyClient(db, user_id)
            bundle = RequestDataBundle(client)

            # Phase 0: Prefetch common data
            task["phase"] = "prefetch"
            await bundle.prefetch(artists=True, tracks=True, recent=True)

            # Phase 1: Top tracks (instant — already prefetched)
            task["phase"] = "top_tracks"
            try:
                top_tracks_raw = await bundle.get_top_tracks(time_range=time_range)
                if isinstance(top_tracks_raw, dict):
                    top_tracks_items = top_tracks_raw.get("items", [])[:10]
                else:
                    top_tracks_items = (
                        top_tracks_raw[:10] if isinstance(top_tracks_raw, list) else []
                    )
                task["results"]["top_tracks"] = top_tracks_items
                if top_tracks_items:
                    task["results"]["available_slides"].append("top_tracks")
            except SpotifyAuthError:
                raise
            except Exception as exc:
                logger.warning("Wrapped top_tracks failed: %s", exc)
            task["completed_services"] = 1

            # Phase 2: Temporal patterns
            task["phase"] = "temporal"
            try:
                temporal = await compute_temporal_patterns(
                    client, db=db, user_id=user_id
                )
                task["results"]["temporal"] = (
                    sanitize_nans(temporal) if temporal else None
                )
                if temporal and temporal.get("total_plays", 0) > 0:
                    task["results"]["available_slides"].extend(
                        ["listening_habits", "peak_hours"]
                    )
            except SpotifyAuthError:
                raise
            except Exception as exc:
                logger.warning("Wrapped temporal failed: %s", exc)
            task["completed_services"] = 2

            # Phase 3: Taste evolution
            task["phase"] = "evolution"
            try:
                evolution = await compute_taste_evolution(client, bundle=bundle)
                task["results"]["evolution"] = (
                    sanitize_nans(evolution) if evolution else None
                )
                if evolution:
                    artists = evolution.get("artists", {})
                    if artists.get("loyal") or artists.get("rising"):
                        task["results"]["available_slides"].append("artist_evolution")
            except SpotifyAuthError:
                raise
            except Exception as exc:
                logger.warning("Wrapped evolution failed: %s", exc)
            task["completed_services"] = 3

            # Phase 4: Profile/genres
            task["phase"] = "profile"
            try:
                profile = await compute_profile(db, client, time_range, bundle=bundle)
                task["results"]["profile"] = sanitize_nans(profile) if profile else None
                if profile and profile.get("genres"):
                    task["results"]["available_slides"].append("top_genres")
            except SpotifyAuthError:
                raise
            except Exception as exc:
                logger.warning("Wrapped profile failed: %s", exc)
            task["completed_services"] = 4

            # Phase 5: Artist network (slowest)
            task["phase"] = "network"
            try:
                network = await build_artist_network(client, db=db, bundle=bundle)
                task["results"]["network"] = sanitize_nans(network) if network else None
                if network and network.get("metrics", {}).get("cluster_count", 0) > 0:
                    task["results"]["available_slides"].append("artist_network")
            except SpotifyAuthError:
                raise
            except Exception as exc:
                logger.warning("Wrapped network failed: %s", exc)
            task["completed_services"] = 5

            # Done
            task["results"]["available_slides"].append("outro")
            task["status"] = "completed"

    except SpotifyAuthError:
        task["status"] = "error"
        task["error_detail"] = "Sessione Spotify scaduta. Effettua nuovamente il login."
    except (RateLimitError, ThrottleError) as exc:
        task["status"] = "error"
        retry_after = getattr(exc, "retry_after", 30) or 30
        task["error_detail"] = (
            f"Troppe richieste a Spotify. Riprova tra {int(retry_after)}s."
        )
    except Exception as exc:
        logger.exception("Wrapped task %s failed: %s", task_id, exc)
        task["status"] = "error"
        task["error_detail"] = "Errore nel calcolo Wrapped"
    finally:
        if client:
            await client.close()
