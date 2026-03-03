"""Analisi dei pattern temporali di ascolto."""

from collections import defaultdict
from datetime import datetime

from app.services.spotify_client import SpotifyClient
from app.utils.rate_limiter import retry_with_backoff

DAY_LABELS = ["Lun", "Mar", "Mer", "Gio", "Ven", "Sab", "Dom"]


async def compute_temporal_patterns(client: SpotifyClient) -> dict:
    """Analizza i pattern temporali dai brani ascoltati di recente."""

    data = await retry_with_backoff(client.get_recently_played, limit=50)
    items = data.get("items", [])

    if not items:
        return _empty_result()

    # Parse timestamps
    plays = []
    for item in items:
        played_at_str = item.get("played_at")
        if not played_at_str:
            continue
        dt = datetime.fromisoformat(played_at_str.replace("Z", "+00:00"))
        track = item.get("track", {})
        plays.append({
            "datetime": dt,
            "weekday": dt.weekday(),  # 0=Monday
            "hour": dt.hour,
            "track_name": track.get("name", ""),
            "artist_name": (track.get("artists", [{}])[0].get("name", "")
                           if track.get("artists") else ""),
            "duration_ms": track.get("duration_ms", 180000),
        })

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
        if gap > 1800:  # 30 minutes
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

    # Most played track
    track_counts = defaultdict(int)
    for play in plays:
        track_counts[play["track_name"]] += 1
    most_played = max(track_counts.items(), key=lambda x: x[1]) if track_counts else ("", 0)

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
        },
        "most_played": {
            "track_name": most_played[0],
            "count": most_played[1],
        },
        "total_plays": len(plays),
    }


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
        "streak": {"max_streak": 0, "unique_days": 0},
        "most_played": {"track_name": "", "count": 0},
        "total_plays": 0,
    }
