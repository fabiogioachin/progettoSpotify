"""Servizio cache generi artista — DB persistente (7gg TTL) + fetch Spotify on miss."""

import json
import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.track import ArtistGenre
from app.services.spotify_client import SpotifyClient
from app.utils.rate_limiter import (
    RateLimitError,
    SpotifyAuthError,
    gather_in_chunks,
    retry_with_backoff,
)

logger = logging.getLogger(__name__)

GENRE_CACHE_TTL_DAYS = 7


async def get_artist_genres_cached(
    db: AsyncSession,
    client: SpotifyClient | None,
    artist_ids: list[str],
) -> dict[str, list[str]]:
    """
    Return {artist_id: [genres]} for the requested artist IDs.

    1. Check DB cache (artist_genres table, TTL 7 days)
    2. For cache misses, fetch from Spotify API via client.get_artist
    3. Upsert results into DB cache
    4. Return merged dict

    If client is None (background job context), only return DB-cached data.
    """
    if not artist_ids:
        return {}

    cutoff = datetime.now(timezone.utc) - timedelta(days=GENRE_CACHE_TTL_DAYS)

    # Step 1: Query DB cache
    result = await db.execute(
        select(ArtistGenre).where(
            ArtistGenre.artist_spotify_id.in_(artist_ids),
            ArtistGenre.cached_at > cutoff,
        )
    )
    cached = result.scalars().all()
    genres_map: dict[str, list[str]] = {}
    for row in cached:
        try:
            genres_map[row.artist_spotify_id] = json.loads(row.genres)
        except (json.JSONDecodeError, TypeError):
            genres_map[row.artist_spotify_id] = []

    # Step 2: Find misses
    missing_ids = [aid for aid in artist_ids if aid not in genres_map]

    if not missing_ids or client is None:
        return genres_map

    # Step 3: Fetch from Spotify API (in chunks to respect rate limits)
    async def _fetch_one(aid: str):
        try:
            data = await retry_with_backoff(client.get_artist, aid)
            return aid, data.get("name"), data.get("genres", [])
        except (SpotifyAuthError, RateLimitError):
            raise
        except Exception as exc:
            logger.warning("Genre fetch failed for artist %s: %s", aid, exc)
            return aid, None, []

    tasks = [_fetch_one(aid) for aid in missing_ids]
    results = await gather_in_chunks(tasks, chunk_size=4)

    # Step 4: Upsert into DB cache
    rows_to_upsert = []
    for item in results:
        if isinstance(item, Exception):
            continue
        aid, name, genres = item
        genres_map[aid] = genres
        rows_to_upsert.append(
            {
                "artist_spotify_id": aid,
                "artist_name": name,
                "genres": json.dumps(genres),
                "cached_at": datetime.now(timezone.utc),
            }
        )

    if rows_to_upsert:
        try:
            stmt = pg_insert(ArtistGenre).values(rows_to_upsert)
            stmt = stmt.on_conflict_do_update(
                index_elements=["artist_spotify_id"],
                set_={
                    "artist_name": stmt.excluded.artist_name,
                    "genres": stmt.excluded.genres,
                    "cached_at": stmt.excluded.cached_at,
                },
            )
            await db.execute(stmt)
            await db.commit()
        except Exception as exc:
            logger.warning("Genre cache upsert failed: %s", exc)
            await db.rollback()

    return genres_map


def build_genre_distribution(
    artist_genres: dict[str, list[str]],
    tracks: list[dict],
) -> dict[str, float]:
    """
    Build genre frequency distribution from tracks and their artists' genres.

    Returns {genre: percentage} sorted by frequency descending.
    """
    from app.services.genre_utils import normalize_genre

    genre_counts: dict[str, int] = {}
    for track in tracks:
        track_artists = track.get("artists", [])
        for artist in track_artists:
            aid = artist.get("id", "")
            genres = artist_genres.get(aid, [])
            for g in genres:
                normalized = normalize_genre(g)
                if normalized:
                    genre_counts[normalized] = genre_counts.get(normalized, 0) + 1

    total = sum(genre_counts.values())
    if total == 0:
        return {}

    distribution = {
        g: round(count / total * 100, 1)
        for g, count in sorted(genre_counts.items(), key=lambda x: -x[1])
    }
    return distribution
