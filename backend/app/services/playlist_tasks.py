"""In-memory task store per progressive playlist loading (compare + analytics).

Same pattern as _analysis_tasks in analysis.py — task creato via POST,
risultati progressivi disponibili via GET polling.
"""

import logging
import time
import uuid

logger = logging.getLogger(__name__)

# In-memory task store
_playlist_tasks: dict[str, dict] = {}
MAX_TASKS_PER_USER = 3
TASK_TTL_SECONDS = 1800  # 30 minuti


def create_task(
    user_id: int,
    task_type: str,
    total_playlists: int,
    playlist_ids: list[str] | None = None,
) -> dict:
    """Crea un nuovo task di caricamento progressivo.

    task_type: "compare" o "analytics"
    """
    _cleanup_expired()

    # Check per-user limit
    user_tasks = [
        t
        for t in _playlist_tasks.values()
        if t["user_id"] == user_id and t["status"] not in ("completed", "error")
    ]
    if len(user_tasks) >= MAX_TASKS_PER_USER:
        raise ValueError("Troppi task attivi. Attendi il completamento dei precedenti.")

    task_id = str(uuid.uuid4())
    task = {
        "task_id": task_id,
        "user_id": user_id,
        "task_type": task_type,
        "status": "pending",
        "phase": "",
        "total_playlists": total_playlists,
        "completed_playlists": 0,
        "playlist_ids": playlist_ids,
        "results": None,
        "waiting_seconds": 0,
        "error_detail": None,
        "created_at": time.time(),
    }
    _playlist_tasks[task_id] = task
    return task


def get_task(task_id: str, user_id: int) -> dict | None:
    """Restituisce il task verificando l'ownership."""
    task = _playlist_tasks.get(task_id)
    if task and task["user_id"] == user_id:
        return task
    return None


def _cleanup_expired():
    """Rimuove task scaduti (>30 minuti)."""
    now = time.time()
    expired = [
        tid
        for tid, t in _playlist_tasks.items()
        if now - t["created_at"] > TASK_TTL_SECONDS
    ]
    for tid in expired:
        del _playlist_tasks[tid]
