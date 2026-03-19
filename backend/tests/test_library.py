"""Tests for library.py /api/library/top endpoint.

Covers:
- Tracks with popularity=0 get enriched via read_popularity_cache (DB only)
- Tracks with existing popularity are not re-fetched
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_spotify_track(
    track_id: str,
    name: str = "Test Track",
    popularity: int = 0,
    artist_id: str = "artist1234567890a",
    artist_name: str = "Test Artist",
) -> dict:
    """Build a Spotify-style track dict as returned by /me/top/tracks."""
    return {
        "id": track_id,
        "name": name,
        "artists": [{"id": artist_id, "name": artist_name}],
        "album": {
            "name": "Test Album",
            "images": [{"url": "https://img.example.com/cover.jpg"}],
        },
        "popularity": popularity,
        "duration_ms": 210000,
        "preview_url": None,
    }


def _make_client() -> MagicMock:
    client = MagicMock()
    client.user_id = 1
    client.get_top_tracks = AsyncMock()
    client.get_track = AsyncMock()
    client.close = AsyncMock()
    return client


async def _passthrough_retry(fn, *args, **kwargs):
    """Drop-in for retry_with_backoff that calls fn directly."""
    return await fn(*args, **kwargs)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestLibraryPopularityCache:
    """Tracks get popularity from DB cache (no API calls during page load)."""

    @pytest.mark.asyncio
    async def test_zero_popularity_tracks_read_from_cache(self):
        """When tracks have no popularity, read_popularity_cache is called."""
        client = _make_client()

        client.get_top_tracks.return_value = {
            "items": [
                _make_spotify_track("tid111111111111111", popularity=0),
                _make_spotify_track("tid222222222222222", popularity=0),
            ],
            "total": 2,
        }

        async def _fake_cache_read(tracks, db):
            """Simulate cache hit: set popularity from DB."""
            for t in tracks:
                if t.get("popularity", 0) == 0:
                    t["popularity"] = 75
            return 2

        with (
            patch("app.routers.library.SpotifyClient", return_value=client),
            patch("app.routers.library.require_auth", return_value=1),
            patch("app.routers.library.retry_with_backoff", _passthrough_retry),
            patch("app.routers.library.read_popularity_cache", side_effect=_fake_cache_read),
            patch("app.routers.library.get_or_fetch_features", AsyncMock(return_value={})),
            patch("app.routers.library.get_db", AsyncMock()),
        ):
            from app.routers.library import get_top_tracks

            mock_request = MagicMock()
            mock_db = AsyncMock()

            result = await get_top_tracks(
                request=mock_request,
                time_range="medium_term",
                limit=50,
                user_id=1,
                db=mock_db,
            )

        # Both tracks should now have popularity=75 from cache
        for track in result["tracks"]:
            assert track["popularity"] == 75

    @pytest.mark.asyncio
    async def test_nonzero_popularity_tracks_not_refetched(self):
        """Tracks that already have popularity > 0 are not modified."""
        client = _make_client()

        client.get_top_tracks.return_value = {
            "items": [
                _make_spotify_track("tid111111111111111", popularity=80),
                _make_spotify_track("tid222222222222222", popularity=55),
            ],
            "total": 2,
        }

        mock_cache = AsyncMock(return_value=0)

        with (
            patch("app.routers.library.SpotifyClient", return_value=client),
            patch("app.routers.library.require_auth", return_value=1),
            patch("app.routers.library.retry_with_backoff", _passthrough_retry),
            patch("app.routers.library.read_popularity_cache", mock_cache),
            patch("app.routers.library.get_or_fetch_features", AsyncMock(return_value={})),
            patch("app.routers.library.get_db", AsyncMock()),
        ):
            from app.routers.library import get_top_tracks

            mock_request = MagicMock()
            mock_db = AsyncMock()

            result = await get_top_tracks(
                request=mock_request,
                time_range="short_term",
                limit=50,
                user_id=1,
                db=mock_db,
            )

        assert result["tracks"][0]["popularity"] == 80
        assert result["tracks"][1]["popularity"] == 55

    @pytest.mark.asyncio
    async def test_cache_read_merges_correctly_into_response(self):
        """Cached popularity must appear in the final response dict."""
        client = _make_client()

        client.get_top_tracks.return_value = {
            "items": [
                _make_spotify_track("tid111111111111111", popularity=0),
                _make_spotify_track("tid222222222222222", popularity=90),
            ],
            "total": 2,
        }

        async def _fake_cache_read(tracks, db):
            for t in tracks:
                if t["id"] == "tid111111111111111" and t.get("popularity", 0) == 0:
                    t["popularity"] = 42
            return 1

        with (
            patch("app.routers.library.SpotifyClient", return_value=client),
            patch("app.routers.library.require_auth", return_value=1),
            patch("app.routers.library.retry_with_backoff", _passthrough_retry),
            patch("app.routers.library.read_popularity_cache", side_effect=_fake_cache_read),
            patch("app.routers.library.get_or_fetch_features", AsyncMock(return_value={})),
            patch("app.routers.library.get_db", AsyncMock()),
        ):
            from app.routers.library import get_top_tracks

            mock_request = MagicMock()
            mock_db = AsyncMock()

            result = await get_top_tracks(
                request=mock_request,
                time_range="long_term",
                limit=50,
                user_id=1,
                db=mock_db,
            )

        tracks = result["tracks"]
        enriched = [t for t in tracks if t["id"] == "tid111111111111111"][0]
        assert enriched["popularity"] == 42

        untouched = [t for t in tracks if t["id"] == "tid222222222222222"][0]
        assert untouched["popularity"] == 90
