"""Test della classifica costruita sugli ascolti registrati.

Copre le due cose che possono sbagliare in silenzio:
- il periodo "Tutto" non deve applicare nessun taglio temporale;
- le date lette dal DB senza fuso orario devono valere UTC, non l'ora locale.
"""

from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from app.routers.library import _PLAYED_DAYS_MAP, get_top_played


def _row(track_id: str, play_count: int, naive: bool = False) -> SimpleNamespace:
    when = datetime(2026, 3, 21, 8, 7, 31)
    return SimpleNamespace(
        track_spotify_id=track_id,
        track_name="First Time",
        artist_name="Lil Tjay",
        artist_spotify_id="art1",
        duration_ms=180000,
        total_ms=180000 * play_count,
        first_played_at=when if naive else when.replace(tzinfo=timezone.utc),
        last_played_at=when if naive else when.replace(tzinfo=timezone.utc),
        play_count=play_count,
    )


def _make_db(rows: list, totals: tuple[int, int]) -> AsyncMock:
    """DB finto che registra le query e risponde group-by prima, totali poi."""
    db = AsyncMock()
    db.statements = []

    grouped = AsyncMock()
    grouped.all = lambda: rows
    counted = AsyncMock()
    counted.one = lambda: totals

    async def _execute(stmt):
        db.statements.append(str(stmt))
        return grouped if len(db.statements) == 1 else counted

    db.execute = _execute
    return db


class TestTopPlayed:
    @pytest.mark.asyncio
    async def test_counts_plays_and_reports_totals(self):
        db = _make_db([_row("t1", 44), _row("t2", 19)], (372, 639))

        with (
            patch(
                "app.routers.library.read_popularity_cache", AsyncMock(return_value=0)
            ),
            patch(
                "app.routers.library.get_or_fetch_features", AsyncMock(return_value={})
            ),
            patch(
                "app.routers.library.get_first_play_date",
                AsyncMock(return_value="2026-03-02"),
            ),
        ):
            result = await get_top_played(range="all", limit=50, user_id=1, db=db)

        assert [t["play_count"] for t in result["tracks"]] == [44, 19]
        assert result["total"] == 372
        assert result["total_plays"] == 639
        assert result["first_play_date"] == "2026-03-02"

    @pytest.mark.asyncio
    async def test_all_applies_no_time_cut(self):
        """ "Tutto" deve leggere lo storico intero: nessun filtro sulla data."""
        assert _PLAYED_DAYS_MAP["all"] is None

        with (
            patch(
                "app.routers.library.read_popularity_cache", AsyncMock(return_value=0)
            ),
            patch(
                "app.routers.library.get_or_fetch_features", AsyncMock(return_value={})
            ),
            patch(
                "app.routers.library.get_first_play_date", AsyncMock(return_value=None)
            ),
        ):
            db_all = _make_db([], (0, 0))
            await get_top_played(range="all", limit=50, user_id=1, db=db_all)

            db_week = _make_db([], (0, 0))
            await get_top_played(range="7d", limit=50, user_id=1, db=db_week)

        assert "played_at >=" not in db_all.statements[0]
        assert "played_at >=" in db_week.statements[0]

    @pytest.mark.asyncio
    async def test_naive_datetimes_are_read_as_utc(self):
        db = _make_db([_row("t1", 3, naive=True)], (1, 3))

        with (
            patch(
                "app.routers.library.read_popularity_cache", AsyncMock(return_value=0)
            ),
            patch(
                "app.routers.library.get_or_fetch_features", AsyncMock(return_value={})
            ),
            patch(
                "app.routers.library.get_first_play_date", AsyncMock(return_value=None)
            ),
        ):
            result = await get_top_played(range="30d", limit=50, user_id=1, db=db)

        assert result["tracks"][0]["last_played_at"].endswith("+00:00")

    @pytest.mark.asyncio
    async def test_features_from_cache_are_attached(self):
        db = _make_db([_row("t1", 2)], (1, 2))
        features = {"t1": {"energy": 0.8, "valence": 0.4}}

        with (
            patch(
                "app.routers.library.read_popularity_cache", AsyncMock(return_value=0)
            ),
            patch(
                "app.routers.library.get_or_fetch_features",
                AsyncMock(return_value=features),
            ),
            patch(
                "app.routers.library.get_first_play_date", AsyncMock(return_value=None)
            ),
        ):
            result = await get_top_played(range="30d", limit=50, user_id=1, db=db)

        assert result["tracks"][0]["features"]["energy"] == 0.8
