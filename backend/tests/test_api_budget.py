"""Tests for the priority-based API budget system.

Covers:
- check_budget tier limits and per-user share limits
- check_budget fail-open on Redis errors
- extend_cache_ttl TTL multiplication
- extend_cache_ttl fail-silent on Redis errors
- Integration: _throttle_check_and_register member format includes priority:user_id
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.api_budget import (
    TIER_LIMITS,
    Priority,
    check_budget,
    extend_cache_ttl,
)
from app.utils.rate_limiter import ThrottleError


class TestCheckBudget:
    """Tests for check_budget()."""

    @pytest.mark.asyncio
    async def test_allows_when_tier_under_limit(self):
        """Budget check passes when tier has room."""
        mock_redis = AsyncMock()
        # 3 P0 calls in window, well under limit of 17
        members = [
            f"aaa:{int(Priority.P0_INTERACTIVE)}:1",
            f"bbb:{int(Priority.P0_INTERACTIVE)}:2",
            f"ccc:{int(Priority.P0_INTERACTIVE)}:3",
        ]
        mock_redis.zrangebyscore.return_value = members

        with patch("app.services.api_budget.get_redis", return_value=mock_redis):
            result = await check_budget(user_id=1, priority=Priority.P0_INTERACTIVE)
            assert result is True

    @pytest.mark.asyncio
    async def test_denies_when_tier_at_limit(self):
        """Budget check fails when tier is full."""
        mock_redis = AsyncMock()
        # 17 P0 calls from various users — at the limit
        members = [
            f"{i:032x}:{int(Priority.P0_INTERACTIVE)}:{i % 5}"
            for i in range(TIER_LIMITS[Priority.P0_INTERACTIVE])
        ]
        mock_redis.zrangebyscore.return_value = members

        with patch("app.services.api_budget.get_redis", return_value=mock_redis):
            result = await check_budget(user_id=99, priority=Priority.P0_INTERACTIVE)
            assert result is False

    @pytest.mark.asyncio
    async def test_denies_when_user_exceeds_share(self):
        """Single user exceeding 30% of their tier gets denied."""
        mock_redis = AsyncMock()
        # P0 tier limit is 17, 30% of 17 = 5.1 → floor = 5
        # Put 5 calls from user 42 (at user limit)
        members = [f"{i:032x}:{int(Priority.P0_INTERACTIVE)}:42" for i in range(5)]
        mock_redis.zrangebyscore.return_value = members

        with patch("app.services.api_budget.get_redis", return_value=mock_redis):
            result = await check_budget(user_id=42, priority=Priority.P0_INTERACTIVE)
            assert result is False

    @pytest.mark.asyncio
    async def test_allows_different_user_when_one_is_capped(self):
        """User A at share limit should not block User B."""
        mock_redis = AsyncMock()
        # 5 calls from user 42, but user 99 asking
        members = [f"{i:032x}:{int(Priority.P0_INTERACTIVE)}:42" for i in range(5)]
        mock_redis.zrangebyscore.return_value = members

        with patch("app.services.api_budget.get_redis", return_value=mock_redis):
            result = await check_budget(user_id=99, priority=Priority.P0_INTERACTIVE)
            assert result is True

    @pytest.mark.asyncio
    async def test_p2_batch_has_lower_limit(self):
        """P2_BATCH tier limit is 3."""
        mock_redis = AsyncMock()
        # 3 P2 calls — at limit
        members = [
            f"{i:032x}:{int(Priority.P2_BATCH)}:{i}"
            for i in range(TIER_LIMITS[Priority.P2_BATCH])
        ]
        mock_redis.zrangebyscore.return_value = members

        with patch("app.services.api_budget.get_redis", return_value=mock_redis):
            result = await check_budget(user_id=99, priority=Priority.P2_BATCH)
            assert result is False

    @pytest.mark.asyncio
    async def test_ignores_other_tier_calls(self):
        """P0 budget check should not count P1 or P2 calls."""
        mock_redis = AsyncMock()
        # 20 P1 calls — should not affect P0 budget
        members = [
            f"{i:032x}:{int(Priority.P1_BACKGROUND_SYNC)}:{i}" for i in range(20)
        ]
        mock_redis.zrangebyscore.return_value = members

        with patch("app.services.api_budget.get_redis", return_value=mock_redis):
            result = await check_budget(user_id=1, priority=Priority.P0_INTERACTIVE)
            assert result is True

    @pytest.mark.asyncio
    async def test_failopen_on_redis_error(self):
        """Budget check should return True (allow) when Redis is down."""
        with patch(
            "app.services.api_budget.get_redis",
            side_effect=ConnectionError("Redis down"),
        ):
            result = await check_budget(user_id=1, priority=Priority.P0_INTERACTIVE)
            assert result is True

    @pytest.mark.asyncio
    async def test_legacy_members_ignored(self):
        """Members without priority encoding (legacy) are ignored for tier counting."""
        mock_redis = AsyncMock()
        # Mix of legacy (no colon) and new format members
        members = [
            "abc123legacy",  # legacy — no colons
            f"def456:{int(Priority.P0_INTERACTIVE)}:1",  # new format
        ]
        mock_redis.zrangebyscore.return_value = members

        with patch("app.services.api_budget.get_redis", return_value=mock_redis):
            result = await check_budget(user_id=1, priority=Priority.P0_INTERACTIVE)
            assert result is True  # only 1 P0 call, well under 17


class TestExtendCacheTtl:
    """Tests for extend_cache_ttl()."""

    @pytest.mark.asyncio
    async def test_doubles_ttl_for_matching_keys(self):
        mock_redis = AsyncMock()
        # scan returns cursor=0 (done) and 2 keys
        mock_redis.scan.return_value = (
            0,
            ["cache:user:1:top_tracks:abc", "cache:user:1:me:def"],
        )
        mock_redis.ttl.side_effect = [120, 300]  # current TTLs

        with patch("app.services.api_budget.get_redis", return_value=mock_redis):
            await extend_cache_ttl(user_id=1, multiplier=2)

        # Should have called expire with doubled TTLs
        assert mock_redis.expire.await_count == 2
        mock_redis.expire.assert_any_await("cache:user:1:top_tracks:abc", 240)
        mock_redis.expire.assert_any_await("cache:user:1:me:def", 600)

    @pytest.mark.asyncio
    async def test_skips_keys_with_no_ttl(self):
        mock_redis = AsyncMock()
        mock_redis.scan.return_value = (0, ["cache:user:1:no_ttl:abc"])
        mock_redis.ttl.return_value = -1  # no TTL set

        with patch("app.services.api_budget.get_redis", return_value=mock_redis):
            await extend_cache_ttl(user_id=1)

        mock_redis.expire.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_silent_on_redis_error(self):
        with patch(
            "app.services.api_budget.get_redis",
            side_effect=ConnectionError("Redis down"),
        ):
            # Should not raise
            await extend_cache_ttl(user_id=1)


class TestThrottleMemberFormat:
    """Tests that _throttle_check_and_register encodes priority:user_id in member."""

    @pytest.mark.asyncio
    async def test_member_includes_priority_and_user_id(self):
        mock_pipe = MagicMock()
        mock_pipe.execute = AsyncMock(
            return_value=[0, [], 1, True]  # empty window — under limit
        )

        mock_redis = MagicMock()
        mock_redis.pipeline.return_value = mock_pipe

        with patch("app.services.spotify_client.get_redis", return_value=mock_redis):
            from app.services.spotify_client import SpotifyClient

            await SpotifyClient._throttle_check_and_register(
                priority=Priority.P1_BACKGROUND_SYNC, user_id=42
            )

        # Check that zadd was called with a member containing ":1:42"
        zadd_calls = [call for call in mock_pipe.method_calls if call[0] == "zadd"]
        assert len(zadd_calls) == 1
        member_dict = zadd_calls[0][1][1]  # second positional arg is the dict
        member_key = list(member_dict.keys())[0]
        assert ":1:42" in member_key  # priority=1, user_id=42


class TestCheckAndRegisterLua:
    """Tests for _check_and_register (Lua script-based atomic check)."""

    @pytest.mark.asyncio
    async def test_allowed_call_passes_through(self):
        """When Lua returns allowed=1, no exception is raised."""
        from app.services.spotify_client import SpotifyClient

        mock_redis = AsyncMock()
        mock_redis.script_load = AsyncMock(return_value="fake_sha")
        # Lua returns: [allowed=1, reason=0, wait=0, count=1]
        mock_redis.evalsha = AsyncMock(return_value=[1, 0, 0, 1])

        with patch("app.services.spotify_client.get_redis", return_value=mock_redis):
            SpotifyClient._lua_sha = None
            client = SpotifyClient(
                AsyncMock(), user_id=1, priority=Priority.P0_INTERACTIVE
            )
            await client._check_and_register()

    @pytest.mark.asyncio
    async def test_cooldown_raises_rate_limit_error(self):
        """When Lua returns reason=1 (cooldown), RateLimitError is raised."""
        from app.services.spotify_client import SpotifyClient
        from app.utils.rate_limiter import RateLimitError

        mock_redis = AsyncMock()
        mock_redis.script_load = AsyncMock(return_value="fake_sha")
        # Lua returns: [allowed=0, reason=1(cooldown), wait=42, count=0]
        mock_redis.evalsha = AsyncMock(return_value=[0, 1, 42, 0])

        with patch("app.services.spotify_client.get_redis", return_value=mock_redis):
            SpotifyClient._lua_sha = None
            client = SpotifyClient(
                AsyncMock(), user_id=1, priority=Priority.P0_INTERACTIVE
            )
            with pytest.raises(RateLimitError) as exc_info:
                await client._check_and_register()
            assert exc_info.value.retry_after == 42.0

    @pytest.mark.asyncio
    async def test_tier_budget_exhausted_raises_throttle_error(self):
        """When Lua returns reason=2 (tier exhausted), ThrottleError is raised."""
        from app.services.spotify_client import SpotifyClient

        mock_redis = AsyncMock()
        mock_redis.script_load = AsyncMock(return_value="fake_sha")
        # Lua returns: [allowed=0, reason=2(tier), wait=0, count=17]
        mock_redis.evalsha = AsyncMock(return_value=[0, 2, 0, 17])

        with patch("app.services.spotify_client.get_redis", return_value=mock_redis):
            with patch(
                "app.services.spotify_client.extend_cache_ttl",
                new_callable=AsyncMock,
            ) as mock_extend:
                SpotifyClient._lua_sha = None
                client = SpotifyClient(
                    AsyncMock(), user_id=1, priority=Priority.P0_INTERACTIVE
                )
                with pytest.raises(ThrottleError):
                    await client._check_and_register()
                mock_extend.assert_awaited_once_with(1)

    @pytest.mark.asyncio
    async def test_user_budget_exhausted_raises_throttle_error(self):
        """When Lua returns reason=3 (user exhausted), ThrottleError is raised."""
        from app.services.spotify_client import SpotifyClient

        mock_redis = AsyncMock()
        mock_redis.script_load = AsyncMock(return_value="fake_sha")
        # Lua returns: [allowed=0, reason=3(user), wait=0, count=10]
        mock_redis.evalsha = AsyncMock(return_value=[0, 3, 0, 10])

        with patch("app.services.spotify_client.get_redis", return_value=mock_redis):
            with patch(
                "app.services.spotify_client.extend_cache_ttl",
                new_callable=AsyncMock,
            ) as mock_extend:
                SpotifyClient._lua_sha = None
                client = SpotifyClient(
                    AsyncMock(), user_id=42, priority=Priority.P0_INTERACTIVE
                )
                with pytest.raises(ThrottleError):
                    await client._check_and_register()
                mock_extend.assert_awaited_once_with(42)

    @pytest.mark.asyncio
    async def test_window_full_raises_throttle_error(self):
        """When Lua returns reason=4 (window full), ThrottleError with wait time."""
        from app.services.spotify_client import SpotifyClient

        mock_redis = AsyncMock()
        mock_redis.script_load = AsyncMock(return_value="fake_sha")
        # Lua returns: [allowed=0, reason=4(window), wait=10.5, count=25]
        mock_redis.evalsha = AsyncMock(return_value=[0, 4, 10.5, 25])

        with patch("app.services.spotify_client.get_redis", return_value=mock_redis):
            SpotifyClient._lua_sha = None
            client = SpotifyClient(
                AsyncMock(), user_id=1, priority=Priority.P0_INTERACTIVE
            )
            with pytest.raises(ThrottleError) as exc_info:
                await client._check_and_register()
            assert exc_info.value.retry_after == 10.5

    @pytest.mark.asyncio
    async def test_failopen_on_redis_error(self):
        """When Redis is unavailable, call is allowed (fail-open)."""
        from app.services.spotify_client import SpotifyClient

        with patch(
            "app.services.spotify_client.get_redis",
            side_effect=ConnectionError("Redis down"),
        ):
            SpotifyClient._lua_sha = None
            client = SpotifyClient(
                AsyncMock(), user_id=1, priority=Priority.P0_INTERACTIVE
            )
            # Should not raise — fail-open
            await client._check_and_register()

    @pytest.mark.asyncio
    async def test_noscript_reloads_and_retries(self):
        """NOSCRIPT error triggers script reload and successful retry."""
        from app.services.spotify_client import SpotifyClient

        mock_redis = AsyncMock()
        mock_redis.script_load = AsyncMock(return_value="new_sha")
        # First call: NOSCRIPT error, second call: success
        mock_redis.evalsha = AsyncMock(
            side_effect=[
                Exception("NOSCRIPT No matching script"),
                [1, 0, 0, 1],
            ]
        )

        with patch("app.services.spotify_client.get_redis", return_value=mock_redis):
            SpotifyClient._lua_sha = "stale_sha"
            client = SpotifyClient(
                AsyncMock(), user_id=1, priority=Priority.P0_INTERACTIVE
            )
            await client._check_and_register()

            # script_load should have been called to reload
            mock_redis.script_load.assert_awaited_once()
            assert mock_redis.evalsha.await_count == 2

    @pytest.mark.asyncio
    async def test_request_uses_lua_check(self):
        """_request calls _check_and_register (Lua path) instead of 3 separate checks."""
        from app.services.spotify_client import SpotifyClient

        mock_db = AsyncMock()

        with (
            patch.object(
                SpotifyClient,
                "_check_and_register",
                new_callable=AsyncMock,
            ) as mock_lua_check,
            patch.object(
                SpotifyClient,
                "_get_valid_token",
                new_callable=AsyncMock,
                return_value="fake_token",
            ),
            patch("httpx.AsyncClient.request") as mock_http,
        ):
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {"ok": True}
            mock_response.raise_for_status = MagicMock()
            mock_http.return_value = mock_response

            client = SpotifyClient(mock_db, user_id=5, priority=Priority.P2_BATCH)
            result = await client._request("GET", "https://api.spotify.com/v1/me")

            assert result == {"ok": True}
            mock_lua_check.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_request_lua_tier_exhausted_extends_cache(self):
        """When Lua returns tier exhausted, _request raises ThrottleError and extends cache."""
        from app.services.spotify_client import SpotifyClient

        mock_db = AsyncMock()
        mock_redis = AsyncMock()
        mock_redis.script_load = AsyncMock(return_value="fake_sha")
        mock_redis.evalsha = AsyncMock(return_value=[0, 2, 0, 17])

        with (
            patch("app.services.spotify_client.get_redis", return_value=mock_redis),
            patch(
                "app.services.spotify_client.extend_cache_ttl",
                new_callable=AsyncMock,
            ) as mock_extend,
        ):
            SpotifyClient._lua_sha = None
            client = SpotifyClient(mock_db, user_id=1, priority=Priority.P0_INTERACTIVE)
            with pytest.raises(ThrottleError):
                await client._request("GET", "https://api.spotify.com/v1/me")

            mock_extend.assert_awaited_once_with(1)
