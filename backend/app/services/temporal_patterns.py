"""Analisi dei pattern temporali di ascolto.

Accumula gli ascolti nel DB per superare il limite di 50 dell'API Spotify.
Ogni volta che viene chiamato, salva i nuovi ascolti e analizza l'intero storico.
"""

import logging
from collections import defaultdict
from datetime import datetime, timedelta

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.listening_history import RecentPlay
from app.services.spotify_client import SpotifyClient
from app.utils.rate_limiter import retry_with_backoff

logger = logging.getLogger(__name__)

DAY_LABELS = ["Lun", "Mar", "Mer", "Gio", "Ven", "Sab", "Dom"]


async def compute_temporal_patterns(
    client: SpotifyClient, db: AsyncSession = None, user_id: int = None
) -> dict:
    """Analizza i pattern temporali dai brani ascoltati di recente.

    Se db e user_id sono forniti, accumula gli ascolti nel DB per avere
    uno storico superiore ai 50 dell'API Spotify.
    """

    data = await retry_with_backoff(client.get_recently_played, limit=50)
    items = data.get("items", [])

    # Parse timestamps from Spotify API
    api_plays = []
    for item in items:
        played_at_str = item.get("played_at")
        if not played_at_str:
            continue
        dt = datetime.fromisoformat(played_at_str.replace("Z", "+00:00"))
        track = item.get("track", {})
        api_plays.append(
            {
                "datetime": dt,
                "weekday": dt.weekday(),
                "hour": dt.hour,
                "track_name": track.get("name", ""),
                "track_id": track.get("id", ""),
                "artist_name": (
                    track.get("artists", [{}])[0].get("name", "")
                    if track.get("artists")
                    else ""
                ),
                "duration_ms": track.get("duration_ms", 0),
            }
        )

    # Persist to DB if available (accumulate historical data)
    stored_count = 0
    if db and user_id and api_plays:
        stored_count = await _store_plays(db, user_id, api_plays)

    # Read accumulated plays from DB (if available, gives us more than 50)
    plays = api_plays
    if db and user_id:
        db_plays = await _load_plays(db, user_id)
        if db_plays and len(db_plays) > len(api_plays):
            plays = db_plays
            logger.info(
                "Temporal patterns: using %d accumulated plays (vs %d from API)",
                len(plays),
                len(api_plays),
            )

    if not plays:
        return _empty_result()

    plays.sort(key=lambda x: x["datetime"])

    # Heatmap: 7 days x 24 hours
    heatmap = [[0] * 24 for _ in range(7)]
    for play in plays:
        heatmap[play["weekday"]][play["hour"]] += 1

    # Session detection (gap > 30 min = new session)
    sessions = []
    current_session = [plays[0]] if plays else []

    for i in range(1, len(plays)):
        gap = abs((plays[i]["datetime"] - plays[i - 1]["datetime"]).total_seconds())
        if gap > 1800:
            sessions.append(current_session)
            current_session = [plays[i]]
        else:
            current_session.append(plays[i])
    if current_session:
        sessions.append(current_session)

    # Session durations in minutes
    session_durations = []
    for session in sessions:
        if len(session) > 1:
            duration_sec = abs(
                (session[-1]["datetime"] - session[0]["datetime"]).total_seconds()
            )
            duration_sec += session[-1]["duration_ms"] / 1000
            session_durations.append(duration_sec / 60)
        else:
            session_durations.append(session[0]["duration_ms"] / 60000)

    avg_session = (
        round(sum(session_durations) / len(session_durations), 1)
        if session_durations
        else 0
    )
    max_session = round(max(session_durations), 1) if session_durations else 0

    # Peak hours (top 3)
    hour_counts = defaultdict(int)
    for play in plays:
        hour_counts[play["hour"]] += 1
    peak_hours = sorted(hour_counts.items(), key=lambda x: x[1], reverse=True)[:3]

    # Weekend vs weekday
    weekday_plays = sum(1 for p in plays if p["weekday"] < 5)
    weekend_plays = sum(1 for p in plays if p["weekday"] >= 5)

    # Listening streak (consecutive days)
    unique_days = sorted(set(p["datetime"].date() for p in plays))
    max_streak = _compute_streak(unique_days)

    # Last 7 calendar days activity (Mon→Sun aligned with DAY_LABELS)
    today = datetime.now().date()
    unique_days_set = set(unique_days)
    active_last_7 = []
    for offset in range(6, -1, -1):  # 6 days ago → today
        day = today - timedelta(days=offset)
        active_last_7.append(day in unique_days_set)

    # Most played track
    track_counts = defaultdict(int)
    for play in plays:
        track_counts[play["track_name"]] += 1
    most_played = (
        max(track_counts.items(), key=lambda x: x[1]) if track_counts else ("", 0)
    )

    # Top 5 most played tracks
    top_tracks = sorted(track_counts.items(), key=lambda x: x[1], reverse=True)[:5]
    top_tracks_list = [{"name": name, "count": count} for name, count in top_tracks]

    return {
        "heatmap": {
            "data": heatmap,
            "day_labels": DAY_LABELS,
            "hour_labels": [f"{h:02d}" for h in range(24)],
        },
        "sessions": {
            "count": len(sessions),
            "avg_duration_minutes": avg_session,
            "longest_session_minutes": max_session,
            "avg_tracks_per_session": round(len(plays) / max(len(sessions), 1), 1),
        },
        "peak_hours": [{"hour": h, "count": c} for h, c in peak_hours],
        "patterns": {
            "weekday_plays": weekday_plays,
            "weekend_plays": weekend_plays,
            "weekday_pct": round(weekday_plays / len(plays) * 100, 1) if plays else 0,
        },
        "streak": {
            "max_streak": max_streak,
            "unique_days": len(unique_days),
            "active_last_7": active_last_7,
        },
        "most_played": {
            "track_name": most_played[0],
            "count": most_played[1],
        },
        "top_tracks": top_tracks_list,
        "total_plays": len(plays),
        "accumulated": len(plays) > len(api_plays),
        "new_plays_stored": stored_count,
    }


async def _store_plays(db: AsyncSession, user_id: int, plays: list[dict]) -> int:
    """Salva nuovi ascolti nel DB, ignorando duplicati."""
    stored = 0
    for play in plays:
        dt_naive = play["datetime"].replace(tzinfo=None)
        track_id = play.get("track_id", "")
        if not track_id:
            continue
        result = await db.execute(
            select(func.count(RecentPlay.id)).where(
                RecentPlay.user_id == user_id,
                RecentPlay.track_spotify_id == track_id,
                RecentPlay.played_at == dt_naive,
            )
        )
        if result.scalar() > 0:
            continue
        rp = RecentPlay(
            user_id=user_id,
            track_spotify_id=track_id,
            track_name=play["track_name"],
            artist_name=play["artist_name"],
            duration_ms=play["duration_ms"],
            played_at=dt_naive,
        )
        db.add(rp)
        stored += 1
    if stored > 0:
        try:
            await db.commit()
        except Exception as exc:
            logger.warning("Errore salvataggio ascolti: %s", exc)
            await db.rollback()
            stored = 0
    return stored


async def _load_plays(db: AsyncSession, user_id: int) -> list[dict]:
    """Carica tutti gli ascolti accumulati dal DB."""
    result = await db.execute(
        select(RecentPlay)
        .where(RecentPlay.user_id == user_id)
        .order_by(RecentPlay.played_at.asc())
    )
    rows = result.scalars().all()
    plays = []
    for r in rows:
        dt = r.played_at
        if dt.tzinfo is None:
            from datetime import timezone

            dt = dt.replace(tzinfo=timezone.utc)
        plays.append(
            {
                "datetime": dt,
                "weekday": dt.weekday(),
                "hour": dt.hour,
                "track_name": r.track_name,
                "track_id": r.track_spotify_id,
                "artist_name": r.artist_name,
                "duration_ms": r.duration_ms or 0,
            }
        )
    return plays


def _compute_streak(sorted_dates: list) -> int:
    """Calcola la streak massima di giorni consecutivi."""
    if not sorted_dates:
        return 0
    max_streak = 1
    current_streak = 1
    for i in range(1, len(sorted_dates)):
        diff = (sorted_dates[i] - sorted_dates[i - 1]).days
        if diff == 1:
            current_streak += 1
            max_streak = max(max_streak, current_streak)
        elif diff > 1:
            current_streak = 1
    return max_streak


def _empty_result():
    return {
        "heatmap": {
            "data": [[0] * 24 for _ in range(7)],
            "day_labels": DAY_LABELS,
            "hour_labels": [f"{h:02d}" for h in range(24)],
        },
        "sessions": {
            "count": 0,
            "avg_duration_minutes": 0,
            "longest_session_minutes": 0,
            "avg_tracks_per_session": 0,
        },
        "peak_hours": [],
        "patterns": {
            "weekday_plays": 0,
            "weekend_plays": 0,
            "weekday_pct": 0,
        },
        "streak": {"max_streak": 0, "unique_days": 0, "active_last_7": [False] * 7},
        "most_played": {"track_name": "", "count": 0},
        "top_tracks": [],
        "total_plays": 0,
        "accumulated": False,
        "new_plays_stored": 0,
    }
