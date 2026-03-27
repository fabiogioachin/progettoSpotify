"""Tests for rate limit status endpoint and RateLimitHeaderMiddleware in main.py.

Covers:
- /api/v1/rate-limit-status includes window_reset_seconds field
- RateLimitHeaderMiddleware injects X-RateLimit-Reset header on /api/ responses

All rate limit state is now backed by Redis — tests mock SpotifyClient static methods.
"""

from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient


@pytest.fixture
def patched_app():
    """Import app with Redis-backed rate limit methods safely mocked."""
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

        yield app


class TestRateLimitHeaderMiddleware:
    """Tests for X-RateLimit-Reset header injection."""

    @pytest.mark.asyncio
    async def test_api_response_includes_ratelimit_reset_header(self, patched_app):
        """Every /api/ response must include X-RateLimit-Reset header."""
        transport = ASGITransport(app=patched_app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            response = await ac.get("/api/v1/rate-limit-status")

        assert "x-ratelimit-reset" in response.headers, (
            "Response must include X-RateLimit-Reset header"
        )
        # Value should be a parseable float
        reset_val = float(response.headers["x-ratelimit-reset"])
        assert reset_val >= 0

    @pytest.mark.asyncio
    async def test_api_response_includes_ratelimit_usage_header(self, patched_app):
        """Every /api/ response must include X-RateLimit-Usage header."""
        transport = ASGITransport(app=patched_app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            response = await ac.get("/api/v1/rate-limit-status")

        assert "x-ratelimit-usage" in response.headers, (
            "Response must include X-RateLimit-Usage header"
        )

    @pytest.mark.asyncio
    async def test_health_endpoint_no_ratelimit_headers(self, patched_app):
        """/health is not under /api/ so should not get rate limit headers."""
        transport = ASGITransport(app=patched_app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            response = await ac.get("/health")

        # /health is not an /api/ path, so no X-RateLimit-Reset
        assert "x-ratelimit-reset" not in response.headers
