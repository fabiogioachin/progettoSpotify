"""Tests for progressive playlist loading (task store + compare/analytics background workers).

Covers:
1. playlist_tasks.py — task creation, ownership, cleanup, per-user limits
2. playlists.py — POST /compare start, GET /compare/{task_id} polling, background worker
3. playlist_analytics.py — POST /playlist-analytics start, GET /{task_id} polling
"""

import asyncio
import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.playlist_tasks import (
    MAX_TASKS_PER_USER,
    TASK_TTL_SECONDS,
    _playlist_tasks,
    create_task,
    get_task,
    _cleanup_expired,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _clear_tasks():
    """Reset the in-memory task store between tests."""
    _playlist_tasks.clear()


def _make_playlist_items_response(track_ids: list[str], total: int | None = None):
    """Create a mock /playlists/{id}/items response."""
    items = []
    for tid in track_ids:
        items.append(
            {
                "item": {
                    "id": tid,
                    "name": f"Track {tid}",
                    "artists": [{"id": f"artist_{tid}", "name": f"Artist {tid}"}],
                    "popularity": 50,
                    "album": {"release_date": "2024-01-01"},
                },
                "added_at": "2024-06-01T12:00:00Z",
            }
        )
    return {
        "items": items,
        "total": total if total is not None else len(track_ids),
        "next": None,
    }


# ---------------------------------------------------------------------------
# 1. Task Store (playlist_tasks.py)
# ---------------------------------------------------------------------------


class TestPlaylistTaskStore:
    def setup_method(self):
        _clear_tasks()

    def test_create_task_returns_valid_structure(self):
        task = create_task(user_id=1, task_type="compare", total_playlists=3)
        assert task["task_id"]
        assert task["user_id"] == 1
        assert task["task_type"] == "compare"
        assert task["status"] == "pending"
        assert task["total_playlists"] == 3
        assert task["completed_playlists"] == 0
        assert task["results"] is None

    def test_create_task_with_playlist_ids(self):
        task = create_task(
            user_id=1,
            task_type="compare",
            total_playlists=2,
            playlist_ids=["abc", "def"],
        )
        assert task["playlist_ids"] == ["abc", "def"]

    def test_get_task_returns_owned_task(self):
        task = create_task(user_id=1, task_type="compare", total_playlists=2)
        retrieved = get_task(task["task_id"], user_id=1)
        assert retrieved is not None
        assert retrieved["task_id"] == task["task_id"]

    def test_get_task_rejects_wrong_user(self):
        task = create_task(user_id=1, task_type="compare", total_playlists=2)
        retrieved = get_task(task["task_id"], user_id=2)
        assert retrieved is None

    def test_get_task_returns_none_for_missing(self):
        assert get_task("nonexistent-id", user_id=1) is None

    def test_per_user_limit_enforced(self):
        for _ in range(MAX_TASKS_PER_USER):
            create_task(user_id=1, task_type="compare", total_playlists=2)

        with pytest.raises(ValueError, match="Troppi task attivi"):
            create_task(user_id=1, task_type="compare", total_playlists=2)

    def test_completed_tasks_dont_count_toward_limit(self):
        for _ in range(MAX_TASKS_PER_USER):
            task = create_task(user_id=1, task_type="compare", total_playlists=2)
            task["status"] = "completed"

        # Should succeed — completed tasks don't count
        new_task = create_task(user_id=1, task_type="compare", total_playlists=2)
        assert new_task["status"] == "pending"

    def test_error_tasks_dont_count_toward_limit(self):
        for _ in range(MAX_TASKS_PER_USER):
            task = create_task(user_id=1, task_type="compare", total_playlists=2)
            task["status"] = "error"

        new_task = create_task(user_id=1, task_type="compare", total_playlists=2)
        assert new_task["status"] == "pending"

    def test_different_users_have_independent_limits(self):
        for _ in range(MAX_TASKS_PER_USER):
            create_task(user_id=1, task_type="compare", total_playlists=2)

        # User 2 should still be able to create tasks
        task = create_task(user_id=2, task_type="compare", total_playlists=2)
        assert task["user_id"] == 2

    def test_cleanup_expired_removes_old_tasks(self):
        task = create_task(user_id=1, task_type="compare", total_playlists=2)
        # Manually expire the task
        task["created_at"] = time.time() - TASK_TTL_SECONDS - 1

        _cleanup_expired()
        assert get_task(task["task_id"], user_id=1) is None

    def test_cleanup_keeps_recent_tasks(self):
        task = create_task(user_id=1, task_type="compare", total_playlists=2)
        _cleanup_expired()
        assert get_task(task["task_id"], user_id=1) is not None


# ---------------------------------------------------------------------------
# 2. Compare Background Worker
# ---------------------------------------------------------------------------


class TestCompareBackgroundWorker:
    def setup_method(self):
        _clear_tasks()

    @pytest.mark.asyncio
    async def test_compare_worker_completes_successfully(self):
        """Worker fetches tracks, genres, computes results, sets status=completed."""
        task = create_task(
            user_id=1,
            task_type="compare",
            total_playlists=2,
            playlist_ids=["pid1", "pid2"],
        )

        mock_client = MagicMock()
        mock_client.get = AsyncMock(return_value={"name": "Test Playlist"})
        mock_client.get_playlist_items = AsyncMock(
            return_value=_make_playlist_items_response(
                ["t111111111111111", "t222222222222222"], total=2
            )
        )
        mock_client.close = AsyncMock()

        async def _passthrough_retry(fn, *args, **kwargs):
            return await fn(*args, **kwargs)

        async def _mock_genre_cache(db, client, artist_ids):
            return {aid: ["pop", "rock"] for aid in artist_ids}

        async def _mock_popularity(tracks, db):
            return 0

        async def _mock_features(db, track_ids):
            return {}

        with (
            patch("app.routers.playlists.SpotifyClient", return_value=mock_client),
            patch("app.routers.playlists.retry_with_backoff", _passthrough_retry),
            patch(
                "app.routers.playlists.get_artist_genres_cached", _mock_genre_cache
            ),
            patch("app.routers.playlists.read_popularity_cache", _mock_popularity),
            patch("app.routers.playlists.get_or_fetch_features", _mock_features),
        ):
            from app.routers.playlists import _run_compare_task

            await _run_compare_task(task["task_id"], ["pid1", "pid2"], user_id=1)

        assert task["status"] == "completed"
        assert task["results"] is not None
        assert "comparisons" in task["results"]
        assert len(task["results"]["comparisons"]) == 2
        assert task["completed_playlists"] == 2

    @pytest.mark.asyncio
    async def test_compare_worker_sets_error_on_auth_failure(self):
        """Worker sets status=error when SpotifyAuthError is raised."""
        from app.utils.rate_limiter import SpotifyAuthError

        task = create_task(
            user_id=1,
            task_type="compare",
            total_playlists=2,
            playlist_ids=["pid1", "pid2"],
        )

        mock_client = MagicMock()
        mock_client.get = AsyncMock(side_effect=SpotifyAuthError())
        mock_client.close = AsyncMock()

        async def _raise_auth(fn, *args, **kwargs):
            return await fn(*args, **kwargs)

        with (
            patch("app.routers.playlists.SpotifyClient", return_value=mock_client),
            patch("app.routers.playlists.retry_with_backoff", _raise_auth),
        ):
            from app.routers.playlists import _run_compare_task

            await _run_compare_task(task["task_id"], ["pid1", "pid2"], user_id=1)

        assert task["status"] == "error"
        assert task["error_detail"] == "Sessione scaduta"

    @pytest.mark.asyncio
    async def test_compare_worker_waits_on_throttle(self):
        """Worker pauses and retries on ThrottleError."""
        from app.utils.rate_limiter import ThrottleError

        task = create_task(
            user_id=1,
            task_type="compare",
            total_playlists=1,
            playlist_ids=["pid1"],
        )

        call_count = 0

        async def _throttle_then_succeed(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise ThrottleError(retry_after=0.1)
            return {"name": "Test"}

        mock_client = MagicMock()
        mock_client.get = AsyncMock(side_effect=_throttle_then_succeed)
        mock_client.get_playlist_items = AsyncMock(
            return_value=_make_playlist_items_response(["t111111111111111"])
        )
        mock_client.close = AsyncMock()

        async def _passthrough_retry(fn, *args, **kwargs):
            return await fn(*args, **kwargs)

        async def _mock_genre_cache(db, client, artist_ids):
            return {}

        async def _mock_popularity(tracks, db):
            return 0

        async def _mock_features(db, track_ids):
            return {}

        with (
            patch("app.routers.playlists.SpotifyClient", return_value=mock_client),
            patch("app.routers.playlists.retry_with_backoff", _passthrough_retry),
            patch(
                "app.routers.playlists.get_artist_genres_cached", _mock_genre_cache
            ),
            patch("app.routers.playlists.read_popularity_cache", _mock_popularity),
            patch("app.routers.playlists.get_or_fetch_features", _mock_features),
        ):
            from app.routers.playlists import _run_compare_task

            await _run_compare_task(task["task_id"], ["pid1"], user_id=1)

        assert task["status"] == "completed"
        assert call_count == 2  # first throttled, second succeeded

    @pytest.mark.asyncio
    async def test_compare_response_matches_schema(self):
        """Results must match PlaylistComparisonResponse shape."""
        task = create_task(
            user_id=1,
            task_type="compare",
            total_playlists=2,
            playlist_ids=["pid1", "pid2"],
        )

        mock_client = MagicMock()
        mock_client.get = AsyncMock(return_value={"name": "Test"})
        mock_client.get_playlist_items = AsyncMock(
            return_value=_make_playlist_items_response(["t111111111111111"])
        )
        mock_client.close = AsyncMock()

        async def _passthrough(fn, *args, **kwargs):
            return await fn(*args, **kwargs)

        async def _mock_genre_cache(db, client, artist_ids):
            return {}

        async def _mock_pop(tracks, db):
            return 0

        async def _mock_features(db, track_ids):
            return {}

        with (
            patch("app.routers.playlists.SpotifyClient", return_value=mock_client),
            patch("app.routers.playlists.retry_with_backoff", _passthrough),
            patch(
                "app.routers.playlists.get_artist_genres_cached", _mock_genre_cache
            ),
            patch("app.routers.playlists.read_popularity_cache", _mock_pop),
            patch("app.routers.playlists.get_or_fetch_features", _mock_features),
        ):
            from app.routers.playlists import _run_compare_task

            await _run_compare_task(task["task_id"], ["pid1", "pid2"], user_id=1)

        # Validate shape matches PlaylistComparisonResponse
        from app.schemas import PlaylistComparisonResponse

        PlaylistComparisonResponse(**task["results"])  # must not raise


# ---------------------------------------------------------------------------
# 3. Analytics Background Worker
# ---------------------------------------------------------------------------


class TestAnalyticsBackgroundWorker:
    def setup_method(self):
        _clear_tasks()

    @pytest.mark.asyncio
    async def test_analytics_worker_completes_with_empty_playlists(self):
        """Worker returns empty result when user has no playlists."""
        task = create_task(user_id=1, task_type="analytics", total_playlists=0)

        mock_client = MagicMock()
        mock_client.get_playlists = AsyncMock(
            return_value={"items": [], "total": 0}
        )
        mock_client.close = AsyncMock()

        async def _passthrough(fn, *args, **kwargs):
            return await fn(*args, **kwargs)

        with (
            patch(
                "app.routers.playlist_analytics.SpotifyClient",
                return_value=mock_client,
            ),
            patch("app.routers.playlist_analytics.retry_with_backoff", _passthrough),
        ):
            from app.routers.playlist_analytics import _run_analytics_task

            await _run_analytics_task(task["task_id"], user_id=1)

        assert task["status"] == "completed"
        assert task["results"]["summary"]["total_playlists"] == 0

    @pytest.mark.asyncio
    async def test_analytics_worker_sets_partial_results_after_listing(self):
        """After listing phase, task has partial results with summary."""
        task = create_task(user_id=1, task_type="analytics", total_playlists=0)

        mock_playlist = {
            "id": "pid1",
            "name": "Test",
            "public": True,
            "collaborative": False,
            "tracks": {"total": 5},
            "images": [{"url": "https://example.com/img.jpg"}],
        }

        mock_client = MagicMock()
        mock_client.get_playlists = AsyncMock(
            return_value={"items": [mock_playlist], "total": 1}
        )
        mock_client.get_playlist_items = AsyncMock(
            return_value=_make_playlist_items_response(
                ["t111111111111111", "t222222222222222"], total=2
            )
        )
        mock_client.close = AsyncMock()

        async def _passthrough(fn, *args, **kwargs):
            return await fn(*args, **kwargs)

        with (
            patch(
                "app.routers.playlist_analytics.SpotifyClient",
                return_value=mock_client,
            ),
            patch("app.routers.playlist_analytics.retry_with_backoff", _passthrough),
        ):
            from app.routers.playlist_analytics import _run_analytics_task

            await _run_analytics_task(task["task_id"], user_id=1)

        assert task["status"] == "completed"
        assert task["results"]["summary"]["total_playlists"] == 1
        assert len(task["results"]["playlists"]) == 1

    @pytest.mark.asyncio
    async def test_analytics_worker_handles_auth_error(self):
        """Worker sets error on SpotifyAuthError during listing."""
        from app.utils.rate_limiter import SpotifyAuthError

        task = create_task(user_id=1, task_type="analytics", total_playlists=0)

        mock_client = MagicMock()
        mock_client.get_playlists = AsyncMock(side_effect=SpotifyAuthError())
        mock_client.close = AsyncMock()

        async def _passthrough(fn, *args, **kwargs):
            return await fn(*args, **kwargs)

        with (
            patch(
                "app.routers.playlist_analytics.SpotifyClient",
                return_value=mock_client,
            ),
            patch("app.routers.playlist_analytics.retry_with_backoff", _passthrough),
        ):
            from app.routers.playlist_analytics import _run_analytics_task

            await _run_analytics_task(task["task_id"], user_id=1)

        assert task["status"] == "error"
        assert task["error_detail"] == "Sessione scaduta"


# ---------------------------------------------------------------------------
# 4. Task Status Response Shape
# ---------------------------------------------------------------------------


class TestTaskStatusSchema:
    def setup_method(self):
        _clear_tasks()

    def test_status_response_fields(self):
        """PlaylistTaskStatusResponse must accept all task fields."""
        from app.schemas import PlaylistTaskStatusResponse

        task = create_task(user_id=1, task_type="compare", total_playlists=3)
        response = PlaylistTaskStatusResponse(
            task_id=task["task_id"],
            status=task["status"],
            phase=task["phase"],
            total_playlists=task["total_playlists"],
            completed_playlists=task["completed_playlists"],
            waiting_seconds=task["waiting_seconds"],
            error_detail=task["error_detail"],
            results=task["results"],
        )
        assert response.task_id == task["task_id"]
        assert response.status == "pending"
        assert response.results is None

    def test_start_response_fields(self):
        """PlaylistTaskStartResponse must accept task_id and total_playlists."""
        from app.schemas import PlaylistTaskStartResponse

        response = PlaylistTaskStartResponse(
            task_id="test-id", total_playlists=3
        )
        assert response.task_id == "test-id"
        assert response.total_playlists == 3
