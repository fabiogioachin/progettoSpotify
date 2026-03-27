"""One-time script: backfill artist_genres cache from existing RecentPlay data.

Usage: cd backend && python -m scripts.backfill_artist_genres
"""

import asyncio
import json
import logging
import sys
from datetime import datetime, timedelta, timezone

from sqlalchemy import distinct, select

from app.database import async_session
from app.models.listening_history import RecentPlay
from app.models.track import ArtistGenre
from app.models.user import SpotifyToken, User
from app.services.api_budget import Priority
from app.services.spotify_client import SpotifyClient
from app.utils.rate_limiter import (
    RateLimitError,
    SpotifyAuthError,
    ThrottleError,
    gather_in_chunks,
    retry_with_backoff,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

GENRE_CACHE_TTL_DAYS = 7


async def _find_admin_user_id() -> int | None:
    """Find the first admin user with valid tokens."""
    async with async_session() as db:
        result = await db.execute(
            select(User.id)
            .join(SpotifyToken, SpotifyToken.user_id == User.id)
            .where(User.is_admin.is_(True))
            .limit(1)
        )
        row = result.scalar_one_or_none()
        if row:
            return row
        # Fallback: any user with tokens
        result = await db.execute(
            select(User.id)
            .join(SpotifyToken, SpotifyToken.user_id == User.id)
            .limit(1)
        )
        return result.scalar_one_or_none()


async def _get_uncached_artist_ids() -> list[str]:
    """Get artist IDs from RecentPlay that are not in ArtistGenre or have expired cache."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=GENRE_CACHE_TTL_DAYS)

    async with async_session() as db:
        # All distinct artist IDs from RecentPlay
        all_result = await db.execute(
            select(distinct(RecentPlay.artist_spotify_id)).where(
                RecentPlay.artist_spotify_id.isnot(None),
                RecentPlay.artist_spotify_id != "",
            )
        )
        all_ids = {row[0] for row in all_result.all()}

        # Already cached and not expired
        cached_result = await db.execute(
            select(ArtistGenre.artist_spotify_id).where(
                ArtistGenre.cached_at > cutoff,
            )
        )
        cached_ids = {row[0] for row in cached_result.all()}

    uncached = list(all_ids - cached_ids)
    return uncached


async def main():
    user_id = await _find_admin_user_id()
    if user_id is None:
        logger.error("Nessun utente con token valido trovato. Impossibile procedere.")
        sys.exit(1)

    logger.info("Utilizzo user_id=%d per le chiamate Spotify API", user_id)

    uncached_ids = await _get_uncached_artist_ids()
    total = len(uncached_ids)
    if total == 0:
        logger.info("Tutti gli artisti sono gia' in cache. Nulla da fare.")
        return

    logger.info("Artisti da recuperare: %d", total)

    async with async_session() as db:
        client = SpotifyClient(db, user_id, priority=Priority.P1_BACKGROUND_SYNC)
        try:
            fetched = 0
            failed = 0

            async def _fetch_one(aid: str):
                try:
                    data = await retry_with_backoff(client.get_artist, aid)
                    return aid, data.get("name"), data.get("genres", [])
                except (SpotifyAuthError, RateLimitError):
                    raise
                except Exception as exc:
                    logger.warning("Fetch fallito per artista %s: %s", aid, exc)
                    return aid, None, []

            # Process sequentially, one artist at a time, with delay between calls
            # to stay within budget (P1_LOGIN allows ~6 calls/30s)
            delay_between = 6.0  # seconds between API calls
            from sqlalchemy.dialects.postgresql import insert as pg_insert

            for idx, aid in enumerate(uncached_ids):
                try:
                    data = await retry_with_backoff(client.get_artist, aid)
                    name = data.get("name")
                    genres = data.get("genres", [])
                except (SpotifyAuthError, RateLimitError, ThrottleError) as exc:
                    logger.warning(
                        "Rate limit dopo %d/%d artisti, pausa 35s: %s",
                        fetched,
                        total,
                        exc,
                    )
                    await asyncio.sleep(35)
                    # Retry this one
                    try:
                        data = await retry_with_backoff(client.get_artist, aid)
                        name = data.get("name")
                        genres = data.get("genres", [])
                    except Exception:
                        failed += 1
                        continue
                except Exception as exc:
                    logger.warning("Fetch fallito per artista %s: %s", aid, exc)
                    failed += 1
                    continue

                stmt = (
                    pg_insert(ArtistGenre)
                    .values(
                        artist_spotify_id=aid,
                        artist_name=name,
                        genres=json.dumps(genres),
                        cached_at=datetime.now(timezone.utc),
                    )
                    .on_conflict_do_update(
                        index_elements=["artist_spotify_id"],
                        set_={
                            "artist_name": name,
                            "genres": json.dumps(genres),
                            "cached_at": datetime.now(timezone.utc),
                        },
                    )
                )
                await db.execute(stmt)
                await db.commit()
                fetched += 1

                if fetched % 10 == 0 or (idx + 1) == total:
                    logger.info(
                        "Progresso: %d/%d recuperati, %d falliti",
                        fetched,
                        total,
                        failed,
                    )

                # Delay to respect budget
                if (idx + 1) < total:
                    await asyncio.sleep(delay_between)

            logger.info(
                "Backfill completato: %d/%d artisti recuperati, %d falliti",
                fetched,
                total,
                failed,
            )
        finally:
            await client.close()


if __name__ == "__main__":
    asyncio.run(main())
