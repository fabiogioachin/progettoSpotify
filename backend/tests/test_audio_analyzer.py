"""Tests for audio_analyzer.py — compute_profile and compute_trends."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.audio_analyzer import (
    _extract_genres,
    _safe_compute,
    compute_profile,
    compute_trends,
    get_or_fetch_features,
)
from app.utils.rate_limiter import SpotifyAuthError


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _passthrough_retry(fn, **kwargs):
    """Stand-in for retry_with_backoff that just awaits the function."""
    return await fn(**kwargs)


# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------

def _make_track(
    track_id: str,
    popularity: int = 50,
    artists: list[dict] | None = None,
) -> dict:
    """Build a minimal Spotify track dict for testing."""
    if artists is None:
        artists = [{"id": "art1", "name": "Artist One"}]
    return {
        "id": track_id,
        "popularity": popularity,
        "artists": artists,
    }


def _make_audio_feature_row(track_id: str, **overrides):
    """Build a mock AudioFeatures ORM row."""
    defaults = {
        "track_spotify_id": track_id,
        "danceability": 0.7,
        "energy": 0.8,
        "valence": 0.5,
        "acousticness": 0.3,
        "instrumentalness": 0.01,
        "liveness": 0.15,
        "speechiness": 0.05,
        "tempo": 120.0,
    }
    defaults.update(overrides)
    row = MagicMock()
    for k, v in defaults.items():
        setattr(row, k, v)
    return row


# ---------------------------------------------------------------------------
# compute_profile
# ---------------------------------------------------------------------------


class TestComputeProfile:
    """Tests for compute_profile()."""

    @pytest.mark.asyncio
    async def test_empty_tracks_returns_defaults(self):
        """When Spotify returns no items, all fields should be safe defaults."""
        client = MagicMock()
        client.get_top_tracks = AsyncMock(return_value={"items": []})
        db = AsyncMock()

        with patch(
            "app.services.audio_analyzer.retry_with_backoff",
            side_effect=_passthrough_retry,
        ):
            result = await compute_profile(db, client, "short_term")

        assert result["features"] == {}
        assert result["genres"] == {}
        assert result["track_count"] == 0
        assert result["popularity_avg"] == 0
        assert result["unique_artists"] == 0
        assert result["top_artist"] == "\u2014"

    @pytest.mark.asyncio
    async def test_output_structure_keys(self):
        """Return dict must contain all expected top-level keys."""
        tracks = [_make_track("t1", popularity=80), _make_track("t2", popularity=60)]
        client = MagicMock()
        client.get_top_tracks = AsyncMock(return_value={"items": tracks})
        db = AsyncMock()

        with (
            patch(
                "app.services.audio_analyzer.retry_with_backoff",
                side_effect=_passthrough_retry,
            ),
            patch(
                "app.services.audio_analyzer.read_popularity_cache",
                new_callable=AsyncMock,
            ),
            patch(
                "app.services.audio_analyzer.get_or_fetch_features",
                new_callable=AsyncMock,
                return_value={},
            ),
            patch(
                "app.services.audio_analyzer._extract_genres",
                new_callable=AsyncMock,
                return_value={"rock": 60.0, "pop": 40.0},
            ),
        ):
            result = await compute_profile(db, client, "medium_term")

        expected_keys = {
            "features",
            "genres",
            "track_count",
            "popularity_avg",
            "unique_artists",
            "top_artist",
        }
        assert set(result.keys()) == expected_keys

    @pytest.mark.asyncio
    async def test_popularity_averaging(self):
        """popularity_avg should be the rounded mean of track popularities."""
        tracks = [
            _make_track("t1", popularity=80),
            _make_track("t2", popularity=60),
            _make_track("t3", popularity=40),
        ]
        client = MagicMock()
        client.get_top_tracks = AsyncMock(return_value={"items": tracks})
        db = AsyncMock()

        with (
            patch(
                "app.services.audio_analyzer.retry_with_backoff",
                side_effect=_passthrough_retry,
            ),
            patch(
                "app.services.audio_analyzer.read_popularity_cache",
                new_callable=AsyncMock,
            ),
            patch(
                "app.services.audio_analyzer.get_or_fetch_features",
                new_callable=AsyncMock,
                return_value={},
            ),
            patch(
                "app.services.audio_analyzer._extract_genres",
                new_callable=AsyncMock,
                return_value={},
            ),
        ):
            result = await compute_profile(db, client, "short_term")

        assert result["popularity_avg"] == 60.0
        assert result["track_count"] == 3

    @pytest.mark.asyncio
    async def test_feature_averaging(self):
        """Audio features should be averaged across all cached tracks."""
        tracks = [_make_track("t1"), _make_track("t2")]
        client = MagicMock()
        client.get_top_tracks = AsyncMock(return_value={"items": tracks})
        db = AsyncMock()

        features_map = {
            "t1": {
                "danceability": 0.6,
                "energy": 0.8,
                "valence": 0.4,
                "acousticness": 0.2,
                "instrumentalness": 0.0,
                "liveness": 0.1,
                "speechiness": 0.05,
                "tempo": 100.0,
            },
            "t2": {
                "danceability": 0.8,
                "energy": 0.6,
                "valence": 0.6,
                "acousticness": 0.4,
                "instrumentalness": 0.02,
                "liveness": 0.2,
                "speechiness": 0.15,
                "tempo": 140.0,
            },
        }

        with (
            patch(
                "app.services.audio_analyzer.retry_with_backoff",
                side_effect=_passthrough_retry,
            ),
            patch(
                "app.services.audio_analyzer.read_popularity_cache",
                new_callable=AsyncMock,
            ),
            patch(
                "app.services.audio_analyzer.get_or_fetch_features",
                new_callable=AsyncMock,
                return_value=features_map,
            ),
            patch(
                "app.services.audio_analyzer._extract_genres",
                new_callable=AsyncMock,
                return_value={},
            ),
        ):
            result = await compute_profile(db, client, "medium_term")

        feats = result["features"]
        assert feats["danceability"] == 0.7
        assert feats["energy"] == 0.7
        assert feats["valence"] == 0.5
        assert feats["tempo"] == 120.0

    @pytest.mark.asyncio
    async def test_unique_artists_and_top_artist(self):
        """Verify artist counting across tracks."""
        tracks = [
            _make_track(
                "t1",
                artists=[
                    {"id": "a1", "name": "Alpha"},
                    {"id": "a2", "name": "Beta"},
                ],
            ),
            _make_track("t2", artists=[{"id": "a1", "name": "Alpha"}]),
            _make_track("t3", artists=[{"id": "a3", "name": "Gamma"}]),
        ]
        client = MagicMock()
        client.get_top_tracks = AsyncMock(return_value={"items": tracks})
        db = AsyncMock()

        with (
            patch(
                "app.services.audio_analyzer.retry_with_backoff",
                side_effect=_passthrough_retry,
            ),
            patch(
                "app.services.audio_analyzer.read_popularity_cache",
                new_callable=AsyncMock,
            ),
            patch(
                "app.services.audio_analyzer.get_or_fetch_features",
                new_callable=AsyncMock,
                return_value={},
            ),
            patch(
                "app.services.audio_analyzer._extract_genres",
                new_callable=AsyncMock,
                return_value={},
            ),
        ):
            result = await compute_profile(db, client, "short_term")

        assert result["unique_artists"] == 3
        assert result["top_artist"] == "Alpha"  # appears in 2 tracks

    @pytest.mark.asyncio
    async def test_pre_genres_skips_extract(self):
        """When pre_genres is provided, _extract_genres should NOT be called."""
        tracks = [_make_track("t1")]
        client = MagicMock()
        client.get_top_tracks = AsyncMock(return_value={"items": tracks})
        db = AsyncMock()

        pre = {"rock": 75.0, "pop": 25.0}

        with (
            patch(
                "app.services.audio_analyzer.retry_with_backoff",
                side_effect=_passthrough_retry,
            ),
            patch(
                "app.services.audio_analyzer.read_popularity_cache",
                new_callable=AsyncMock,
            ),
            patch(
                "app.services.audio_analyzer.get_or_fetch_features",
                new_callable=AsyncMock,
                return_value={},
            ),
            patch(
                "app.services.audio_analyzer._extract_genres",
                new_callable=AsyncMock,
            ) as mock_extract,
        ):
            result = await compute_profile(db, client, "short_term", pre_genres=pre)

        mock_extract.assert_not_called()
        assert result["genres"] == pre


# ---------------------------------------------------------------------------
# _safe_compute
# ---------------------------------------------------------------------------


class TestSafeCompute:
    """Tests for _safe_compute() error-barrier helper."""

    @pytest.mark.asyncio
    async def test_propagates_spotify_auth_error(self):
        """SpotifyAuthError must NOT be swallowed (Critical Invariant #1)."""

        async def _boom():
            raise SpotifyAuthError("expired")

        with pytest.raises(SpotifyAuthError):
            await _safe_compute(_boom(), "short_term")

    @pytest.mark.asyncio
    async def test_swallows_generic_exception(self):
        """Non-auth errors should return None, not crash."""

        async def _boom():
            raise RuntimeError("transient failure")

        result = await _safe_compute(_boom(), "medium_term")
        assert result is None

    @pytest.mark.asyncio
    async def test_returns_value_on_success(self):
        async def _ok():
            return {"features": {}}

        result = await _safe_compute(_ok(), "long_term")
        assert result == {"features": {}}


# ---------------------------------------------------------------------------
# compute_trends
# ---------------------------------------------------------------------------


class TestComputeTrends:
    """Tests for compute_trends()."""

    @pytest.mark.asyncio
    async def test_returns_three_periods(self):
        """Should return a list with entries for all 3 time ranges."""
        tracks = [_make_track("t1")]
        client = MagicMock()
        client.get_top_tracks = AsyncMock(return_value={"items": tracks})
        db = AsyncMock()

        with (
            patch(
                "app.services.audio_analyzer.retry_with_backoff",
                side_effect=_passthrough_retry,
            ),
            patch(
                "app.services.audio_analyzer.get_artist_genres_cached",
                new_callable=AsyncMock,
                return_value={},
            ),
            patch(
                "app.services.audio_analyzer.read_popularity_cache",
                new_callable=AsyncMock,
            ),
            patch(
                "app.services.audio_analyzer.get_or_fetch_features",
                new_callable=AsyncMock,
                return_value={},
            ),
        ):
            trends = await compute_trends(db, client, user_id=1)

        assert len(trends) == 3
        periods = [t["period"] for t in trends]
        assert periods == ["short_term", "medium_term", "long_term"]

    @pytest.mark.asyncio
    async def test_trend_entry_has_expected_keys(self):
        """Each trend entry should contain period, label, and profile keys."""
        tracks = [_make_track("t1", popularity=70)]
        client = MagicMock()
        client.get_top_tracks = AsyncMock(return_value={"items": tracks})
        db = AsyncMock()

        with (
            patch(
                "app.services.audio_analyzer.retry_with_backoff",
                side_effect=_passthrough_retry,
            ),
            patch(
                "app.services.audio_analyzer.get_artist_genres_cached",
                new_callable=AsyncMock,
                return_value={},
            ),
            patch(
                "app.services.audio_analyzer.read_popularity_cache",
                new_callable=AsyncMock,
            ),
            patch(
                "app.services.audio_analyzer.get_or_fetch_features",
                new_callable=AsyncMock,
                return_value={},
            ),
        ):
            trends = await compute_trends(db, client, user_id=1)

        entry = trends[0]
        required_keys = {
            "period",
            "label",
            "features",
            "genres",
            "track_count",
            "popularity_avg",
            "unique_artists",
            "top_artist",
        }
        assert required_keys.issubset(set(entry.keys()))

    @pytest.mark.asyncio
    async def test_genre_aggregation_across_artists(self):
        """Genres should be fetched once for all unique artists across periods."""
        tracks_short = [
            _make_track("t1", artists=[{"id": "a1", "name": "A"}]),
        ]
        tracks_medium = [
            _make_track("t2", artists=[{"id": "a2", "name": "B"}]),
        ]
        tracks_long = [
            _make_track("t3", artists=[{"id": "a1", "name": "A"}]),
        ]

        call_count = 0

        async def _mock_get_top_tracks(**kwargs):
            nonlocal call_count
            tr = kwargs.get("time_range", "")
            if tr == "short_term":
                return {"items": tracks_short}
            elif tr == "medium_term":
                return {"items": tracks_medium}
            else:
                return {"items": tracks_long}

        client = MagicMock()
        client.get_top_tracks = AsyncMock(side_effect=_mock_get_top_tracks)
        db = AsyncMock()

        genre_map = {"a1": ["rock", "indie"], "a2": ["pop"]}

        with (
            patch(
                "app.services.audio_analyzer.retry_with_backoff",
                side_effect=_passthrough_retry,
            ),
            patch(
                "app.services.audio_analyzer.get_artist_genres_cached",
                new_callable=AsyncMock,
                return_value=genre_map,
            ) as mock_genre_cache,
            patch(
                "app.services.audio_analyzer.read_popularity_cache",
                new_callable=AsyncMock,
            ),
            patch(
                "app.services.audio_analyzer.get_or_fetch_features",
                new_callable=AsyncMock,
                return_value={},
            ),
        ):
            trends = await compute_trends(db, client, user_id=1)

        # Genre cache should be called exactly ONCE with all unique artist IDs
        mock_genre_cache.assert_called_once()
        called_ids = set(mock_genre_cache.call_args[0][2])
        assert called_ids == {"a1", "a2"}

        # short_term has artist a1 -> rock, indie
        short = next(t for t in trends if t["period"] == "short_term")
        assert "rock" in short["genres"]

    @pytest.mark.asyncio
    async def test_spotify_auth_error_propagates_from_trends(self):
        """SpotifyAuthError during top_tracks fetch must propagate."""
        client = MagicMock()
        client.get_top_tracks = AsyncMock(side_effect=SpotifyAuthError("expired"))
        db = AsyncMock()

        with (
            patch(
                "app.services.audio_analyzer.retry_with_backoff",
                side_effect=_passthrough_retry,
            ),
            pytest.raises(SpotifyAuthError),
        ):
            await compute_trends(db, client, user_id=1)

    @pytest.mark.asyncio
    async def test_partial_failure_still_returns_successful_periods(self):
        """If one period fails (non-auth), the other periods should still appear."""
        call_num = 0

        async def _flaky_get_top_tracks(**kwargs):
            nonlocal call_num
            call_num += 1
            tr = kwargs.get("time_range", "")
            if tr == "medium_term":
                raise RuntimeError("transient error")
            return {"items": [_make_track("t1")]}

        client = MagicMock()
        client.get_top_tracks = AsyncMock(side_effect=_flaky_get_top_tracks)
        db = AsyncMock()

        with (
            patch(
                "app.services.audio_analyzer.retry_with_backoff",
                side_effect=_passthrough_retry,
            ),
            patch(
                "app.services.audio_analyzer.get_artist_genres_cached",
                new_callable=AsyncMock,
                return_value={},
            ),
            patch(
                "app.services.audio_analyzer.read_popularity_cache",
                new_callable=AsyncMock,
            ),
            patch(
                "app.services.audio_analyzer.get_or_fetch_features",
                new_callable=AsyncMock,
                return_value={},
            ),
        ):
            trends = await compute_trends(db, client, user_id=1)

        # medium_term raises RuntimeError both in compute_trends (caught, empty items)
        # AND again inside compute_profile (via retry_with_backoff -> get_top_tracks).
        # _safe_compute catches the second error and returns None, so medium_term is excluded.
        assert len(trends) == 2
        periods = [t["period"] for t in trends]
        assert "short_term" in periods
        assert "long_term" in periods
        assert "medium_term" not in periods

    @pytest.mark.asyncio
    async def test_bundle_deduplicates_api_calls(self):
        """When bundle is provided, retry_with_backoff should NOT be called.

        The bundle caches get_top_tracks results, so compute_trends and
        compute_profile both read from the bundle instead of calling the API.
        """
        tracks = [_make_track("t1")]
        bundle_mock = AsyncMock()
        bundle_mock.get_top_tracks = AsyncMock(return_value={"items": tracks})

        client = MagicMock()
        db = AsyncMock()

        with (
            patch(
                "app.services.audio_analyzer.retry_with_backoff",
                side_effect=_passthrough_retry,
            ) as mock_retry,
            patch(
                "app.services.audio_analyzer.get_artist_genres_cached",
                new_callable=AsyncMock,
                return_value={},
            ),
            patch(
                "app.services.audio_analyzer.read_popularity_cache",
                new_callable=AsyncMock,
            ),
            patch(
                "app.services.audio_analyzer.get_or_fetch_features",
                new_callable=AsyncMock,
                return_value={},
            ),
        ):
            trends = await compute_trends(db, client, user_id=1, bundle=bundle_mock)

        # retry_with_backoff must NOT have been called — bundle handles everything
        mock_retry.assert_not_called()

        # bundle.get_top_tracks called 6 times total (3 in compute_trends + 3 in compute_profile)
        # but with caching, the API is only hit 3 times (one per time_range)
        assert bundle_mock.get_top_tracks.call_count == 6
        assert len(trends) == 3

    @pytest.mark.asyncio
    async def test_compute_profile_uses_bundle_when_provided(self):
        """compute_profile should use bundle.get_top_tracks instead of retry_with_backoff."""
        tracks = [_make_track("t1", popularity=75)]
        bundle_mock = AsyncMock()
        bundle_mock.get_top_tracks = AsyncMock(return_value={"items": tracks})

        client = MagicMock()
        db = AsyncMock()

        with (
            patch(
                "app.services.audio_analyzer.retry_with_backoff",
                side_effect=_passthrough_retry,
            ) as mock_retry,
            patch(
                "app.services.audio_analyzer.read_popularity_cache",
                new_callable=AsyncMock,
            ),
            patch(
                "app.services.audio_analyzer.get_or_fetch_features",
                new_callable=AsyncMock,
                return_value={},
            ),
            patch(
                "app.services.audio_analyzer._extract_genres",
                new_callable=AsyncMock,
                return_value={},
            ),
        ):
            result = await compute_profile(
                db, client, "short_term", bundle=bundle_mock
            )

        mock_retry.assert_not_called()
        bundle_mock.get_top_tracks.assert_called_once_with(
            time_range="short_term", limit=50
        )
        assert result["track_count"] == 1


# ---------------------------------------------------------------------------
# get_or_fetch_features (DB-only cache lookup)
# ---------------------------------------------------------------------------


class TestGetOrFetchFeatures:
    """Tests for the DB-only audio features cache lookup."""

    @pytest.mark.asyncio
    async def test_empty_track_ids(self):
        db = AsyncMock()
        result = await get_or_fetch_features(db, [])
        assert result == {}

    @pytest.mark.asyncio
    async def test_returns_cached_features(self):
        """Should return feature dicts for tracks found in DB."""
        row = _make_audio_feature_row("t1", danceability=0.9, tempo=130.0)
        mock_result = MagicMock()
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = [row]
        mock_result.scalars.return_value = mock_scalars

        db = AsyncMock()
        db.execute = AsyncMock(return_value=mock_result)

        result = await get_or_fetch_features(db, ["t1", "t2"])

        assert "t1" in result
        assert result["t1"]["danceability"] == 0.9
        assert result["t1"]["tempo"] == 130.0
        # t2 not in DB -> not in result
        assert "t2" not in result


# ---------------------------------------------------------------------------
# _extract_genres
# ---------------------------------------------------------------------------


class TestExtractGenres:
    """Tests for the genre extraction helper."""

    @pytest.mark.asyncio
    async def test_no_artists_returns_empty(self):
        tracks = [{"id": "t1", "artists": []}]
        db = AsyncMock()
        client = MagicMock()
        result = await _extract_genres(db, client, tracks)
        assert result == {}

    @pytest.mark.asyncio
    async def test_genre_percentages_sum_to_100(self):
        tracks = [
            _make_track("t1", artists=[{"id": "a1", "name": "A"}]),
            _make_track("t2", artists=[{"id": "a2", "name": "B"}]),
        ]
        genre_map = {"a1": ["rock", "indie"], "a2": ["rock", "pop"]}
        db = AsyncMock()
        client = MagicMock()

        with patch(
            "app.services.audio_analyzer.get_artist_genres_cached",
            new_callable=AsyncMock,
            return_value=genre_map,
        ):
            result = await _extract_genres(db, client, tracks)

        total = sum(result.values())
        assert abs(total - 100.0) < 0.5  # rounding tolerance
        # rock appears 2x out of 4 total genre mentions -> 50%
        assert result["rock"] == 50.0
