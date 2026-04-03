"""Tests for wrapped router — POST/poll endpoints and background worker.

Covers:
- POST start_wrapped: returns task_id + total_services, validates time_range
- GET get_wrapped_status: 404 for missing, correct structure for existing
- _run_wrapped_task: progressive execution, error handling, partial failure
"""

import time
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.wrapped_tasks import _wrapped_tasks, create_task


def _clear_tasks():
    _wrapped_tasks.clear()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _mock_async_session():
    """Create a mock async_session context manager that yields a MagicMock db."""
    mock_db = MagicMock()

    @asynccontextmanager
    async def _session():
        yield mock_db

    return _session, mock_db


def _setup_wrapped_mocks():
    """Return a dict of configured mocks for all services used by _run_wrapped_task."""
    mock_session_fn, mock_db = _mock_async_session()

    mock_client = MagicMock()
    mock_client.close = AsyncMock()

    mock_bundle = MagicMock()
    mock_bundle.prefetch = AsyncMock()
    mock_bundle.get_top_tracks = AsyncMock(
        return_value={"items": [{"id": "t1", "name": "Track1"}]}
    )

    return {
        "session_fn": mock_session_fn,
        "db": mock_db,
        "client": mock_client,
        "bundle": mock_bundle,
        "temporal": {"total_plays": 100, "daily_minutes": []},
        "evolution": {
            "artists": {"loyal": [{"name": "A1"}], "rising": []}
        },
        "profile": {"genres": {"pop": 50}},
        "network": {"metrics": {"cluster_count": 3}},
    }


def _patch_wrapped_router(mocks):
    """Return a combined patch context manager for _run_wrapped_task dependencies."""
    mock_client_cls = MagicMock(return_value=mocks["client"])
    mock_bundle_cls = MagicMock(return_value=mocks["bundle"])

    patches = {
        "async_session": patch(
            "app.routers.wrapped.async_session", mocks["session_fn"]
        ),
        "client_cls": patch(
            "app.routers.wrapped.SpotifyClient", mock_client_cls
        ),
        "bundle_cls": patch(
            "app.routers.wrapped.RequestDataBundle", mock_bundle_cls
        ),
        "temporal": patch(
            "app.routers.wrapped.compute_temporal_patterns",
            AsyncMock(return_value=mocks["temporal"]),
        ),
        "evolution": patch(
            "app.routers.wrapped.compute_taste_evolution",
            AsyncMock(return_value=mocks["evolution"]),
        ),
        "profile": patch(
            "app.routers.wrapped.compute_profile",
            AsyncMock(return_value=mocks["profile"]),
        ),
        "network": patch(
            "app.routers.wrapped.build_artist_network",
            AsyncMock(return_value=mocks["network"]),
        ),
        "sanitize": patch(
            "app.routers.wrapped.sanitize_nans", side_effect=lambda x: x
        ),
    }
    return patches, mock_client_cls, mock_bundle_cls


class _MultiPatch:
    """Helper to enter/exit multiple patches at once."""

    def __init__(self, patches: dict):
        self._patches = patches
        self._mocks = {}

    def __enter__(self):
        for name, p in self._patches.items():
            self._mocks[name] = p.start()
        return self._mocks

    def __exit__(self, *args):
        for p in self._patches.values():
            p.stop()


# ---------------------------------------------------------------------------
# 1. POST start_wrapped
# ---------------------------------------------------------------------------


class TestStartWrapped:
    def setup_method(self):
        _clear_tasks()

    @pytest.mark.asyncio
    async def test_start_wrapped_returns_task_id_and_total(self):
        """POST start_wrapped returns task_id and total_services=5."""
        from app.routers.wrapped import start_wrapped

        mock_request = MagicMock()

        with patch("app.routers.wrapped.asyncio.create_task"):
            result = await start_wrapped(
                request=mock_request, user_id=1, time_range="medium_term"
            )

        assert "task_id" in result
        assert result["total_services"] == 5

    @pytest.mark.asyncio
    async def test_start_wrapped_defaults_invalid_time_range(self):
        """Invalid time_range falls back to medium_term."""
        from app.routers.wrapped import start_wrapped

        mock_request = MagicMock()

        with patch("app.routers.wrapped.asyncio.create_task"):
            result = await start_wrapped(
                request=mock_request, user_id=1, time_range="invalid_range"
            )

        task = _wrapped_tasks[result["task_id"]]
        assert task["time_range"] == "medium_term"

    @pytest.mark.asyncio
    async def test_start_wrapped_accepts_valid_time_ranges(self):
        """All three valid time_range values are accepted as-is."""
        from app.routers.wrapped import start_wrapped

        mock_request = MagicMock()

        for tr in ("short_term", "medium_term", "long_term"):
            with patch("app.routers.wrapped.asyncio.create_task"):
                result = await start_wrapped(
                    request=mock_request, user_id=1, time_range=tr
                )
            task = _wrapped_tasks[result["task_id"]]
            assert task["time_range"] == tr


# ---------------------------------------------------------------------------
# 2. GET get_wrapped_status
# ---------------------------------------------------------------------------


class TestGetWrappedStatus:
    def setup_method(self):
        _clear_tasks()

    @pytest.mark.asyncio
    async def test_returns_404_for_nonexistent_task(self):
        """GET with unknown task_id raises 404."""
        from fastapi import HTTPException

        from app.routers.wrapped import get_wrapped_status

        mock_request = MagicMock()

        with pytest.raises(HTTPException) as exc_info:
            await get_wrapped_status(
                task_id="nonexistent", request=mock_request, user_id=1
            )
        assert exc_info.value.status_code == 404

    @pytest.mark.asyncio
    async def test_returns_404_for_wrong_user(self):
        """GET by a different user raises 404 (ownership check)."""
        from fastapi import HTTPException

        from app.routers.wrapped import get_wrapped_status

        task = create_task(user_id=1, time_range="medium_term")
        mock_request = MagicMock()

        with pytest.raises(HTTPException) as exc_info:
            await get_wrapped_status(
                task_id=task["task_id"], request=mock_request, user_id=2
            )
        assert exc_info.value.status_code == 404

    @pytest.mark.asyncio
    async def test_returns_correct_structure(self):
        """GET returns all expected fields from the task."""
        from app.routers.wrapped import get_wrapped_status

        task = create_task(user_id=1, time_range="medium_term")
        mock_request = MagicMock()

        with patch("app.routers.wrapped.sanitize_nans", side_effect=lambda x: x):
            result = await get_wrapped_status(
                task_id=task["task_id"], request=mock_request, user_id=1
            )

        assert result["task_id"] == task["task_id"]
        assert result["status"] == "pending"
        assert result["phase"] == ""
        assert result["completed_services"] == 0
        assert result["total_services"] == 5
        assert result["waiting_seconds"] == 0
        assert result["error_detail"] is None
        assert result["results"]["available_slides"] == ["intro"]


# ---------------------------------------------------------------------------
# 3. _run_wrapped_task — progressive execution
# ---------------------------------------------------------------------------


class TestRunWrappedTask:
    def setup_method(self):
        _clear_tasks()

    @pytest.mark.asyncio
    async def test_progressive_execution_all_succeed(self):
        """All 5 services complete, task ends with status=completed and all slides."""
        from app.routers.wrapped import _run_wrapped_task

        task = create_task(user_id=1, time_range="medium_term")
        task_id = task["task_id"]

        mocks = _setup_wrapped_mocks()
        patches, _, _ = _patch_wrapped_router(mocks)

        with _MultiPatch(patches):
            await _run_wrapped_task(task_id, 1, "medium_term")

        assert task["status"] == "completed"
        assert task["completed_services"] == 5
        slides = task["results"]["available_slides"]
        assert "intro" in slides
        assert "top_tracks" in slides
        assert "listening_habits" in slides
        assert "peak_hours" in slides
        assert "artist_evolution" in slides
        assert "top_genres" in slides
        assert "artist_network" in slides
        assert "outro" in slides

    @pytest.mark.asyncio
    async def test_progressive_execution_updates_results(self):
        """Each service result is stored in task["results"]."""
        from app.routers.wrapped import _run_wrapped_task

        task = create_task(user_id=1, time_range="medium_term")
        task_id = task["task_id"]

        mocks = _setup_wrapped_mocks()
        patches, _, _ = _patch_wrapped_router(mocks)

        with _MultiPatch(patches):
            await _run_wrapped_task(task_id, 1, "medium_term")

        results = task["results"]
        assert results["top_tracks"] == [{"id": "t1", "name": "Track1"}]
        assert results["temporal"] == mocks["temporal"]
        assert results["evolution"] == mocks["evolution"]
        assert results["profile"] == mocks["profile"]
        assert results["network"] == mocks["network"]

    @pytest.mark.asyncio
    async def test_handles_spotify_auth_error(self):
        """SpotifyAuthError sets status=error with Italian message."""
        from app.routers.wrapped import _run_wrapped_task
        from app.utils.rate_limiter import SpotifyAuthError

        task = create_task(user_id=1, time_range="medium_term")
        task_id = task["task_id"]

        mocks = _setup_wrapped_mocks()
        # Make prefetch raise SpotifyAuthError
        mocks["bundle"].prefetch = AsyncMock(side_effect=SpotifyAuthError())
        patches, _, _ = _patch_wrapped_router(mocks)

        with _MultiPatch(patches):
            await _run_wrapped_task(task_id, 1, "medium_term")

        assert task["status"] == "error"
        assert "Sessione Spotify scaduta" in task["error_detail"]

    @pytest.mark.asyncio
    async def test_handles_throttle_error(self):
        """ThrottleError sets status=error with retry_after in Italian message."""
        from app.routers.wrapped import _run_wrapped_task
        from app.utils.rate_limiter import ThrottleError

        task = create_task(user_id=1, time_range="medium_term")
        task_id = task["task_id"]

        mocks = _setup_wrapped_mocks()
        mocks["bundle"].prefetch = AsyncMock(side_effect=ThrottleError(retry_after=45))
        patches, _, _ = _patch_wrapped_router(mocks)

        with _MultiPatch(patches):
            await _run_wrapped_task(task_id, 1, "medium_term")

        assert task["status"] == "error"
        assert "45" in task["error_detail"]
        assert "Troppe richieste" in task["error_detail"]

    @pytest.mark.asyncio
    async def test_handles_rate_limit_error(self):
        """RateLimitError sets status=error with retry message."""
        from app.routers.wrapped import _run_wrapped_task
        from app.utils.rate_limiter import RateLimitError

        task = create_task(user_id=1, time_range="medium_term")
        task_id = task["task_id"]

        mocks = _setup_wrapped_mocks()
        mocks["bundle"].prefetch = AsyncMock(
            side_effect=RateLimitError(retry_after=30)
        )
        patches, _, _ = _patch_wrapped_router(mocks)

        with _MultiPatch(patches):
            await _run_wrapped_task(task_id, 1, "medium_term")

        assert task["status"] == "error"
        assert "Troppe richieste" in task["error_detail"]

    @pytest.mark.asyncio
    async def test_handles_generic_exception(self):
        """Unexpected exception sets status=error with generic Italian message."""
        from app.routers.wrapped import _run_wrapped_task

        task = create_task(user_id=1, time_range="medium_term")
        task_id = task["task_id"]

        mocks = _setup_wrapped_mocks()
        mocks["bundle"].prefetch = AsyncMock(side_effect=RuntimeError("Unexpected"))
        patches, _, _ = _patch_wrapped_router(mocks)

        with _MultiPatch(patches):
            await _run_wrapped_task(task_id, 1, "medium_term")

        assert task["status"] == "error"
        assert task["error_detail"] == "Errore nel calcolo Wrapped"

    @pytest.mark.asyncio
    async def test_partial_failure_other_services_still_complete(self):
        """If one service fails, the others still run and complete."""
        from app.routers.wrapped import _run_wrapped_task

        task = create_task(user_id=1, time_range="medium_term")
        task_id = task["task_id"]

        mocks = _setup_wrapped_mocks()
        patches, _, _ = _patch_wrapped_router(mocks)

        # Override temporal to raise a non-auth exception
        patches["temporal"] = patch(
            "app.routers.wrapped.compute_temporal_patterns",
            AsyncMock(side_effect=RuntimeError("temporal service down")),
        )
        # Override network to also fail
        patches["network"] = patch(
            "app.routers.wrapped.build_artist_network",
            AsyncMock(side_effect=RuntimeError("network service down")),
        )

        with _MultiPatch(patches):
            await _run_wrapped_task(task_id, 1, "medium_term")

        # Task should still complete
        assert task["status"] == "completed"
        assert task["completed_services"] == 5

        # Failed services should have None results
        assert task["results"]["temporal"] is None
        assert task["results"]["network"] is None

        # Successful services should have data
        assert task["results"]["top_tracks"] is not None
        assert task["results"]["evolution"] is not None
        assert task["results"]["profile"] is not None

        # Slides from failed services should not be present
        slides = task["results"]["available_slides"]
        assert "listening_habits" not in slides
        assert "peak_hours" not in slides
        assert "artist_network" not in slides

        # Slides from successful services should be present
        assert "top_tracks" in slides
        assert "artist_evolution" in slides
        assert "top_genres" in slides
        assert "outro" in slides

    @pytest.mark.asyncio
    async def test_uses_dedicated_async_session(self):
        """_run_wrapped_task uses async_session() (not request-scoped get_db)."""
        from app.routers.wrapped import _run_wrapped_task

        task = create_task(user_id=1, time_range="medium_term")
        task_id = task["task_id"]

        mocks = _setup_wrapped_mocks()
        patches, _, _ = _patch_wrapped_router(mocks)

        session_called = False
        original_fn = mocks["session_fn"]

        @asynccontextmanager
        async def tracking_session():
            nonlocal session_called
            session_called = True
            async with original_fn() as db:
                yield db

        patches["async_session"] = patch(
            "app.routers.wrapped.async_session", tracking_session
        )

        with _MultiPatch(patches):
            await _run_wrapped_task(task_id, 1, "medium_term")

        assert session_called, "async_session was not called — task must use dedicated session"

    @pytest.mark.asyncio
    async def test_client_closed_on_success(self):
        """SpotifyClient.close() is called even after successful completion."""
        from app.routers.wrapped import _run_wrapped_task

        task = create_task(user_id=1, time_range="medium_term")
        task_id = task["task_id"]

        mocks = _setup_wrapped_mocks()
        patches, mock_client_cls, _ = _patch_wrapped_router(mocks)

        with _MultiPatch(patches):
            await _run_wrapped_task(task_id, 1, "medium_term")

        mocks["client"].close.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_client_closed_on_error(self):
        """SpotifyClient.close() is called even when task errors out."""
        from app.routers.wrapped import _run_wrapped_task

        task = create_task(user_id=1, time_range="medium_term")
        task_id = task["task_id"]

        mocks = _setup_wrapped_mocks()
        mocks["bundle"].prefetch = AsyncMock(side_effect=RuntimeError("boom"))
        patches, _, _ = _patch_wrapped_router(mocks)

        with _MultiPatch(patches):
            await _run_wrapped_task(task_id, 1, "medium_term")

        mocks["client"].close.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_nonexistent_task_exits_early(self):
        """_run_wrapped_task returns immediately if task_id is not in store."""
        from app.routers.wrapped import _run_wrapped_task

        mocks = _setup_wrapped_mocks()
        patches, _, _ = _patch_wrapped_router(mocks)

        with _MultiPatch(patches):
            # Should not raise — just returns
            await _run_wrapped_task("nonexistent-id", 1, "medium_term")

        # No client should have been created
        mocks["client"].close.assert_not_awaited()
