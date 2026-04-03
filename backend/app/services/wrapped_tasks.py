"""In-memory task store for Wrapped computation.

Same pattern as playlist_tasks.py — task creato via POST,
risultati progressivi disponibili via GET polling.
"""

import logging
import time
import uuid

logger = logging.getLogger(__name__)

# In-memory task store
_wrapped_tasks: dict[str, dict] = {}
MAX_TASKS_PER_USER = 3
TASK_TTL_SECONDS = 1800  # 30 minuti


def create_task(user_id: int, time_range: str) -> dict:
    """Crea un nuovo task di computazione Wrapped."""
    _cleanup_expired()

    # Enforce max tasks per user — evict oldest if at limit
    user_tasks = [t for t in _wrapped_tasks.values() if t["user_id"] == user_id]
    if len(user_tasks) >= MAX_TASKS_PER_USER:
        oldest = min(user_tasks, key=lambda t: t["created_at"])
        del _wrapped_tasks[oldest["task_id"]]

    task_id = str(uuid.uuid4())
    task = {
        "task_id": task_id,
        "user_id": user_id,
        "time_range": time_range,
        "status": "pending",
        "phase": "",
        "completed_services": 0,
        "total_services": 5,
        "waiting_seconds": 0,
        "error_detail": None,
        "created_at": time.time(),
        "results": {
            "temporal": None,
            "evolution": None,
            "profile": None,
            "top_tracks": None,
            "network": None,
            "available_slides": ["intro"],
        },
    }
    _wrapped_tasks[task_id] = task
    return task


def get_task(task_id: str, user_id: int) -> dict | None:
    """Restituisce il task verificando l'ownership."""
    _cleanup_expired()
    task = _wrapped_tasks.get(task_id)
    if task and task["user_id"] == user_id:
        return task
    return None


def find_completed_task(user_id: int, time_range: str) -> dict | None:
    """Find a completed wrapped task for this user/time_range still within TTL."""
    _cleanup_expired()
    for task in _wrapped_tasks.values():
        if (
            task["user_id"] == user_id
            and task["time_range"] == time_range
            and task["status"] == "completed"
        ):
            return task
    return None


def _cleanup_expired():
    """Rimuove task scaduti (>30 minuti)."""
    now = time.time()
    expired = [
        tid
        for tid, t in _wrapped_tasks.items()
        if now - t["created_at"] > TASK_TTL_SECONDS
    ]
    for tid in expired:
        del _wrapped_tasks[tid]
