"""Tests for Redis async client singleton."""

from unittest.mock import AsyncMock, patch

import pytest

from app.services import redis_client as rc


@pytest.fixture(autouse=True)
def _reset_singleton():
    """Reset the module-level singleton before each test."""
    rc._redis_client = None
    yield
    rc._redis_client = None


class TestGetRedis:
    """Tests for get_redis() singleton."""

    def test_returns_redis_client(self):
        client = rc.get_redis()
        assert client is not None

    def test_returns_same_instance(self):
        c1 = rc.get_redis()
        c2 = rc.get_redis()
        assert c1 is c2

    def test_lazy_init(self):
        """Client is None until first call."""
        assert rc._redis_client is None
        rc.get_redis()
        assert rc._redis_client is not None


class TestRedisPing:
    """Tests for redis_ping() health check helper."""

    @pytest.mark.asyncio
    async def test_ping_returns_true_when_redis_up(self):
        mock_client = AsyncMock()
        mock_client.ping.return_value = True
        rc._redis_client = mock_client

        result = await rc.redis_ping()
        assert result is True
        mock_client.ping.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_ping_returns_false_when_redis_down(self):
        mock_client = AsyncMock()
        mock_client.ping.side_effect = ConnectionError("Connection refused")
        rc._redis_client = mock_client

        result = await rc.redis_ping()
        assert result is False


class TestCloseRedis:
    """Tests for close_redis() graceful shutdown."""

    @pytest.mark.asyncio
    async def test_close_clears_singleton(self):
        mock_client = AsyncMock()
        rc._redis_client = mock_client

        await rc.close_redis()
        assert rc._redis_client is None
        mock_client.aclose.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_close_noop_when_not_initialized(self):
        """Closing when no client exists should not raise."""
        await rc.close_redis()
        assert rc._redis_client is None


class TestHealthEndpointRedis:
    """Test that /health includes Redis status."""

    @pytest.mark.asyncio
    async def test_health_includes_redis_ok(self):
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
            patch("app.main.redis_ping", new_callable=AsyncMock, return_value=True),
        ):
            from app.main import app
            from httpx import ASGITransport, AsyncClient

            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as ac:
                response = await ac.get("/health")

            data = response.json()
            assert "redis" in data["checks"]
            assert data["checks"]["redis"] == "ok"

    @pytest.mark.asyncio
    async def test_health_redis_error_degrades_status(self):
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
            patch("app.main.redis_ping", new_callable=AsyncMock, return_value=False),
        ):
            from app.main import app
            from httpx import ASGITransport, AsyncClient

            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as ac:
                response = await ac.get("/health")

            data = response.json()
            assert data["checks"]["redis"] == "error"
            assert data["status"] == "degraded"
            assert response.status_code == 503
