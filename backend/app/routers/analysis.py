"""Router per analisi audio features on-demand (librosa + RapidAPI fallback)."""

import asyncio
import logging
import time
import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import async_session, get_db
from app.dependencies import require_auth
from app.services.audio_feature_extractor import analyze_tracks_batch

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1", tags=["analysis"])

# In-memory store per task di analisi
_analysis_tasks: dict[str, dict] = {}

# Durata massima di un task in memoria (30 minuti)
_TASK_TTL = 30 * 60

# Massimo task concorrenti per utente
_MAX_TASKS_PER_USER = 3


class TrackItem(BaseModel):
    id: str
    name: str = ""
    artist: str = ""
    preview_url: str | None = None


class AnalyzeTracksRequest(BaseModel):
    tracks: list[TrackItem]


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
    body: AnalyzeTracksRequest,
    user_id: int = Depends(require_auth),
    db: AsyncSession = Depends(get_db),
):
    """Avvia analisi audio asincrona. Restituisce task_id per il polling.

    Il frontend invia i dati delle tracce (id, name, artist, preview_url) già
    disponibili dalla risposta di /api/library/top — zero chiamate Spotify qui.
    """
    _cleanup_old_tasks()

    if not body.tracks:
        raise HTTPException(status_code=400, detail="Nessuna traccia specificata")

    if len(body.tracks) > 100:
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

    # Converti in dicts per analyze_tracks_batch (nessuna chiamata Spotify)
    track_items = [t.model_dump() for t in body.tracks]

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
