"""Servizio per il calcolo delle metriche profilo utente."""

import asyncio
import json
import logging
import math
from collections import Counter
from datetime import date, datetime, timedelta, timezone

from sqlalchemy import func, select, distinct
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import async_session
from app.models.listening_history import (
    DailyListeningStats,
    RecentPlay,
    UserProfileMetrics,
    UserSnapshot,
)
from app.services.spotify_client import SpotifyClient
from app.utils.rate_limiter import SpotifyAuthError, retry_with_backoff

logger = logging.getLogger(__name__)


async def _safe_fetch(label, coro):
    try:
        return await coro
    except SpotifyAuthError:
        raise
    except Exception as exc:
        logger.warning("profile_metrics %s failed: %s", label, exc)
        return {"items": []}


def compute_obscurity_score(top_artists: list[dict]) -> float:
    """Score 0-100: higher = more obscure. Based on inverse of avg popularity."""
    if not top_artists:
        return 0.0
    popularities = [a["popularity"] for a in top_artists if "popularity" in a]
    if not popularities:
        return 0.0
    return round(100 - sum(popularities) / len(popularities), 1)


def compute_genre_diversity(top_artists: list[dict]) -> float:
    """Shannon entropy of genres, normalized to 0-100."""
    genres = []
    for a in top_artists:
        genres.extend(a.get("genres", []))
    if not genres:
        return 0.0
    counter = Counter(genres)
    total = sum(counter.values())
    entropy = -sum(
        (c / total) * math.log2(c / total) for c in counter.values() if c > 0
    )
    # Normalize: max entropy = log2(num_unique_genres)
    max_entropy = math.log2(len(counter)) if len(counter) > 1 else 1.0
    return round((entropy / max_entropy) * 100, 1) if max_entropy > 0 else 0.0


async def compute_artist_loyalty(db: AsyncSession, user_id: int) -> float:
    """Overlap between oldest and newest UserSnapshot top_artists. 0-100."""
    result = await db.execute(
        select(UserSnapshot)
        .where(UserSnapshot.user_id == user_id)
        .order_by(UserSnapshot.captured_at.asc())
    )
    snapshots = result.scalars().all()
    if len(snapshots) < 2:
        return 0.0

    oldest = set(
        a["id"] for a in json.loads(snapshots[0].top_artists_json) if "id" in a
    )
    newest = set(
        a["id"] for a in json.loads(snapshots[-1].top_artists_json) if "id" in a
    )

    if not oldest or not newest:
        return 0.0

    union = oldest | newest
    intersection = oldest & newest
    return round((len(intersection) / len(union)) * 100, 1) if union else 0.0


def compute_decade_distribution(top_tracks: list[dict]) -> dict[str, int]:
    """Group tracks by album release decade."""
    decades: Counter = Counter()
    for track in top_tracks:
        release_date = track.get("album", {}).get("release_date", "")
        if release_date and len(release_date) >= 4:
            try:
                year = int(release_date[:4])
                decade = f"{(year // 10) * 10}s"
                decades[decade] += 1
            except ValueError:
                pass
    return dict(sorted(decades.items()))


async def compute_listening_consistency(
    db: AsyncSession, user_id: int, days: int = 30
) -> float:
    """Percentage of days with at least one play in the last N days. 0-100."""
    cutoff = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=days)
    result = await db.execute(
        select(func.count(distinct(func.date(RecentPlay.played_at)))).where(
            RecentPlay.user_id == user_id, RecentPlay.played_at >= cutoff
        )
    )
    active_days = result.scalar() or 0
    return round((active_days / days) * 100, 1)


async def compute_profile_metrics(
    db: AsyncSession, client: SpotifyClient, user_id: int
) -> dict:
    """Compute all profile metrics. Returns dict with all fields."""
    # Parallel fetch from Spotify — Semaphore(2) for dev mode burst protection
    sem = asyncio.Semaphore(2)

    async def _sem_fetch(label, coro):
        async with sem:
            return await _safe_fetch(label, coro)

    artists_short, artists_long, tracks_long = await asyncio.gather(
        _sem_fetch(
            "artists_short",
            retry_with_backoff(
                client.get_top_artists, time_range="short_term", limit=50
            ),
        ),
        _sem_fetch(
            "artists_long",
            retry_with_backoff(
                client.get_top_artists, time_range="long_term", limit=50
            ),
        ),
        _sem_fetch(
            "tracks_long",
            retry_with_backoff(client.get_top_tracks, time_range="long_term", limit=50),
        ),
    )

    all_artists = artists_long.get("items", []) or artists_short.get("items", [])
    all_tracks = tracks_long.get("items", [])

    # Compute scores
    obscurity = compute_obscurity_score(all_artists)
    diversity = compute_genre_diversity(all_artists)
    loyalty = await compute_artist_loyalty(db, user_id)
    consistency = await compute_listening_consistency(db, user_id)
    decades = compute_decade_distribution(all_tracks)

    # Top genres
    genre_counter: Counter = Counter()
    for a in all_artists:
        for g in a.get("genres", []):
            genre_counter[g] += 1
    top_genres = [g for g, _ in genre_counter.most_common(10)]

    # Lifetime stats from DB
    total_plays = (
        await db.execute(
            select(func.count(RecentPlay.id)).where(RecentPlay.user_id == user_id)
        )
    ).scalar() or 0
    total_artists = (
        await db.execute(
            select(func.count(distinct(RecentPlay.artist_name))).where(
                RecentPlay.user_id == user_id
            )
        )
    ).scalar() or 0
    total_tracks = (
        await db.execute(
            select(func.count(distinct(RecentPlay.track_spotify_id))).where(
                RecentPlay.user_id == user_id
            )
        )
    ).scalar() or 0

    # Upsert UserProfileMetrics — dedicated session to avoid corrupting
    # the request-scoped session on failure
    metrics_data = {
        "obscurity_score": obscurity,
        "genre_diversity_index": diversity,
        "artist_loyalty_score": loyalty,
        "listening_consistency": consistency,
        "total_plays_lifetime": total_plays,
        "total_artists_lifetime": total_artists,
        "total_tracks_lifetime": total_tracks,
        "top_genres_json": json.dumps(top_genres, ensure_ascii=False),
        "decade_distribution_json": json.dumps(decades, ensure_ascii=False),
        "updated_at": datetime.now(timezone.utc),
    }

    try:
        async with async_session() as write_db:
            existing = (
                await write_db.execute(
                    select(UserProfileMetrics).where(
                        UserProfileMetrics.user_id == user_id
                    )
                )
            ).scalar_one_or_none()

            if existing:
                for key, value in metrics_data.items():
                    setattr(existing, key, value)
            else:
                write_db.add(UserProfileMetrics(user_id=user_id, **metrics_data))

            await write_db.commit()
    except Exception as exc:
        logger.warning("Failed to save profile metrics: %s", exc)

    return {
        "obscurity_score": obscurity,
        "genre_diversity_index": diversity,
        "artist_loyalty_score": loyalty,
        "listening_consistency": consistency,
        "total_plays_lifetime": total_plays,
        "total_artists_lifetime": total_artists,
        "total_tracks_lifetime": total_tracks,
        "top_genres": top_genres,
        "decade_distribution": decades,
    }


async def compute_daily_stats(
    db: AsyncSession, user_id: int, target_date: date
) -> None:
    """Compute and save daily listening stats for a specific date."""
    start = datetime.combine(target_date, datetime.min.time())
    end = datetime.combine(target_date + timedelta(days=1), datetime.min.time())

    # Query plays for the day
    result = await db.execute(
        select(RecentPlay).where(
            RecentPlay.user_id == user_id,
            RecentPlay.played_at >= start,
            RecentPlay.played_at < end,
        )
    )
    plays = result.scalars().all()

    if not plays:
        return  # No plays for this day

    total_plays = len(plays)
    unique_tracks = len(set(p.track_spotify_id for p in plays))
    unique_artists = len(set(p.artist_name for p in plays))
    total_duration_ms = sum(p.duration_ms for p in plays)

    # Top genre: would need artist genre lookup, skip for now
    top_genre = None

    # Average popularity not available from RecentPlay
    avg_popularity = None

    # New artists/tracks: compare with all previous days
    prev_result = await db.execute(
        select(RecentPlay.artist_name, RecentPlay.track_spotify_id).where(
            RecentPlay.user_id == user_id, RecentPlay.played_at < start
        )
    )
    prev_artists = set()
    prev_tracks = set()
    for row in prev_result.all():
        prev_artists.add(row[0])
        prev_tracks.add(row[1])

    current_artists = set(p.artist_name for p in plays)
    current_tracks = set(p.track_spotify_id for p in plays)
    new_artists_count = len(current_artists - prev_artists)
    new_tracks_count = len(current_tracks - prev_tracks)

    # Upsert
    existing = (
        await db.execute(
            select(DailyListeningStats).where(
                DailyListeningStats.user_id == user_id,
                DailyListeningStats.date == target_date,
            )
        )
    ).scalar_one_or_none()

    stats_data = {
        "total_plays": total_plays,
        "unique_tracks": unique_tracks,
        "unique_artists": unique_artists,
        "total_duration_ms": total_duration_ms,
        "top_genre": top_genre,
        "avg_popularity": avg_popularity,
        "new_artists_count": new_artists_count,
        "new_tracks_count": new_tracks_count,
    }

    if existing:
        for key, value in stats_data.items():
            setattr(existing, key, value)
    else:
        db.add(DailyListeningStats(user_id=user_id, date=target_date, **stats_data))

    await db.commit()


async def get_recent_daily_stats(
    db: AsyncSession, user_id: int, days: int = 30
) -> list[dict]:
    """Get last N days of daily stats."""
    cutoff = date.today() - timedelta(days=days)
    result = await db.execute(
        select(DailyListeningStats)
        .where(
            DailyListeningStats.user_id == user_id,
            DailyListeningStats.date >= cutoff,
        )
        .order_by(DailyListeningStats.date.desc())
    )
    rows = result.scalars().all()
    return [
        {
            "date": str(r.date),
            "total_plays": r.total_plays,
            "unique_tracks": r.unique_tracks,
            "unique_artists": r.unique_artists,
            "total_duration_ms": r.total_duration_ms,
            "new_artists_count": r.new_artists_count,
            "new_tracks_count": r.new_tracks_count,
        }
        for r in rows
    ]
