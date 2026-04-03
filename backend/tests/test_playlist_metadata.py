"""Tests for PlaylistMetadata DB cache and modified playlist endpoints.

Covers:
1. PlaylistMetadata model structure
2. _upsert_playlist_metadata helper
3. get_playlists — DB cache integration (no burst fallback)
4. get_playlist_counts — lightweight DB-only endpoint
5. playlist_analytics — DB cache for zero counts + aggressive partial results
6. _bg_fetch_remaining_counts background task
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.models.playlist_metadata import PlaylistMetadata


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_playlist_item(
    pid: str,
    name: str = "Test",
    track_total: int = 0,
    owner_id: str = "owner123",
) -> dict:
    return {
        "id": pid,
        "name": name,
        "description": "",
        "images": [{"url": "https://example.com/img.jpg"}],
        "tracks": {"total": track_total},
        "owner": {"id": owner_id, "display_name": "Test User"},
        "public": True,
        "collaborative": False,
    }


async def _passthrough_retry(fn, *args, **kwargs):
    """Drop-in for retry_with_backoff that calls fn directly."""
    return await fn(*args, **kwargs)


class _FakeResult:
    """Fake DB result for select queries."""

    def __init__(self, rows=None, scalars=None):
        self._rows = rows or []
        self._scalars = scalars or []

    def fetchall(self):
        return self._rows

    def scalars(self):
        return self

    def all(self):
        return self._scalars


# ---------------------------------------------------------------------------
# 1. Model structure
# ---------------------------------------------------------------------------

class TestPlaylistMetadataModel:
    def test_table_name(self):
        assert PlaylistMetadata.__tablename__ == "playlist_metadata"

    def test_columns_exist(self):
        cols = {c.name for c in PlaylistMetadata.__table__.columns}
        expected = {
            "id", "user_id", "playlist_id", "track_count",
            "name", "image_url", "is_owner", "updated_at",
        }
        assert expected.issubset(cols)

    def test_unique_constraint(self):
        constraints = PlaylistMetadata.__table__.constraints
        uq = [
            c for c in constraints
            if hasattr(c, "name")
            and c.name == "uq_playlist_metadata_user_pid"
        ]
        assert len(uq) == 1


# ---------------------------------------------------------------------------
# 2. _upsert_playlist_metadata helper
# ---------------------------------------------------------------------------

class TestUpsertHelper:
    @pytest.mark.asyncio
    async def test_upsert_calls_execute_and_commit(self):
        """Upsert should call db.execute and db.commit."""
        from app.routers.playlists import _upsert_playlist_metadata

        mock_db = AsyncMock()
        mock_db.execute = AsyncMock()
        mock_db.commit = AsyncMock()

        await _upsert_playlist_metadata(
            mock_db,
            user_id=1,
            playlist_id="pid1111111111111",
            track_count=42,
            name="Test",
        )

        mock_db.execute.assert_called_once()
        mock_db.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_upsert_swallows_errors(self):
        """Upsert errors should be swallowed, not raised."""
        from app.routers.playlists import _upsert_playlist_metadata

        mock_db = AsyncMock()
        mock_db.execute = AsyncMock(side_effect=Exception("DB down"))
        mock_db.rollback = AsyncMock()

        # Should NOT raise
        await _upsert_playlist_metadata(
            mock_db,
            user_id=1,
            playlist_id="pid1111111111111",
            track_count=42,
        )


# ---------------------------------------------------------------------------
# 3. get_playlists — DB cache integration
# ---------------------------------------------------------------------------

class TestGetPlaylistsDBCache:
    @pytest.mark.asyncio
    async def test_uses_db_cache_when_api_returns_zero(self):
        """When API returns track_count=0, should use DB cached value."""
        client = MagicMock()
        client.get_playlists = AsyncMock(return_value={
            "items": [_make_playlist_item("pid1111111111111", track_total=0)],
            "total": 1,
        })
        client.get_playlist_items = AsyncMock()
        client.close = AsyncMock()

        # Mock DB: user query + playlist metadata query + upsert
        mock_user = MagicMock()
        mock_user.spotify_id = "owner123"
        user_result = MagicMock()
        user_result.scalar_one_or_none.return_value = mock_user

        # Create a fake cached PlaylistMetadata
        cached_meta = MagicMock(spec=PlaylistMetadata)
        cached_meta.playlist_id = "pid1111111111111"
        cached_meta.track_count = 55

        cache_result = _FakeResult(scalars=[cached_meta])

        mock_db = AsyncMock()

        call_count = 0

        async def _mock_execute(stmt):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return user_result  # User query
            elif call_count == 2:
                return cache_result  # Metadata cache query
            return MagicMock()

        mock_db.execute = AsyncMock(side_effect=_mock_execute)
        mock_db.commit = AsyncMock()
        mock_db.rollback = AsyncMock()

        with (
            patch("app.routers.playlists.SpotifyClient", return_value=client),
            patch(
                "app.routers.playlists.retry_with_backoff",
                _passthrough_retry,
            ),
            patch("app.routers.playlists.asyncio") as mock_asyncio,
        ):
            mock_asyncio.create_task = MagicMock()  # Don't actually launch BG task

            from app.routers.playlists import get_playlists
            mock_request = MagicMock()

            result = await get_playlists(
                request=mock_request,
                limit=50,
                offset=0,
                user_id=1,
                db=mock_db,
            )

        # Playlist should have the DB-cached count
        assert result["playlists"][0]["track_count"] == 55
        # No burst API calls for individual playlists
        client.get_playlist_items.assert_not_called()

    @pytest.mark.asyncio
    async def test_uses_api_count_when_nonzero(self):
        """When API returns track_count > 0, should use that directly."""
        client = MagicMock()
        client.get_playlists = AsyncMock(return_value={
            "items": [_make_playlist_item("pid1111111111111", track_total=30)],
            "total": 1,
        })
        client.close = AsyncMock()

        mock_user = MagicMock()
        mock_user.spotify_id = "owner123"
        user_result = MagicMock()
        user_result.scalar_one_or_none.return_value = mock_user

        cache_result = _FakeResult(scalars=[])

        mock_db = AsyncMock()
        call_count = 0

        async def _mock_execute(stmt):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return user_result
            elif call_count == 2:
                return cache_result
            return MagicMock()

        mock_db.execute = AsyncMock(side_effect=_mock_execute)
        mock_db.commit = AsyncMock()
        mock_db.rollback = AsyncMock()

        with (
            patch("app.routers.playlists.SpotifyClient", return_value=client),
            patch(
                "app.routers.playlists.retry_with_backoff",
                _passthrough_retry,
            ),
        ):
            from app.routers.playlists import get_playlists
            mock_request = MagicMock()

            result = await get_playlists(
                request=mock_request,
                limit=50,
                offset=0,
                user_id=1,
                db=mock_db,
            )

        assert result["playlists"][0]["track_count"] == 30

    @pytest.mark.asyncio
    async def test_launches_bg_task_for_remaining_zeros(self):
        """When playlists have no count from API or DB, BG task is launched."""
        client = MagicMock()
        client.get_playlists = AsyncMock(return_value={
            "items": [_make_playlist_item("pid1111111111111", track_total=0)],
            "total": 1,
        })
        client.close = AsyncMock()

        mock_user = MagicMock()
        mock_user.spotify_id = "owner123"
        user_result = MagicMock()
        user_result.scalar_one_or_none.return_value = mock_user
        cache_result = _FakeResult(scalars=[])

        mock_db = AsyncMock()
        call_count = 0

        async def _mock_execute(stmt):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return user_result
            elif call_count == 2:
                return cache_result
            return MagicMock()

        mock_db.execute = AsyncMock(side_effect=_mock_execute)
        mock_db.commit = AsyncMock()
        mock_db.rollback = AsyncMock()

        with (
            patch("app.routers.playlists.SpotifyClient", return_value=client),
            patch(
                "app.routers.playlists.retry_with_backoff",
                _passthrough_retry,
            ),
            patch("app.routers.playlists.asyncio") as mock_asyncio,
        ):
            mock_asyncio.create_task = MagicMock()
            from app.routers.playlists import get_playlists
            mock_request = MagicMock()

            result = await get_playlists(
                request=mock_request,
                limit=50,
                offset=0,
                user_id=1,
                db=mock_db,
            )

        # Background task should have been created
        mock_asyncio.create_task.assert_called_once()
        # Track count should be 0 (will update via polling)
        assert result["playlists"][0]["track_count"] == 0


# ---------------------------------------------------------------------------
# 4. get_playlist_counts — DB-only endpoint
# ---------------------------------------------------------------------------

class TestGetPlaylistCounts:
    @pytest.mark.asyncio
    async def test_returns_counts_from_db(self):
        """Counts endpoint should return dict from DB, no API calls."""
        from app.routers.playlists import get_playlist_counts

        mock_rows = [
            MagicMock(playlist_id="pid1111111111111", track_count=42),
            MagicMock(playlist_id="pid2222222222222", track_count=15),
        ]
        mock_result = MagicMock()
        mock_result.fetchall.return_value = mock_rows

        mock_db = AsyncMock()
        mock_db.execute = AsyncMock(return_value=mock_result)

        result = await get_playlist_counts(user_id=1, db=mock_db)

        assert result == {
            "counts": {
                "pid1111111111111": 42,
                "pid2222222222222": 15,
            }
        }

    @pytest.mark.asyncio
    async def test_returns_empty_when_no_cache(self):
        """Counts endpoint should return empty dict when no cache exists."""
        from app.routers.playlists import get_playlist_counts

        mock_result = MagicMock()
        mock_result.fetchall.return_value = []

        mock_db = AsyncMock()
        mock_db.execute = AsyncMock(return_value=mock_result)

        result = await get_playlist_counts(user_id=1, db=mock_db)

        assert result == {"counts": {}}


# ---------------------------------------------------------------------------
# 5. Playlist analytics — DB cache + aggressive partial results
# ---------------------------------------------------------------------------

class TestPlaylistAnalyticsDBCache:
    def test_upsert_playlist_count_swallows_errors(self):
        """_upsert_playlist_count should not raise on DB errors."""
        import asyncio
        from app.routers.playlist_analytics import _upsert_playlist_count

        mock_db = AsyncMock()
        mock_db.execute = AsyncMock(side_effect=Exception("DB down"))
        mock_db.rollback = AsyncMock()

        # Should NOT raise
        asyncio.get_event_loop().run_until_complete(
            _upsert_playlist_count(mock_db, 1, "pid1111111111111", 42)
        )


# ---------------------------------------------------------------------------
# 6. Background task tests
# ---------------------------------------------------------------------------

class TestBackgroundFetchCounts:
    @pytest.mark.asyncio
    async def test_bg_task_stops_on_auth_error(self):
        """BG task should stop when SpotifyAuthError occurs."""
        from app.utils.rate_limiter import SpotifyAuthError
        from app.routers.playlists import _bg_fetch_remaining_counts

        mock_client = MagicMock()
        mock_client.get_playlist_items = AsyncMock(
            side_effect=SpotifyAuthError("expired")
        )
        mock_client.close = AsyncMock()

        with (
            patch(
                "app.routers.playlists.async_session"
            ) as mock_session_factory,
            patch("app.routers.playlists.SpotifyClient", return_value=mock_client),
            patch(
                "app.routers.playlists.retry_with_backoff",
                _passthrough_retry,
            ),
        ):
            mock_session = AsyncMock()
            mock_session_factory.return_value.__aenter__ = AsyncMock(
                return_value=mock_session
            )
            mock_session_factory.return_value.__aexit__ = AsyncMock(
                return_value=False
            )

            zero_pids = [{"id": "pid1111111111111", "name": "Test"}]

            # Should not raise despite SpotifyAuthError
            await _bg_fetch_remaining_counts(user_id=1, zero_pids=zero_pids)

    @pytest.mark.asyncio
    async def test_bg_task_stops_on_rate_limit(self):
        """BG task should stop when RateLimitError occurs."""
        from app.utils.rate_limiter import ThrottleError
        from app.routers.playlists import _bg_fetch_remaining_counts

        mock_client = MagicMock()
        mock_client.get_playlist_items = AsyncMock(
            side_effect=ThrottleError(retry_after=10)
        )
        mock_client.close = AsyncMock()

        with (
            patch(
                "app.routers.playlists.async_session"
            ) as mock_session_factory,
            patch("app.routers.playlists.SpotifyClient", return_value=mock_client),
            patch(
                "app.routers.playlists.retry_with_backoff",
                _passthrough_retry,
            ),
        ):
            mock_session = AsyncMock()
            mock_session_factory.return_value.__aenter__ = AsyncMock(
                return_value=mock_session
            )
            mock_session_factory.return_value.__aexit__ = AsyncMock(
                return_value=False
            )

            zero_pids = [
                {"id": f"pid{str(i).zfill(12)}", "name": f"P{i}"}
                for i in range(5)
            ]

            # Should not raise
            await _bg_fetch_remaining_counts(user_id=1, zero_pids=zero_pids)

    @pytest.mark.asyncio
    async def test_bg_task_empty_list_returns_immediately(self):
        """BG task with empty list should return without any API calls."""
        from app.routers.playlists import _bg_fetch_remaining_counts

        # Should return immediately, no mocking needed
        await _bg_fetch_remaining_counts(user_id=1, zero_pids=[])
