"""Tests for background_tasks staggering, skip tracking, and priority levels.

Covers:
- _get_syncable_users prioritizes skipped users
- _get_syncable_users fail-open on Redis errors
- _mark_skipped / _clear_skipped Redis operations
- sync_recent_plays staggering and break-on-rate-limit
- _sync_single_user uses P2_BATCH priority
- _sync_user_recent_plays accepts optional client parameter
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.api_budget import Priority
from app.services.background_tasks import (
    _clear_skipped,
    _get_syncable_users,
    _mark_skipped,
    _sync_single_user,
    _sync_user_recent_plays,
    sync_recent_plays,
)
from app.utils.rate_limiter import RateLimitError, ThrottleError


class TestSkipTracking:
    """Tests for _mark_skipped and _clear_skipped."""

    @pytest.mark.asyncio
    async def test_mark_skipped_sets_redis_key(self):
        """_mark_skipped sets sync:skipped:{user_id} with 2h TTL."""
        mock_redis = AsyncMock()
        with patch("app.services.background_tasks.get_redis", return_value=mock_redis):
            await _mark_skipped(42)
        mock_redis.set.assert_called_once_with("sync:skipped:42", "1", ex=7200)

    @pytest.mark.asyncio
    async def test_clear_skipped_deletes_redis_key(self):
        """_clear_skipped deletes sync:skipped:{user_id}."""
        mock_redis = AsyncMock()
        with patch("app.services.background_tasks.get_redis", return_value=mock_redis):
            await _clear_skipped(42)
        mock_redis.delete.assert_called_once_with("sync:skipped:42")

    @pytest.mark.asyncio
    async def test_mark_skipped_swallows_redis_errors(self):
        """_mark_skipped silently ignores Redis errors."""
        with patch(
            "app.services.background_tasks.get_redis",
            side_effect=ConnectionError("Redis down"),
        ):
            # Should not raise
            await _mark_skipped(42)

    @pytest.mark.asyncio
    async def test_clear_skipped_swallows_redis_errors(self):
        """_clear_skipped silently ignores Redis errors."""
        with patch(
            "app.services.background_tasks.get_redis",
            side_effect=ConnectionError("Redis down"),
        ):
            await _clear_skipped(42)


class TestGetSyncableUsers:
    """Tests for _get_syncable_users."""

    @pytest.mark.asyncio
    async def test_skipped_users_come_first(self):
        """Previously skipped users are prioritized in the returned list."""
        mock_db_result = MagicMock()
        mock_db_result.all.return_value = [(1,), (2,), (3,)]

        mock_session = AsyncMock()
        mock_session.execute.return_value = mock_db_result
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)

        mock_redis = AsyncMock()
        # User 3 is skipped, users 1 and 2 are not
        mock_redis.exists = AsyncMock(
            side_effect=lambda key: key == "sync:skipped:3"
        )

        with (
            patch("app.services.background_tasks.async_session", return_value=mock_session),
            patch("app.services.background_tasks.get_redis", return_value=mock_redis),
        ):
            result = await _get_syncable_users()

        assert result == [3, 1, 2]  # skipped first

    @pytest.mark.asyncio
    async def test_fail_open_on_redis_error(self):
        """Returns all users in DB order when Redis is unavailable."""
        mock_db_result = MagicMock()
        mock_db_result.all.return_value = [(1,), (2,)]

        mock_session = AsyncMock()
        mock_session.execute.return_value = mock_db_result
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)

        with (
            patch("app.services.background_tasks.async_session", return_value=mock_session),
            patch(
                "app.services.background_tasks.get_redis",
                side_effect=ConnectionError("Redis down"),
            ),
        ):
            result = await _get_syncable_users()

        assert result == [1, 2]

    @pytest.mark.asyncio
    async def test_empty_users(self):
        """Returns empty list when no users have tokens."""
        mock_db_result = MagicMock()
        mock_db_result.all.return_value = []

        mock_session = AsyncMock()
        mock_session.execute.return_value = mock_db_result
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)

        with patch("app.services.background_tasks.async_session", return_value=mock_session):
            result = await _get_syncable_users()

        assert result == []


class TestSyncSingleUser:
    """Tests for _sync_single_user."""

    @pytest.mark.asyncio
    async def test_uses_p2_batch_priority(self):
        """_sync_single_user creates SpotifyClient with P2_BATCH priority."""
        mock_client = AsyncMock()
        mock_session = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)

        created_priorities = []

        def capture_client(db, user_id, priority=Priority.P0_INTERACTIVE):
            created_priorities.append(priority)
            return mock_client

        with (
            patch("app.services.background_tasks.async_session", return_value=mock_session),
            patch("app.services.background_tasks.SpotifyClient", side_effect=capture_client),
            patch("app.services.background_tasks._sync_user_recent_plays", new_callable=AsyncMock),
            patch("app.services.background_tasks._clear_skipped", new_callable=AsyncMock),
        ):
            await _sync_single_user(1)

        assert created_priorities == [Priority.P2_BATCH]

    @pytest.mark.asyncio
    async def test_clears_skipped_on_success(self):
        """_sync_single_user clears skip flag after successful sync."""
        mock_client = AsyncMock()
        mock_session = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)

        with (
            patch("app.services.background_tasks.async_session", return_value=mock_session),
            patch("app.services.background_tasks.SpotifyClient", return_value=mock_client),
            patch("app.services.background_tasks._sync_user_recent_plays", new_callable=AsyncMock),
            patch("app.services.background_tasks._clear_skipped", new_callable=AsyncMock) as mock_clear,
        ):
            await _sync_single_user(42)

        mock_clear.assert_called_once_with(42)

    @pytest.mark.asyncio
    async def test_closes_client_on_error(self):
        """_sync_single_user closes client even when sync raises."""
        mock_client = AsyncMock()
        mock_session = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)

        with (
            patch("app.services.background_tasks.async_session", return_value=mock_session),
            patch("app.services.background_tasks.SpotifyClient", return_value=mock_client),
            patch(
                "app.services.background_tasks._sync_user_recent_plays",
                new_callable=AsyncMock,
                side_effect=RateLimitError(retry_after=30),
            ),
        ):
            with pytest.raises(RateLimitError):
                await _sync_single_user(1)

        mock_client.close.assert_called_once()


class TestSyncRecentPlays:
    """Tests for sync_recent_plays orchestrator."""

    @pytest.mark.asyncio
    async def test_breaks_on_rate_limit(self):
        """sync_recent_plays stops syncing all users on RateLimitError."""
        call_count = 0

        async def fake_sync(user_id):
            nonlocal call_count
            call_count += 1
            if call_count >= 2:
                raise RateLimitError(retry_after=30)

        with (
            patch(
                "app.services.background_tasks._get_syncable_users",
                new_callable=AsyncMock,
                return_value=[1, 2, 3, 4],
            ),
            patch("app.services.background_tasks._sync_single_user", side_effect=fake_sync),
            patch("app.services.background_tasks._mark_skipped", new_callable=AsyncMock) as mock_mark,
            patch("app.services.background_tasks.asyncio") as mock_asyncio,
        ):
            mock_asyncio.sleep = AsyncMock()
            await sync_recent_plays()

        # Should have marked user 2 as skipped (the one that triggered rate limit)
        mock_mark.assert_called_once_with(2)
        # Should NOT have tried users 3 and 4
        assert call_count == 2

    @pytest.mark.asyncio
    async def test_breaks_on_throttle_error(self):
        """sync_recent_plays also breaks on ThrottleError."""
        call_count = 0

        async def fake_sync(user_id):
            nonlocal call_count
            call_count += 1
            if call_count >= 1:
                raise ThrottleError(retry_after=10)

        with (
            patch(
                "app.services.background_tasks._get_syncable_users",
                new_callable=AsyncMock,
                return_value=[1, 2],
            ),
            patch("app.services.background_tasks._sync_single_user", side_effect=fake_sync),
            patch("app.services.background_tasks._mark_skipped", new_callable=AsyncMock),
            patch("app.services.background_tasks.asyncio") as mock_asyncio,
        ):
            mock_asyncio.sleep = AsyncMock()
            await sync_recent_plays()

        assert call_count == 1

    @pytest.mark.asyncio
    async def test_continues_on_generic_exception(self):
        """sync_recent_plays continues to next user on generic exceptions."""
        call_count = 0

        async def fake_sync(user_id):
            nonlocal call_count
            call_count += 1
            if user_id == 1:
                raise ValueError("something went wrong")

        with (
            patch(
                "app.services.background_tasks._get_syncable_users",
                new_callable=AsyncMock,
                return_value=[1, 2],
            ),
            patch("app.services.background_tasks._sync_single_user", side_effect=fake_sync),
            patch("app.services.background_tasks.asyncio") as mock_asyncio,
        ):
            mock_asyncio.sleep = AsyncMock()
            await sync_recent_plays()

        assert call_count == 2  # both users attempted

    @pytest.mark.asyncio
    async def test_stagger_interval_calculation(self):
        """sync_recent_plays sleeps between users with correct interval."""
        sleep_calls = []

        async def capture_sleep(seconds):
            sleep_calls.append(seconds)

        with (
            patch(
                "app.services.background_tasks._get_syncable_users",
                new_callable=AsyncMock,
                return_value=[1, 2, 3],
            ),
            patch("app.services.background_tasks._sync_single_user", new_callable=AsyncMock),
            patch("app.services.background_tasks.asyncio") as mock_asyncio,
        ):
            mock_asyncio.sleep = AsyncMock(side_effect=capture_sleep)
            await sync_recent_plays()

        # 3 users → interval = min(55*60/3, 180) = min(1100, 180) = 180
        assert len(sleep_calls) == 2  # no sleep before first user
        assert all(s == 180 for s in sleep_calls)

    @pytest.mark.asyncio
    async def test_no_sleep_for_single_user(self):
        """sync_recent_plays does not sleep when there's only one user."""
        with (
            patch(
                "app.services.background_tasks._get_syncable_users",
                new_callable=AsyncMock,
                return_value=[1],
            ),
            patch("app.services.background_tasks._sync_single_user", new_callable=AsyncMock),
            patch("app.services.background_tasks.asyncio") as mock_asyncio,
        ):
            mock_asyncio.sleep = AsyncMock()
            await sync_recent_plays()

        mock_asyncio.sleep.assert_not_called()

    @pytest.mark.asyncio
    async def test_returns_early_when_no_users(self):
        """sync_recent_plays returns immediately when no syncable users."""
        with (
            patch(
                "app.services.background_tasks._get_syncable_users",
                new_callable=AsyncMock,
                return_value=[],
            ),
            patch("app.services.background_tasks._sync_single_user", new_callable=AsyncMock) as mock_sync,
        ):
            await sync_recent_plays()

        mock_sync.assert_not_called()


class TestSyncUserRecentPlaysOptionalClient:
    """Tests for _sync_user_recent_plays client parameter."""

    @pytest.mark.asyncio
    async def test_uses_provided_client(self):
        """When client is passed, _sync_user_recent_plays uses it and does NOT close it."""
        mock_client = AsyncMock()
        mock_client.get_recently_played = AsyncMock(return_value={"items": []})
        mock_db = AsyncMock()

        with patch("app.services.background_tasks.retry_with_backoff", new_callable=AsyncMock, return_value={"items": []}):
            await _sync_user_recent_plays(mock_db, 1, client=mock_client)

        # Should NOT close the client (caller's responsibility)
        mock_client.close.assert_not_called()

    @pytest.mark.asyncio
    async def test_creates_own_client_when_none(self):
        """When no client is passed, _sync_user_recent_plays creates and closes its own."""
        mock_client = AsyncMock()
        mock_client.get_recently_played = AsyncMock(return_value={"items": []})
        mock_db = AsyncMock()

        with (
            patch("app.services.background_tasks.SpotifyClient", return_value=mock_client),
            patch("app.services.background_tasks.retry_with_backoff", new_callable=AsyncMock, return_value={"items": []}),
        ):
            await _sync_user_recent_plays(mock_db, 1)

        mock_client.close.assert_called_once()
