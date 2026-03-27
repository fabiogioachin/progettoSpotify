"""Data retention cleanup — monthly purge of expired data per retention policy."""

import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import delete

from app.database import async_session
from app.models.listening_history import UserSnapshot
from app.models.track import TrackPopularity

logger = logging.getLogger(__name__)


async def cleanup_expired_data():
    """Monthly cleanup of expired data per retention policy.

    Retention rules:
    - user_snapshots older than 365 days -> DELETE
    - track_popularity with cached_at older than 90 days -> DELETE
    - recent_plays, daily_listening_stats, audio_features -> kept forever
    """
    now = datetime.now(timezone.utc)
    cutoff_365 = now - timedelta(days=365)
    cutoff_90 = now - timedelta(days=90)

    deleted_counts: dict[str, int] = {}

    async with async_session() as db:
        # UserSnapshot: delete older than 365 days
        result = await db.execute(
            delete(UserSnapshot).where(UserSnapshot.captured_at < cutoff_365.date())
        )
        deleted_counts["user_snapshots"] = result.rowcount

        # TrackPopularity: delete cached_at older than 90 days
        result = await db.execute(
            delete(TrackPopularity).where(TrackPopularity.cached_at < cutoff_90)
        )
        deleted_counts["track_popularity"] = result.rowcount

        await db.commit()

    logger.info(
        "Pulizia dati scaduti completata: %s",
        ", ".join(f"{table}={count}" for table, count in deleted_counts.items()),
    )
