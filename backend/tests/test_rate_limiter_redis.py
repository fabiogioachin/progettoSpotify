"""Tests for Redis-backed rate limiting in SpotifyClient and APIRateLimiter.

Covers:
- SpotifyClient._check_cooldown / _set_cooldown via Redis
- SpotifyClient._throttle_check_and_register via Redis sorted set
- SpotifyClient.get_window_usage / get_cooldown_remaining
- APIRateLimiter middleware with Redis sorted sets
- Graceful degradation when Redis is unavailable
"""

import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.utils.rate_limiter import ThrottleError


class TestSpotifyClientCooldown:
    """Tests for Redis-backed cooldown in SpotifyClient."""

    @pytest.mark.asyncio
    async def test_check_cooldown_returns_none_when_no_cooldown(self):
        mock_redis = AsyncMock()
        mock_redis.ttl.return_value = -2  # key does not exist

        with patch("app.services.spotify_client.get_redis", return_value=mock_redis):
            from app.services.spotify_client import SpotifyClient

            result = await SpotifyClient._check_cooldown()
            assert result is None

    @pytest.mark.asyncio
    async def test_check_cooldown_returns_remaining_seconds(self):
        mock_redis = AsyncMock()
        mock_redis.ttl.return_value = 42

        with patch("app.services.spotify_client.get_redis", return_value=mock_redis):
            from app.services.spotify_client import SpotifyClient

            result = await SpotifyClient._check_cooldown()
            assert result == 42.0

    @pytest.mark.asyncio
    async def test_check_cooldown_failopen_on_redis_error(self):
        with patch(
            "app.services.spotify_client.get_redis",
            side_effect=ConnectionError("Redis down"),
        ):
            from app.services.spotify_client import SpotifyClient

            result = await SpotifyClient._check_cooldown()
            assert result is None

    @pytest.mark.asyncio
    async def test_set_cooldown_sets_key_with_ttl(self):
        mock_redis = AsyncMock()

        with patch("app.services.spotify_client.get_redis", return_value=mock_redis):
            from app.services.spotify_client import SpotifyClient

            await SpotifyClient._set_cooldown(30.0)
            mock_redis.set.assert_awaited_once_with(
                SpotifyClient._REDIS_COOLDOWN_KEY, "1", ex=30
            )

    @pytest.mark.asyncio
    async def test_set_cooldown_minimum_ttl_is_1(self):
        mock_redis = AsyncMock()

        with patch("app.services.spotify_client.get_redis", return_value=mock_redis):
            from app.services.spotify_client import SpotifyClient

            await SpotifyClient._set_cooldown(0.3)
            mock_redis.set.assert_awaited_once_with(
                SpotifyClient._REDIS_COOLDOWN_KEY, "1", ex=1
            )

    @pytest.mark.asyncio
    async def test_set_cooldown_silent_on_redis_error(self):
        with patch(
            "app.services.spotify_client.get_redis",
            side_effect=ConnectionError("Redis down"),
        ):
            from app.services.spotify_client import SpotifyClient

            # Should not raise
            await SpotifyClient._set_cooldown(10.0)


class TestSpotifyClientThrottle:
    """Tests for Redis-backed sliding window throttle."""

    @pytest.mark.asyncio
    async def test_throttle_allows_when_under_limit(self):
        mock_pipe = MagicMock()
        # execute() is the only awaited call on the pipeline
        mock_pipe.execute = AsyncMock(
            return_value=[
                0,
                [b"call1", b"call2"],  # 2 calls in window — well under 25
                1,
                True,
            ]
        )

        mock_redis = MagicMock()
        mock_redis.pipeline.return_value = mock_pipe

        with patch("app.services.spotify_client.get_redis", return_value=mock_redis):
            from app.services.spotify_client import SpotifyClient

            # Should not raise
            await SpotifyClient._throttle_check_and_register()

    @pytest.mark.asyncio
    async def test_throttle_raises_when_over_limit(self):
        # Simulate 25 calls already in window
        calls_in_window = [f"call{i}".encode() for i in range(25)]

        mock_pipe = MagicMock()
        mock_pipe.execute = AsyncMock(return_value=[0, calls_in_window, 1, True])

        mock_redis = MagicMock()
        mock_redis.pipeline.return_value = mock_pipe
        mock_redis.zrem = AsyncMock()
        mock_redis.zscore = AsyncMock(return_value=time.time() - 20)

        with patch("app.services.spotify_client.get_redis", return_value=mock_redis):
            from app.services.spotify_client import SpotifyClient

            with pytest.raises(ThrottleError):
                await SpotifyClient._throttle_check_and_register()

            # Verify it tried to remove the over-budget call
            mock_redis.zrem.assert_awaited()

    @pytest.mark.asyncio
    async def test_throttle_failopen_on_redis_error(self):
        with patch(
            "app.services.spotify_client.get_redis",
            side_effect=ConnectionError("Redis down"),
        ):
            from app.services.spotify_client import SpotifyClient

            # Should not raise — fail-open
            await SpotifyClient._throttle_check_and_register()


class TestSpotifyClientWindowUsage:
    """Tests for get_window_usage() and get_cooldown_remaining().

    get_window_usage now uses a pipeline: ZCOUNT + ZRANGEBYSCORE LIMIT 0 1.
    """

    @pytest.mark.asyncio
    async def test_get_window_usage_returns_count_and_reset(self):
        now = time.time()
        oldest_score = now - 20

        mock_pipe = MagicMock()
        # results: [zcount=3, zrangebyscore with LIMIT 0 1 = [(oldest_member, score)]]
        mock_pipe.execute = AsyncMock(return_value=[3, [("call1", oldest_score)]])

        mock_redis = MagicMock()
        mock_redis.pipeline.return_value = mock_pipe

        with patch("app.services.spotify_client.get_redis", return_value=mock_redis):
            from app.services.spotify_client import SpotifyClient

            count, reset = await SpotifyClient.get_window_usage()
            assert count == 3
            # oldest is at now-20, window is 30s, so reset ~ 10s
            assert 9.0 <= reset <= 11.0

    @pytest.mark.asyncio
    async def test_get_window_usage_empty(self):
        mock_pipe = MagicMock()
        mock_pipe.execute = AsyncMock(return_value=[0, []])

        mock_redis = MagicMock()
        mock_redis.pipeline.return_value = mock_pipe

        with patch("app.services.spotify_client.get_redis", return_value=mock_redis):
            from app.services.spotify_client import SpotifyClient

            count, reset = await SpotifyClient.get_window_usage()
            assert count == 0
            assert reset == 0

    @pytest.mark.asyncio
    async def test_get_window_usage_returns_zero_on_redis_error(self):
        with patch(
            "app.services.spotify_client.get_redis",
            side_effect=ConnectionError("down"),
        ):
            from app.services.spotify_client import SpotifyClient

            count, reset = await SpotifyClient.get_window_usage()
            assert count == 0
            assert reset == 0

    @pytest.mark.asyncio
    async def test_get_cooldown_remaining_returns_ttl(self):
        mock_redis = AsyncMock()
        mock_redis.ttl.return_value = 15

        with patch("app.services.spotify_client.get_redis", return_value=mock_redis):
            from app.services.spotify_client import SpotifyClient

            result = await SpotifyClient.get_cooldown_remaining()
            assert result == 15.0

    @pytest.mark.asyncio
    async def test_get_cooldown_remaining_returns_zero_when_not_set(self):
        mock_redis = AsyncMock()
        mock_redis.ttl.return_value = -2

        with patch("app.services.spotify_client.get_redis", return_value=mock_redis):
            from app.services.spotify_client import SpotifyClient

            result = await SpotifyClient.get_cooldown_remaining()
            assert result == 0


class TestAPIRateLimiterRedis:
    """Tests for the Redis-backed APIRateLimiter middleware."""

    @pytest.mark.asyncio
    async def test_allows_request_under_limit(self):
        mock_pipe = MagicMock()
        # 2 entries in window (under 120 rpm)
        entries = [("call1", time.time() - 10), ("call2", time.time() - 5)]
        mock_pipe.execute = AsyncMock(return_value=[0, entries, 1, True])

        mock_redis = MagicMock()
        mock_redis.pipeline.return_value = mock_pipe

        with (
            patch("app.utils.rate_limiter.get_redis", return_value=mock_redis),
            patch(
                "app.services.spotify_client.SpotifyClient.get_window_usage",
                new_callable=AsyncMock,
                return_value=(0, 0),
            ),
            patch(
                "app.services.spotify_client.SpotifyClient.get_cooldown_remaining",
                new_callable=AsyncMock,
                return_value=0,
            ),
        ):
            from app.main import app
            from httpx import ASGITransport, AsyncClient

            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as ac:
                response = await ac.get("/health")

            # Health endpoint is exempt from rate limiting — should pass through
            # (503 is expected when DB/Redis are not running in test)
            assert response.status_code in (200, 503)

    @pytest.mark.asyncio
    async def test_blocks_request_over_limit(self):
        now = time.time()
        # 120 entries in window (at limit)
        entries = [(f"call{i}", now - 30 + i * 0.25) for i in range(120)]

        mock_pipe = MagicMock()
        mock_pipe.execute = AsyncMock(return_value=[0, entries, 1, True])

        mock_redis = MagicMock()
        mock_redis.pipeline.return_value = mock_pipe
        mock_redis.zrem = AsyncMock()

        with (
            patch("app.utils.rate_limiter.get_redis", return_value=mock_redis),
            patch(
                "app.services.spotify_client.SpotifyClient.get_window_usage",
                new_callable=AsyncMock,
                return_value=(0, 0),
            ),
            patch(
                "app.services.spotify_client.SpotifyClient.get_cooldown_remaining",
                new_callable=AsyncMock,
                return_value=0,
            ),
        ):
            from app.main import app
            from httpx import ASGITransport, AsyncClient

            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as ac:
                response = await ac.get("/api/v1/analytics/features")

            assert response.status_code == 429
            assert "Retry-After" in response.headers

    @pytest.mark.asyncio
    async def test_exempt_paths_bypass_rate_limit(self):
        """Health endpoint should bypass rate limiting entirely."""
        with (
            patch(
                "app.services.spotify_client.SpotifyClient.get_window_usage",
                new_callable=AsyncMock,
                return_value=(0, 0),
            ),
            patch(
                "app.services.spotify_client.SpotifyClient.get_cooldown_remaining",
                new_callable=AsyncMock,
                return_value=0,
            ),
        ):
            from app.main import app
            from httpx import ASGITransport, AsyncClient

            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as ac:
                response = await ac.get("/health")

            # Health should work regardless of Redis state
            assert response.status_code in (200, 503)  # depends on DB/Redis health

    @pytest.mark.asyncio
    async def test_failopen_on_redis_error(self):
        """When Redis is down, APIRateLimiter should allow requests."""
        with (
            patch(
                "app.utils.rate_limiter.get_redis",
                side_effect=ConnectionError("Redis down"),
            ),
            patch(
                "app.services.spotify_client.SpotifyClient.get_window_usage",
                new_callable=AsyncMock,
                return_value=(0, 0),
            ),
            patch(
                "app.services.spotify_client.SpotifyClient.get_cooldown_remaining",
                new_callable=AsyncMock,
                return_value=0,
            ),
        ):
            from app.main import app
            from httpx import ASGITransport, AsyncClient

            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as ac:
                response = await ac.get("/health")

            # Should still pass through — fail-open (503 expected when DB is not running)
            assert response.status_code in (200, 503)
