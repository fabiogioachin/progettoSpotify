"""Tests for temporal_patterns.py — streak calculation, hourly/weekday bucketing,
daily minutes, DB fallback, empty data, and first_play_date.

Covers:
- Output structure has expected keys
- Streak calculation with consecutive days
- Streak breaks on gaps
- Daily minutes from duration_ms
- Hourly distribution (24-hour bucketing)
- Day-of-week bucketing (7 days)
- DB fallback when accumulated plays > API plays
- API-only mode when db is None
- Empty data returns graceful empty result
- get_first_play_date returns formatted date
- get_first_play_date returns None when no plays
- _compute_streak pure function edge cases
"""

from datetime import datetime, date, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.temporal_patterns import (
    _compute_streak,
    _empty_result,
    compute_temporal_patterns,
    get_first_play_date,
    DAY_LABELS,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_api_item(played_at: datetime, track_name: str = "Track",
                   track_id: str = "tid", artist_name: str = "Artist",
                   duration_ms: int = 210000) -> dict:
    """Build a Spotify recently-played item dict."""
    return {
        "played_at": played_at.isoformat(),
        "track": {
            "name": track_name,
            "id": track_id,
            "artists": [{"name": artist_name}],
            "duration_ms": duration_ms,
        },
    }


def _make_items(base: datetime, count: int, gap_minutes: int = 5,
                duration_ms: int = 210000) -> list[dict]:
    """Generate a list of API items spaced `gap_minutes` apart."""
    items = []
    for i in range(count):
        dt = base + timedelta(minutes=i * gap_minutes)
        items.append(_make_api_item(
            dt,
            track_name=f"Track {i}",
            track_id=f"tid_{i}",
            duration_ms=duration_ms,
        ))
    return items


def _mock_client(items: list[dict]) -> MagicMock:
    """Return a MagicMock SpotifyClient whose get_recently_played returns items."""
    client = MagicMock()
    client.get_recently_played = AsyncMock(return_value={"items": items})
    return client


async def _passthrough_retry(fn, **kw):
    """Stand-in for retry_with_backoff that just awaits the function."""
    return await fn(**kw)


# ---------------------------------------------------------------------------
# _compute_streak (pure function)
# ---------------------------------------------------------------------------

class TestComputeStreak:
    def test_empty_dates(self):
        assert _compute_streak([]) == 0

    def test_single_day(self):
        assert _compute_streak([date(2026, 3, 1)]) == 1

    def test_consecutive_days(self):
        dates = [date(2026, 3, 1) + timedelta(days=i) for i in range(5)]
        assert _compute_streak(dates) == 5

    def test_gap_breaks_streak(self):
        dates = [
            date(2026, 3, 1),
            date(2026, 3, 2),
            date(2026, 3, 3),
            # gap
            date(2026, 3, 6),
            date(2026, 3, 7),
        ]
        assert _compute_streak(dates) == 3  # first run of 3

    def test_second_run_longer(self):
        dates = [
            date(2026, 3, 1),
            date(2026, 3, 2),
            # gap
            date(2026, 3, 5),
            date(2026, 3, 6),
            date(2026, 3, 7),
            date(2026, 3, 8),
        ]
        assert _compute_streak(dates) == 4  # second run of 4

    def test_duplicate_dates_no_crash(self):
        dates = [date(2026, 3, 1), date(2026, 3, 1)]
        # same day repeated — diff==0, not consecutive
        assert _compute_streak(dates) == 1


# ---------------------------------------------------------------------------
# _empty_result
# ---------------------------------------------------------------------------

class TestEmptyResult:
    def test_structure(self):
        r = _empty_result()
        assert r["total_plays"] == 0
        assert r["streak"]["max_streak"] == 0
        assert r["streak"]["unique_days"] == 0
        assert r["streak"]["active_last_7"] == [False] * 7
        assert len(r["heatmap"]["data"]) == 7
        assert all(len(row) == 24 for row in r["heatmap"]["data"])
        assert r["sessions"]["count"] == 0
        assert r["peak_hours"] == []
        assert r["daily_minutes"] == []
        assert r["most_played"]["track_name"] == ""
        assert r["most_played"]["count"] == 0


# ---------------------------------------------------------------------------
# compute_temporal_patterns — output structure
# ---------------------------------------------------------------------------

class TestOutputStructure:
    @pytest.mark.asyncio
    async def test_all_expected_keys_present(self):
        """Return dict has all documented top-level keys."""
        now = datetime.now(timezone.utc)
        items = _make_items(now - timedelta(hours=1), count=3)
        client = _mock_client(items)

        with patch("app.services.temporal_patterns.retry_with_backoff",
                    side_effect=_passthrough_retry):
            result = await compute_temporal_patterns(client, db=None)

        expected_keys = {
            "heatmap", "sessions", "peak_hours", "patterns", "streak",
            "most_played", "top_tracks", "total_plays", "accumulated",
            "new_plays_stored", "daily_minutes", "first_play_date",
        }
        assert expected_keys == set(result.keys())

    @pytest.mark.asyncio
    async def test_heatmap_shape(self):
        """Heatmap has 7 rows x 24 cols, with correct labels."""
        now = datetime.now(timezone.utc)
        items = _make_items(now - timedelta(hours=1), count=2)
        client = _mock_client(items)

        with patch("app.services.temporal_patterns.retry_with_backoff",
                    side_effect=_passthrough_retry):
            result = await compute_temporal_patterns(client, db=None)

        hm = result["heatmap"]
        assert len(hm["data"]) == 7
        assert all(len(row) == 24 for row in hm["data"])
        assert hm["day_labels"] == DAY_LABELS
        assert len(hm["hour_labels"]) == 24


# ---------------------------------------------------------------------------
# Hourly distribution
# ---------------------------------------------------------------------------

class TestHourlyDistribution:
    @pytest.mark.asyncio
    async def test_plays_bucketed_to_correct_hour(self):
        """Plays at hour 14 and 15 end up in the correct heatmap columns."""
        base = datetime(2026, 3, 25, 14, 0, tzinfo=timezone.utc)  # Wednesday
        items = [
            _make_api_item(base, track_id="a"),
            _make_api_item(base + timedelta(minutes=5), track_id="b"),
            _make_api_item(base + timedelta(hours=1), track_id="c"),
        ]
        client = _mock_client(items)

        with patch("app.services.temporal_patterns.retry_with_backoff",
                    side_effect=_passthrough_retry):
            result = await compute_temporal_patterns(client, db=None)

        hm = result["heatmap"]["data"]
        weekday = base.weekday()  # Wednesday = 2
        assert hm[weekday][14] == 2  # two plays at hour 14
        assert hm[weekday][15] == 1  # one play at hour 15


# ---------------------------------------------------------------------------
# Day-of-week bucketing
# ---------------------------------------------------------------------------

class TestDayOfWeekBucketing:
    @pytest.mark.asyncio
    async def test_weekday_vs_weekend_counts(self):
        """Plays on a Wednesday are weekday; plays on Saturday are weekend."""
        wed = datetime(2026, 3, 25, 10, 0, tzinfo=timezone.utc)  # Wednesday
        sat = datetime(2026, 3, 28, 10, 0, tzinfo=timezone.utc)  # Saturday
        items = [
            _make_api_item(wed, track_id="a"),
            _make_api_item(wed + timedelta(minutes=5), track_id="b"),
            _make_api_item(sat, track_id="c"),
        ]
        client = _mock_client(items)

        with patch("app.services.temporal_patterns.retry_with_backoff",
                    side_effect=_passthrough_retry):
            result = await compute_temporal_patterns(client, db=None)

        assert result["patterns"]["weekday_plays"] == 2
        assert result["patterns"]["weekend_plays"] == 1


# ---------------------------------------------------------------------------
# Streak in full pipeline
# ---------------------------------------------------------------------------

class TestStreakInPipeline:
    @pytest.mark.asyncio
    async def test_consecutive_days_streak(self):
        """3 plays on 3 consecutive days → max_streak=3."""
        base = datetime(2026, 3, 25, 10, 0, tzinfo=timezone.utc)
        items = [
            _make_api_item(base, track_id="a"),
            _make_api_item(base + timedelta(days=1), track_id="b"),
            _make_api_item(base + timedelta(days=2), track_id="c"),
        ]
        client = _mock_client(items)

        with patch("app.services.temporal_patterns.retry_with_backoff",
                    side_effect=_passthrough_retry):
            result = await compute_temporal_patterns(client, db=None)

        assert result["streak"]["max_streak"] == 3
        assert result["streak"]["unique_days"] == 3

    @pytest.mark.asyncio
    async def test_gap_in_streak(self):
        """Plays on day 1, 2, then day 5 → max_streak=2."""
        base = datetime(2026, 3, 25, 10, 0, tzinfo=timezone.utc)
        items = [
            _make_api_item(base, track_id="a"),
            _make_api_item(base + timedelta(days=1), track_id="b"),
            _make_api_item(base + timedelta(days=4), track_id="c"),
        ]
        client = _mock_client(items)

        with patch("app.services.temporal_patterns.retry_with_backoff",
                    side_effect=_passthrough_retry):
            result = await compute_temporal_patterns(client, db=None)

        assert result["streak"]["max_streak"] == 2


# ---------------------------------------------------------------------------
# Daily minutes
# ---------------------------------------------------------------------------

class TestDailyMinutes:
    @pytest.mark.asyncio
    async def test_daily_minutes_empty_without_db(self):
        """Without DB, daily_minutes is an empty list."""
        now = datetime.now(timezone.utc)
        items = _make_items(now - timedelta(hours=1), count=3, duration_ms=180000)
        client = _mock_client(items)

        with patch("app.services.temporal_patterns.retry_with_backoff",
                    side_effect=_passthrough_retry):
            result = await compute_temporal_patterns(client, db=None)

        # daily_minutes requires DB
        assert result["daily_minutes"] == []


# ---------------------------------------------------------------------------
# Empty data
# ---------------------------------------------------------------------------

class TestEmptyData:
    @pytest.mark.asyncio
    async def test_no_plays_returns_empty_result(self):
        """When API returns no items, result matches _empty_result structure."""
        client = _mock_client([])

        with patch("app.services.temporal_patterns.retry_with_backoff",
                    side_effect=_passthrough_retry):
            result = await compute_temporal_patterns(client, db=None)

        assert result["total_plays"] == 0
        assert result["streak"]["max_streak"] == 0
        assert result["sessions"]["count"] == 0
        assert result["peak_hours"] == []
        assert result["most_played"]["track_name"] == ""


# ---------------------------------------------------------------------------
# DB fallback — accumulated plays > API plays
# ---------------------------------------------------------------------------

class TestDBFallback:
    @pytest.mark.asyncio
    async def test_uses_db_plays_when_more_than_api(self):
        """When DB has more plays than API, accumulated=True."""
        now = datetime.now(timezone.utc)
        api_items = _make_items(now - timedelta(hours=1), count=3)
        client = _mock_client(api_items)

        # DB returns more plays than API
        db_plays = [
            {
                "datetime": now - timedelta(days=i, hours=2),
                "weekday": (now - timedelta(days=i, hours=2)).weekday(),
                "hour": (now - timedelta(days=i, hours=2)).hour,
                "track_name": f"DB Track {i}",
                "track_id": f"db_tid_{i}",
                "artist_name": "DB Artist",
                "duration_ms": 200000,
            }
            for i in range(10)
        ]

        mock_db = AsyncMock()

        with (
            patch("app.services.temporal_patterns.retry_with_backoff",
                  side_effect=_passthrough_retry),
            patch("app.services.temporal_patterns._store_plays",
                  new_callable=AsyncMock, return_value=0),
            patch("app.services.temporal_patterns.get_first_play_date",
                  new_callable=AsyncMock, return_value="01/03/2026"),
            patch("app.services.temporal_patterns._load_plays",
                  new_callable=AsyncMock, return_value=db_plays),
            patch("app.services.temporal_patterns._compute_daily_minutes",
                  new_callable=AsyncMock, return_value=[]),
        ):
            result = await compute_temporal_patterns(
                client, db=mock_db, user_id=1
            )

        assert result["accumulated"] is True
        assert result["total_plays"] <= 10  # uses DB plays (filtered by days cutoff)
        assert result["first_play_date"] == "01/03/2026"

    @pytest.mark.asyncio
    async def test_api_only_when_db_none(self):
        """When db=None, only API plays are used and accumulated=False."""
        now = datetime.now(timezone.utc)
        items = _make_items(now - timedelta(hours=1), count=5)
        client = _mock_client(items)

        with patch("app.services.temporal_patterns.retry_with_backoff",
                    side_effect=_passthrough_retry):
            result = await compute_temporal_patterns(client, db=None)

        assert result["accumulated"] is False
        assert result["total_plays"] == 5
        assert result["first_play_date"] is None

    @pytest.mark.asyncio
    async def test_api_used_when_db_has_fewer_plays(self):
        """When DB has fewer plays than API, API plays are used."""
        now = datetime.now(timezone.utc)
        api_items = _make_items(now - timedelta(hours=1), count=5)
        client = _mock_client(api_items)

        # DB returns fewer plays than API
        db_plays = [
            {
                "datetime": now - timedelta(hours=2),
                "weekday": (now - timedelta(hours=2)).weekday(),
                "hour": (now - timedelta(hours=2)).hour,
                "track_name": "DB Track",
                "track_id": "db_tid",
                "artist_name": "DB Artist",
                "duration_ms": 200000,
            }
        ]

        mock_db = AsyncMock()

        with (
            patch("app.services.temporal_patterns.retry_with_backoff",
                  side_effect=_passthrough_retry),
            patch("app.services.temporal_patterns._store_plays",
                  new_callable=AsyncMock, return_value=0),
            patch("app.services.temporal_patterns.get_first_play_date",
                  new_callable=AsyncMock, return_value=None),
            patch("app.services.temporal_patterns._load_plays",
                  new_callable=AsyncMock, return_value=db_plays),
            patch("app.services.temporal_patterns._compute_daily_minutes",
                  new_callable=AsyncMock, return_value=[]),
        ):
            result = await compute_temporal_patterns(
                client, db=mock_db, user_id=1
            )

        assert result["accumulated"] is False
        assert result["total_plays"] == 5


# ---------------------------------------------------------------------------
# get_first_play_date
# ---------------------------------------------------------------------------

class TestGetFirstPlayDate:
    @pytest.mark.asyncio
    async def test_returns_formatted_date(self):
        """Returns earliest play date as dd/mm/yyyy."""
        mock_db = AsyncMock()
        earliest = datetime(2025, 6, 15, 10, 30, tzinfo=timezone.utc)

        # Mock the db.execute chain: result.scalar() returns the datetime
        mock_result = MagicMock()
        mock_result.scalar.return_value = earliest
        mock_db.execute.return_value = mock_result

        result = await get_first_play_date(mock_db, user_id=1)
        assert result == "15/06/2025"

    @pytest.mark.asyncio
    async def test_returns_none_when_no_plays(self):
        """Returns None when no plays exist."""
        mock_db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar.return_value = None
        mock_db.execute.return_value = mock_result

        result = await get_first_play_date(mock_db, user_id=1)
        assert result is None

    @pytest.mark.asyncio
    async def test_handles_naive_datetime(self):
        """Adds UTC tzinfo if the stored datetime is naive."""
        mock_db = AsyncMock()
        earliest = datetime(2025, 6, 15, 10, 30)  # no tzinfo

        mock_result = MagicMock()
        mock_result.scalar.return_value = earliest
        mock_db.execute.return_value = mock_result

        result = await get_first_play_date(mock_db, user_id=1)
        assert result == "15/06/2025"


# ---------------------------------------------------------------------------
# Most played track
# ---------------------------------------------------------------------------

class TestMostPlayedTrack:
    @pytest.mark.asyncio
    async def test_most_played_track_identified(self):
        """Track played the most times is reported correctly."""
        now = datetime.now(timezone.utc)
        items = [
            _make_api_item(now - timedelta(minutes=30), track_name="Song A", track_id="a"),
            _make_api_item(now - timedelta(minutes=25), track_name="Song A", track_id="a"),
            _make_api_item(now - timedelta(minutes=20), track_name="Song A", track_id="a"),
            _make_api_item(now - timedelta(minutes=15), track_name="Song B", track_id="b"),
        ]
        client = _mock_client(items)

        with patch("app.services.temporal_patterns.retry_with_backoff",
                    side_effect=_passthrough_retry):
            result = await compute_temporal_patterns(client, db=None)

        assert result["most_played"]["track_name"] == "Song A"
        assert result["most_played"]["count"] == 3
        assert len(result["top_tracks"]) == 2
