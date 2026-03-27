"""Tests for SpotifyClient Redis cache helpers."""

import json
from unittest.mock import AsyncMock, patch

import pytest

from app.services.spotify_client import _args_hash, _cache_get, _cache_set


class TestArgsHash:
    """Test deterministic hashing of method arguments."""

    def test_same_args_produce_same_hash(self):
        assert _args_hash("medium_term", 50) == _args_hash("medium_term", 50)

    def test_different_args_produce_different_hash(self):
        assert _args_hash("short_term", 50) != _args_hash("medium_term", 50)

    def test_no_args_produces_consistent_hash(self):
        assert _args_hash() == _args_hash()

    def test_kwargs_order_irrelevant(self):
        h1 = _args_hash(a=1, b=2)
        h2 = _args_hash(b=2, a=1)
        assert h1 == h2

    def test_hash_length(self):
        h = _args_hash("medium_term", 50)
        assert len(h) == 12


class TestCacheGet:
    """Test Redis cache get with graceful degradation."""

    @pytest.mark.asyncio
    async def test_returns_parsed_json_on_hit(self):
        data = {"items": [1, 2, 3]}
        mock_redis = AsyncMock()
        mock_redis.get = AsyncMock(return_value=json.dumps(data))
        with patch("app.services.spotify_client.get_redis", return_value=mock_redis):
            result = await _cache_get("cache:user:1:me:abc123")
        assert result == data

    @pytest.mark.asyncio
    async def test_returns_none_on_miss(self):
        mock_redis = AsyncMock()
        mock_redis.get = AsyncMock(return_value=None)
        with patch("app.services.spotify_client.get_redis", return_value=mock_redis):
            result = await _cache_get("cache:user:1:me:abc123")
        assert result is None

    @pytest.mark.asyncio
    async def test_returns_none_on_redis_error(self):
        with patch(
            "app.services.spotify_client.get_redis",
            side_effect=ConnectionError("Redis down"),
        ):
            result = await _cache_get("cache:user:1:me:abc123")
        assert result is None


class TestCacheSet:
    """Test Redis cache set with fail-silent behavior."""

    @pytest.mark.asyncio
    async def test_sets_with_ttl(self):
        data = {"items": [1, 2, 3]}
        mock_redis = AsyncMock()
        mock_redis.set = AsyncMock()
        with patch("app.services.spotify_client.get_redis", return_value=mock_redis):
            await _cache_set("cache:user:1:me:abc123", data, 300)
        mock_redis.set.assert_awaited_once_with(
            "cache:user:1:me:abc123",
            json.dumps(data, default=str),
            ex=300,
        )

    @pytest.mark.asyncio
    async def test_silently_ignores_redis_error(self):
        with patch(
            "app.services.spotify_client.get_redis",
            side_effect=ConnectionError("Redis down"),
        ):
            # Should not raise
            await _cache_set("cache:user:1:me:abc123", {"x": 1}, 300)
