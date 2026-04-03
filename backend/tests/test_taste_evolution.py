"""Test per taste_evolution.py — unit test con mock di SpotifyClient."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.services.data_bundle import RequestDataBundle
from app.services.taste_evolution import compute_taste_evolution, _safe_fetch
from app.utils.rate_limiter import SpotifyAuthError


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_artist(id: str, name: str, genres: list | None = None, popularity: int = 50):
    """Helper per creare un artista mock."""
    return {
        "id": id,
        "name": name,
        "genres": genres or [],
        "popularity": popularity,
        "images": [{"url": f"https://img/{id}"}],
        "followers": {"total": 1000},
    }


def _make_track(id: str, name: str, artist_name: str = "Artist"):
    """Helper per creare un brano mock."""
    return {
        "id": id,
        "name": name,
        "artists": [{"name": artist_name}],
        "album": {
            "name": "Album",
            "images": [{"url": f"https://album/{id}"}],
        },
    }


def _make_client(
    short_artists=None,
    medium_artists=None,
    long_artists=None,
    short_tracks=None,
    medium_tracks=None,
    long_tracks=None,
):
    """Crea un mock SpotifyClient con risposte configurabili per artisti e brani."""
    artists_by_range = {
        "short_term": short_artists or [],
        "medium_term": medium_artists or [],
        "long_term": long_artists or [],
    }
    tracks_by_range = {
        "short_term": short_tracks or [],
        "medium_term": medium_tracks or [],
        "long_term": long_tracks or [],
    }

    client = MagicMock()
    client.get_top_artists = AsyncMock(
        side_effect=lambda time_range="medium_term", limit=50: {
            "items": artists_by_range.get(time_range, [])
        }
    )
    client.get_top_tracks = AsyncMock(
        side_effect=lambda time_range="medium_term", limit=50: {
            "items": tracks_by_range.get(time_range, [])
        }
    )
    return client


# ---------------------------------------------------------------------------
# _safe_fetch
# ---------------------------------------------------------------------------

class TestSafeFetch:
    @pytest.mark.asyncio
    async def test_returns_result_on_success(self):
        coro = AsyncMock(return_value={"items": [{"id": "a1"}]})
        result = await _safe_fetch(coro())
        assert result == {"items": [{"id": "a1"}]}

    @pytest.mark.asyncio
    async def test_propagates_spotify_auth_error(self):
        async def _raise():
            raise SpotifyAuthError("expired")

        with pytest.raises(SpotifyAuthError):
            await _safe_fetch(_raise())

    @pytest.mark.asyncio
    async def test_returns_empty_items_on_generic_error(self):
        async def _raise():
            raise RuntimeError("network error")

        result = await _safe_fetch(_raise())
        assert result == {"items": []}


# ---------------------------------------------------------------------------
# Output structure
# ---------------------------------------------------------------------------

class TestOutputStructure:
    @pytest.mark.asyncio
    async def test_return_has_expected_top_level_keys(self):
        client = _make_client()
        result = await compute_taste_evolution(client)
        assert "artists" in result
        assert "tracks" in result
        assert "metrics" in result
        assert "overlap_distribution" in result

    @pytest.mark.asyncio
    async def test_artists_has_expected_keys(self):
        client = _make_client()
        result = await compute_taste_evolution(client)
        assert "rising" in result["artists"]
        assert "falling" in result["artists"]
        assert "loyal" in result["artists"]

    @pytest.mark.asyncio
    async def test_tracks_has_expected_keys(self):
        client = _make_client()
        result = await compute_taste_evolution(client)
        assert "persistent" in result["tracks"]
        assert "rising" in result["tracks"]

    @pytest.mark.asyncio
    async def test_metrics_has_expected_keys(self):
        client = _make_client()
        result = await compute_taste_evolution(client)
        m = result["metrics"]
        expected = {
            "loyalty_score",
            "turnover_rate",
            "short_term_count",
            "medium_term_count",
            "long_term_count",
            "persistent_tracks_count",
        }
        assert expected.issubset(m.keys())

    @pytest.mark.asyncio
    async def test_overlap_distribution_has_three_buckets(self):
        client = _make_client()
        result = await compute_taste_evolution(client)
        od = result["overlap_distribution"]
        assert len(od) == 3
        labels = {entry["label"] for entry in od}
        assert labels == {"Passeggeri", "Consolidati", "Fedelissimi"}


# ---------------------------------------------------------------------------
# Empty responses
# ---------------------------------------------------------------------------

class TestEmptyResponses:
    @pytest.mark.asyncio
    async def test_all_empty(self):
        client = _make_client()
        result = await compute_taste_evolution(client)
        assert result["artists"]["rising"] == []
        assert result["artists"]["falling"] == []
        assert result["artists"]["loyal"] == []
        assert result["tracks"]["persistent"] == []
        assert result["tracks"]["rising"] == []
        assert result["metrics"]["loyalty_score"] == 0
        assert result["metrics"]["turnover_rate"] == 0

    @pytest.mark.asyncio
    async def test_only_short_term_has_data(self):
        artists = [_make_artist("a1", "Art1"), _make_artist("a2", "Art2")]
        tracks = [_make_track("t1", "Track1")]
        client = _make_client(short_artists=artists, short_tracks=tracks)
        result = await compute_taste_evolution(client)

        # All short-term artists are "rising" (not in long_term)
        assert len(result["artists"]["rising"]) == 2
        assert result["artists"]["loyal"] == []
        assert result["artists"]["falling"] == []
        # Tracks in short but not long -> rising
        assert len(result["tracks"]["rising"]) == 1
        assert result["tracks"]["persistent"] == []

    @pytest.mark.asyncio
    async def test_only_long_term_has_data(self):
        artists = [_make_artist("a1", "Art1")]
        client = _make_client(long_artists=artists)
        result = await compute_taste_evolution(client)

        # All long-term artists are "falling" (not in short_term)
        assert len(result["artists"]["falling"]) == 1
        assert result["artists"]["rising"] == []
        assert result["artists"]["loyal"] == []


# ---------------------------------------------------------------------------
# Three periods with real data
# ---------------------------------------------------------------------------

class TestThreePeriods:
    @pytest.mark.asyncio
    async def test_artists_classified_correctly(self):
        a1 = _make_artist("a1", "ShortOnly")
        a2 = _make_artist("a2", "AllPeriods")
        a3 = _make_artist("a3", "LongOnly")

        client = _make_client(
            short_artists=[a1, a2],
            medium_artists=[a2],
            long_artists=[a2, a3],
        )
        result = await compute_taste_evolution(client)

        rising_ids = {a["id"] for a in result["artists"]["rising"]}
        falling_ids = {a["id"] for a in result["artists"]["falling"]}
        loyal_ids = {a["id"] for a in result["artists"]["loyal"]}

        assert "a1" in rising_ids       # short only, not in long
        assert "a3" in falling_ids      # long only, not in short
        assert "a2" in loyal_ids        # present in all three

    @pytest.mark.asyncio
    async def test_tracks_classified_correctly(self):
        t1 = _make_track("t1", "ShortOnly")
        t2 = _make_track("t2", "AllPeriods")

        client = _make_client(
            short_tracks=[t1, t2],
            medium_tracks=[t2],
            long_tracks=[t2],
        )
        result = await compute_taste_evolution(client)

        persistent_ids = {t["id"] for t in result["tracks"]["persistent"]}
        rising_ids = {t["id"] for t in result["tracks"]["rising"]}

        assert "t2" in persistent_ids   # present in all three
        assert "t1" in rising_ids       # short only, not in long


# ---------------------------------------------------------------------------
# Metrics computation
# ---------------------------------------------------------------------------

class TestMetrics:
    @pytest.mark.asyncio
    async def test_loyalty_score(self):
        """loyalty_score = loyal / short_count * 100"""
        a_all = _make_artist("a1", "Loyal")
        a_short = _make_artist("a2", "ShortOnly")

        client = _make_client(
            short_artists=[a_all, a_short],
            medium_artists=[a_all],
            long_artists=[a_all],
        )
        result = await compute_taste_evolution(client)

        # 1 loyal out of 2 short = 50.0
        assert result["metrics"]["loyalty_score"] == 50.0

    @pytest.mark.asyncio
    async def test_turnover_rate(self):
        """turnover_rate = (short - medium) / short * 100"""
        a_both = _make_artist("a1", "Both")
        a_short_only = _make_artist("a2", "ShortOnly")

        client = _make_client(
            short_artists=[a_both, a_short_only],
            medium_artists=[a_both],
        )
        result = await compute_taste_evolution(client)

        # 1 in short but not medium, out of 2 short = 50.0
        assert result["metrics"]["turnover_rate"] == 50.0

    @pytest.mark.asyncio
    async def test_counts(self):
        client = _make_client(
            short_artists=[_make_artist("a1", "A1"), _make_artist("a2", "A2")],
            medium_artists=[_make_artist("a3", "A3")],
            long_artists=[
                _make_artist("a4", "A4"),
                _make_artist("a5", "A5"),
                _make_artist("a6", "A6"),
            ],
        )
        result = await compute_taste_evolution(client)
        assert result["metrics"]["short_term_count"] == 2
        assert result["metrics"]["medium_term_count"] == 1
        assert result["metrics"]["long_term_count"] == 3

    @pytest.mark.asyncio
    async def test_persistent_tracks_count(self):
        t_all = _make_track("t1", "Everywhere")
        client = _make_client(
            short_tracks=[t_all],
            medium_tracks=[t_all],
            long_tracks=[t_all],
        )
        result = await compute_taste_evolution(client)
        assert result["metrics"]["persistent_tracks_count"] == 1


# ---------------------------------------------------------------------------
# Overlap distribution
# ---------------------------------------------------------------------------

class TestOverlapDistribution:
    @pytest.mark.asyncio
    async def test_distribution_counts(self):
        a1 = _make_artist("a1", "InAll")       # in 3
        a2 = _make_artist("a2", "InTwo")       # in short + medium = 2
        a3 = _make_artist("a3", "InOne")       # long only = 1

        client = _make_client(
            short_artists=[a1, a2],
            medium_artists=[a1, a2],
            long_artists=[a1, a3],
        )
        result = await compute_taste_evolution(client)
        od = {e["label"]: e["count"] for e in result["overlap_distribution"]}

        assert od["Fedelissimi"] == 1   # a1 in all 3
        assert od["Consolidati"] == 1   # a2 in 2
        assert od["Passeggeri"] == 1    # a3 in 1


# ---------------------------------------------------------------------------
# Deduplication across periods
# ---------------------------------------------------------------------------

class TestDeduplication:
    @pytest.mark.asyncio
    async def test_same_artist_in_all_periods_counted_once(self):
        a = _make_artist("a1", "SameArtist")
        client = _make_client(
            short_artists=[a],
            medium_artists=[a],
            long_artists=[a],
        )
        result = await compute_taste_evolution(client)

        # Should appear as loyal, not duplicated in rising/falling
        assert len(result["artists"]["loyal"]) == 1
        assert result["artists"]["rising"] == []
        assert result["artists"]["falling"] == []

    @pytest.mark.asyncio
    async def test_same_track_in_all_periods_is_persistent(self):
        t = _make_track("t1", "SameTrack")
        client = _make_client(
            short_tracks=[t],
            medium_tracks=[t],
            long_tracks=[t],
        )
        result = await compute_taste_evolution(client)
        assert len(result["tracks"]["persistent"]) == 1
        assert result["tracks"]["rising"] == []


# ---------------------------------------------------------------------------
# Format helpers
# ---------------------------------------------------------------------------

class TestFormatOutput:
    @pytest.mark.asyncio
    async def test_artist_format(self):
        a = _make_artist("a1", "TestArtist")
        client = _make_client(short_artists=[a])
        result = await compute_taste_evolution(client)

        rising = result["artists"]["rising"]
        assert len(rising) == 1
        assert rising[0]["id"] == "a1"
        assert rising[0]["name"] == "TestArtist"
        assert rising[0]["image"] == "https://img/a1"

    @pytest.mark.asyncio
    async def test_artist_without_images(self):
        a = {
            "id": "a1",
            "name": "NoImage",
            "genres": [],
            "popularity": 50,
            "images": [],
            "followers": {"total": 0},
        }
        client = _make_client(short_artists=[a])
        result = await compute_taste_evolution(client)
        assert result["artists"]["rising"][0]["image"] is None

    @pytest.mark.asyncio
    async def test_track_format(self):
        t = _make_track("t1", "TestTrack", artist_name="ArtX")
        client = _make_client(short_tracks=[t])
        result = await compute_taste_evolution(client)

        rising = result["tracks"]["rising"]
        assert len(rising) == 1
        assert rising[0]["id"] == "t1"
        assert rising[0]["name"] == "TestTrack"
        assert rising[0]["artist"] == "ArtX"
        assert rising[0]["album_image"] == "https://album/t1"

    @pytest.mark.asyncio
    async def test_track_without_artists(self):
        t = {
            "id": "t1",
            "name": "NoArtist",
            "artists": [],
            "album": {"name": "A", "images": [{"url": "https://x"}]},
        }
        client = _make_client(short_tracks=[t])
        result = await compute_taste_evolution(client)
        assert result["tracks"]["rising"][0]["artist"] == ""


# ---------------------------------------------------------------------------
# Truncation limits
# ---------------------------------------------------------------------------

class TestTruncation:
    @pytest.mark.asyncio
    async def test_rising_artists_capped_at_15(self):
        artists = [_make_artist(f"a{i}", f"Art{i}") for i in range(25)]
        client = _make_client(short_artists=artists)
        result = await compute_taste_evolution(client)
        assert len(result["artists"]["rising"]) <= 15

    @pytest.mark.asyncio
    async def test_persistent_tracks_capped_at_10(self):
        tracks = [_make_track(f"t{i}", f"Track{i}") for i in range(20)]
        client = _make_client(
            short_tracks=tracks,
            medium_tracks=tracks,
            long_tracks=tracks,
        )
        result = await compute_taste_evolution(client)
        assert len(result["tracks"]["persistent"]) <= 10


# ---------------------------------------------------------------------------
# Error handling
# ---------------------------------------------------------------------------

class TestErrorHandling:
    @pytest.mark.asyncio
    async def test_spotify_auth_error_propagated(self):
        client = MagicMock()
        client.get_top_artists = AsyncMock(side_effect=SpotifyAuthError("expired"))
        client.get_top_tracks = AsyncMock(return_value={"items": []})

        with pytest.raises(SpotifyAuthError):
            await compute_taste_evolution(client)

    @pytest.mark.asyncio
    async def test_generic_error_handled_gracefully(self):
        """A non-auth error in one API call should not crash the function."""
        client = MagicMock()
        # get_top_artists always fails with generic error
        client.get_top_artists = AsyncMock(side_effect=RuntimeError("API down"))
        # get_top_tracks works fine
        client.get_top_tracks = AsyncMock(return_value={"items": []})

        # _safe_fetch swallows generic errors -> function should complete
        result = await compute_taste_evolution(client)
        assert result["metrics"]["short_term_count"] == 0


# ---------------------------------------------------------------------------
# Bundle integration
# ---------------------------------------------------------------------------


def _make_bundle(
    short_artists=None,
    medium_artists=None,
    long_artists=None,
    short_tracks=None,
    medium_tracks=None,
    long_tracks=None,
):
    """Crea un mock RequestDataBundle con risposte configurabili."""
    artists_by_range = {
        "short_term": short_artists or [],
        "medium_term": medium_artists or [],
        "long_term": long_artists or [],
    }
    tracks_by_range = {
        "short_term": short_tracks or [],
        "medium_term": medium_tracks or [],
        "long_term": long_tracks or [],
    }

    bundle = MagicMock(spec=RequestDataBundle)
    bundle.get_top_artists = AsyncMock(
        side_effect=lambda time_range="medium_term", limit=50: {
            "items": artists_by_range.get(time_range, [])
        }
    )
    bundle.get_top_tracks = AsyncMock(
        side_effect=lambda time_range="medium_term", limit=50: {
            "items": tracks_by_range.get(time_range, [])
        }
    )
    return bundle


class TestBundleIntegration:
    @pytest.mark.asyncio
    async def test_bundle_path_returns_same_structure(self):
        """Using bundle produces same output structure as client path."""
        a1 = _make_artist("a1", "ShortOnly")
        a2 = _make_artist("a2", "AllPeriods")
        t1 = _make_track("t1", "Track1")

        bundle = _make_bundle(
            short_artists=[a1, a2],
            medium_artists=[a2],
            long_artists=[a2],
            short_tracks=[t1],
            medium_tracks=[t1],
            long_tracks=[t1],
        )
        client = MagicMock()  # client should not be called when bundle is provided

        result = await compute_taste_evolution(client, bundle=bundle)

        assert "artists" in result
        assert "tracks" in result
        assert "metrics" in result
        assert "overlap_distribution" in result

    @pytest.mark.asyncio
    async def test_bundle_uses_bundle_not_client(self):
        """When bundle is provided, client.get_top_* should NOT be called."""
        bundle = _make_bundle()
        client = MagicMock()
        client.get_top_artists = AsyncMock()
        client.get_top_tracks = AsyncMock()

        await compute_taste_evolution(client, bundle=bundle)

        client.get_top_artists.assert_not_awaited()
        client.get_top_tracks.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_bundle_artists_classified_correctly(self):
        """Bundle path classifies artists correctly (same logic as client path)."""
        a1 = _make_artist("a1", "ShortOnly")
        a2 = _make_artist("a2", "AllPeriods")
        a3 = _make_artist("a3", "LongOnly")

        bundle = _make_bundle(
            short_artists=[a1, a2],
            medium_artists=[a2],
            long_artists=[a2, a3],
        )
        client = MagicMock()
        result = await compute_taste_evolution(client, bundle=bundle)

        rising_ids = {a["id"] for a in result["artists"]["rising"]}
        falling_ids = {a["id"] for a in result["artists"]["falling"]}
        loyal_ids = {a["id"] for a in result["artists"]["loyal"]}

        assert "a1" in rising_ids
        assert "a3" in falling_ids
        assert "a2" in loyal_ids

    @pytest.mark.asyncio
    async def test_bundle_none_falls_back_to_client(self):
        """When bundle=None, uses client (backward compat)."""
        client = _make_client(
            short_artists=[_make_artist("a1", "Art1")],
        )

        result = await compute_taste_evolution(client, bundle=None)
        assert len(result["artists"]["rising"]) == 1
