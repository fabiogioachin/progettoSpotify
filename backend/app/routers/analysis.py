"""Router per analisi audio features on-demand (librosa + RapidAPI fallback)."""

import asyncio
import logging
import time
import uuid

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import async_session, get_db
from app.dependencies import require_auth
from app.services.audio_feature_extractor import analyze_tracks_batch
from app.services.spotify_client import SpotifyClient
from app.utils.rate_limiter import (
    RateLimitError,
    SpotifyAuthError,
    SpotifyServerError,
    retry_with_backoff,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["analysis"])

# In-memory store per task di analisi
_analysis_tasks: dict[str, dict] = {}

# Durata massima di un task in memoria (30 minuti)
_TASK_TTL = 30 * 60

# Massimo task concorrenti per utente
_MAX_TASKS_PER_USER = 3


class AnalyzeTracksRequest(BaseModel):
    track_ids: list[str]


def _cleanup_old_tasks() -> None:
    """Rimuove task piu' vecchi di 30 minuti."""
    now = time.time()
    expired = [
        tid
        for tid, task in _analysis_tasks.items()
        if now - task.get("created_at", 0) > _TASK_TTL
    ]
    for tid in expired:
        del _analysis_tasks[tid]


@router.post("/analyze-tracks")
async def start_analysis(
    request: Request,
    body: AnalyzeTracksRequest,
    user_id: int = Depends(require_auth),
    db: AsyncSession = Depends(get_db),
):
    """Avvia analisi audio asincrona. Restituisce task_id per il polling."""
    _cleanup_old_tasks()

    if not body.track_ids:
        raise HTTPException(status_code=400, detail="Nessuna traccia specificata")

    if len(body.track_ids) > 100:
        raise HTTPException(status_code=400, detail="Massimo 100 tracce per richiesta")

    # Cap task concorrenti per utente
    user_tasks = [
        t
        for t in _analysis_tasks.values()
        if t.get("user_id") == user_id and t["status"] == "processing"
    ]
    if len(user_tasks) >= _MAX_TASKS_PER_USER:
        raise HTTPException(
            status_code=429, detail="Troppi task in corso, riprova tra poco"
        )

    client = SpotifyClient(db, user_id)
    try:
        # Fetch dettagli tracce (serve preview_url) — singolarmente (batch rimosso in dev mode)
        sem = asyncio.Semaphore(2)
        track_items = []

        async def _fetch_track(track_id: str) -> dict | None:
            async with sem:
                try:
                    data = await retry_with_backoff(client.get, f"/tracks/{track_id}")
                    artists = data.get("artists", [])
                    return {
                        "id": data.get("id", track_id),
                        "name": data.get("name", ""),
                        "artist": artists[0].get("name", "") if artists else "",
                        "preview_url": data.get("preview_url"),
                    }
                except SpotifyAuthError:
                    raise
                except Exception as exc:
                    logger.warning("Fetch traccia %s fallito: %s", track_id, exc)
                    return None

        results = await asyncio.gather(
            *[_fetch_track(tid) for tid in body.track_ids],
            return_exceptions=True,
        )

        # Re-raise auth errors
        for r in results:
            if isinstance(r, SpotifyAuthError):
                raise r

        track_items = [r for r in results if isinstance(r, dict)]

        if not track_items:
            raise HTTPException(status_code=404, detail="Nessuna traccia trovata")

        # Genera task ID e inizializza lo store
        task_id = str(uuid.uuid4())
        _analysis_tasks[task_id] = {
            "status": "processing",
            "total": len(track_items),
            "completed": 0,
            "results": {},
            "created_at": time.time(),
            "user_id": user_id,
        }

        # Lancia analisi in background con sessione DB dedicata
        # (la sessione del request viene chiusa al ritorno dell'handler)
        async def _run_analysis():
            async with async_session() as bg_db:
                await analyze_tracks_batch(bg_db, track_items, task_id, _analysis_tasks)

        asyncio.create_task(_run_analysis())

        return {"task_id": task_id, "total": len(track_items)}

    except SpotifyAuthError:
        raise HTTPException(status_code=401, detail="Sessione scaduta")
    except RateLimitError:
        raise
    except SpotifyServerError:
        raise HTTPException(status_code=502, detail="Errore temporaneo di Spotify")
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Errore avvio analisi: %s", exc)
        raise HTTPException(status_code=500, detail="Errore nell'avvio dell'analisi")
    finally:
        await client.close()


@router.get("/analyze-tracks/{task_id}")
async def get_analysis_status(
    task_id: str,
    user_id: int = Depends(require_auth),
):
    """Polling stato analisi con verifica ownership."""
    _cleanup_old_tasks()

    task = _analysis_tasks.get(task_id)
    if not task or task.get("user_id") != user_id:
        raise HTTPException(status_code=404, detail="Task di analisi non trovato")

    return {
        "status": task["status"],
        "total": task["total"],
        "completed": task["completed"],
        "results": task["results"],
    }
