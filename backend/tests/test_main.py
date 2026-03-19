"""Tests for rate limit status endpoint and RateLimitHeaderMiddleware in main.py.

Covers:
- /api/rate-limit-status includes window_reset_seconds field
- RateLimitHeaderMiddleware injects X-RateLimit-Reset header on /api/ responses
"""

from unittest.mock import patch

import pytest
from httpx import ASGITransport, AsyncClient


@pytest.fixture
def patched_app():
    """Import app with SpotifyClient class-level attributes safely mocked."""
    from collections import deque

    with (
        patch("app.services.spotify_client.SpotifyClient._call_timestamps", deque()),
        patch("app.services.spotify_client.SpotifyClient._cooldown_until", 0.0),
    ):
        from app.main import app

        yield app


class TestRateLimitStatusEndpoint:
    """Tests for GET /api/rate-limit-status."""

    @pytest.mark.asyncio
    async def test_response_includes_window_reset_seconds(self, patched_app):
        """The response body must contain the window_reset_seconds field."""
        transport = ASGITransport(app=patched_app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            response = await ac.get("/api/rate-limit-status")

        assert response.status_code == 200
        data = response.json()
        assert "window_reset_seconds" in data, (
            "Response must include 'window_reset_seconds' field"
        )
        assert isinstance(data["window_reset_seconds"], (int, float))

    @pytest.mark.asyncio
    async def test_response_includes_all_expected_fields(self, patched_app):
        """Verify the full shape of the rate limit status response."""
        transport = ASGITransport(app=patched_app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            response = await ac.get("/api/rate-limit-status")

        data = response.json()
        expected_fields = [
            "calls_in_window",
            "max_calls",
            "window_seconds",
            "usage_pct",
            "cooldown_remaining",
            "window_reset_seconds",
        ]
        for field in expected_fields:
            assert field in data, f"Missing field '{field}' in response"


class TestRateLimitHeaderMiddleware:
    """Tests for X-RateLimit-Reset header injection."""

    @pytest.mark.asyncio
    async def test_api_response_includes_ratelimit_reset_header(self, patched_app):
        """Every /api/ response must include X-RateLimit-Reset header."""
        transport = ASGITransport(app=patched_app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            response = await ac.get("/api/rate-limit-status")

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
            response = await ac.get("/api/rate-limit-status")

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
