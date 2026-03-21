"""Cache centralizzata per popularity dei brani.

read_popularity_cache() — solo DB, zero API calls. Usata dagli endpoint sincroni.
La cache viene popolata dal job orario sync_recent_plays in background_tasks.py.
"""

import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.track import TrackPopularity

logger = logging.getLogger(__name__)

POPULARITY_CACHE_TTL = timedelta(hours=24)


async def read_popularity_cache(
    tracks: list[dict],
    db: AsyncSession,
) -> int:
    """Legge popularity dalla cache DB e applica in-place ai track dict.

    NON fa chiamate API. Ritorna il numero di track arricchite dalla cache.
    """
    needs_pop: dict[str, list[dict]] = {}
    for t in tracks:
        tid = t.get("id")
        if tid and t.get("popularity") is None:
            needs_pop.setdefault(tid, []).append(t)

    if not needs_pop:
        return 0

    unique_ids = list(needs_pop.keys())

    cutoff = datetime.now(timezone.utc) - POPULARITY_CACHE_TTL
    result = await db.execute(
        select(TrackPopularity).where(
            TrackPopularity.track_spotify_id.in_(unique_ids),
            TrackPopularity.cached_at >= cutoff,
        )
    )
    cached = {row.track_spotify_id: row.popularity for row in result.scalars().all()}

    for tid, pop in cached.items():
        if tid in needs_pop:
            for t in needs_pop[tid]:
                t["popularity"] = pop

    if cached:
        logger.info(
            "Popularity cache hit: %d/%d track da DB",
            len(cached),
            len(unique_ids),
        )

    return len(cached)
