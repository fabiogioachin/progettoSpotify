"""Test per profile_metrics.py — unit test per funzioni pure + bundle integration."""

from collections import Counter
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.data_bundle import RequestDataBundle
from app.services.profile_metrics import (
    compute_decade_distribution,
    compute_genre_diversity,
    compute_obscurity_score,
    compute_profile_metrics,
)


class TestComputeObscurityScore:
    def test_empty_artists(self):
        assert compute_obscurity_score([]) == 0.0

    def test_no_popularity(self):
        assert compute_obscurity_score([{"name": "A"}]) == 0.0

    def test_known_values(self):
        artists = [{"popularity": 80}, {"popularity": 60}]
        # avg popularity = 70, obscurity = 100 - 70 = 30
        assert compute_obscurity_score(artists) == 30.0

    def test_all_zero_popularity(self):
        artists = [{"popularity": 0}, {"popularity": 0}]
        assert compute_obscurity_score(artists) == 100.0


class TestComputeGenreDiversity:
    def test_empty_artists(self):
        assert compute_genre_diversity([]) == 0.0

    def test_single_genre(self):
        artists = [{"genres": ["rock"]}, {"genres": ["rock"]}]
        # Only one unique genre → entropy 0
        assert compute_genre_diversity(artists) == 0.0

    def test_diverse_genres(self):
        artists = [{"genres": ["rock"]}, {"genres": ["pop"]}, {"genres": ["jazz"]}]
        score = compute_genre_diversity(artists)
        assert 90.0 <= score <= 100.0  # Max entropy with 3 equal genres


class TestComputeDecadeDistribution:
    def test_empty_tracks(self):
        assert compute_decade_distribution([]) == {}

    def test_known_decades(self):
        tracks = [
            {"album": {"release_date": "1985-03-01"}},
            {"album": {"release_date": "1989-06-15"}},
            {"album": {"release_date": "2020-01-01"}},
        ]
        result = compute_decade_distribution(tracks)
        assert result == {"1980s": 2, "2020s": 1}

    def test_missing_release_date(self):
        tracks = [{"album": {"release_date": ""}}]
        assert compute_decade_distribution(tracks) == {}


class TestTopGenresFormat:
    """Verify that top_genres is built as list of dicts with genre+count."""

    def test_top_genres_structure(self):
        """Simulate the genre counting logic from compute_profile_metrics."""
        all_artists = [
            {"genres": ["rock", "indie"]},
            {"genres": ["rock", "pop"]},
            {"genres": ["pop", "electronic"]},
        ]
        genre_counter: Counter = Counter()
        for a in all_artists:
            for g in a.get("genres", []):
                genre_counter[g] += 1

        top_genres = [
            {"genre": g, "count": c} for g, c in genre_counter.most_common(10)
        ]

        assert len(top_genres) == 4
        assert all(isinstance(entry, dict) for entry in top_genres)
        assert all("genre" in entry and "count" in entry for entry in top_genres)
        # rock appears twice → should be first
        assert top_genres[0]["genre"] == "rock"
        assert top_genres[0]["count"] == 2
        # pop appears twice → second (or tied with rock)
        assert top_genres[1]["genre"] == "pop"
        assert top_genres[1]["count"] == 2

    def test_empty_genres(self):
        genre_counter: Counter = Counter()
        top_genres = [
            {"genre": g, "count": c} for g, c in genre_counter.most_common(10)
        ]
        assert top_genres == []

    def test_json_serialization(self):
        """Verify the format is JSON-serializable (for top_genres_json DB column)."""
        import json

        top_genres = [{"genre": "rock", "count": 5}, {"genre": "pop", "count": 3}]
        serialized = json.dumps(top_genres, ensure_ascii=False)
        deserialized = json.loads(serialized)
        assert deserialized == top_genres


class TestComputeProfileMetricsBundle:
    """Test that compute_profile_metrics uses bundle when provided."""

    @pytest.mark.asyncio
    async def test_uses_bundle_instead_of_client(self):
        """When bundle is provided, client.get_top_* should not be called."""
        mock_client = MagicMock()
        mock_client.get_top_artists = AsyncMock()
        mock_client.get_top_tracks = AsyncMock()

        artists_response = {"items": [
            {"popularity": 80, "genres": ["rock"]},
            {"popularity": 60, "genres": ["pop"]},
        ]}
        tracks_response = {"items": [
            {"album": {"release_date": "2020-01-01"}},
        ]}

        bundle = MagicMock(spec=RequestDataBundle)
        bundle.get_top_artists = AsyncMock(return_value=artists_response)
        bundle.get_top_tracks = AsyncMock(return_value=tracks_response)

        mock_db = AsyncMock()
        # Mock DB queries: scalar() calls for total_plays, total_artists, total_tracks
        mock_scalar = MagicMock()
        mock_scalar.scalar.return_value = 0
        mock_scalar.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = mock_scalar

        with patch("app.services.profile_metrics.async_session") as mock_session_factory:
            mock_write_db = AsyncMock()
            mock_write_result = MagicMock()
            mock_write_result.scalar_one_or_none.return_value = None
            mock_write_db.execute.return_value = mock_write_result

            mock_ctx = AsyncMock()
            mock_ctx.__aenter__ = AsyncMock(return_value=mock_write_db)
            mock_ctx.__aexit__ = AsyncMock(return_value=False)
            mock_session_factory.return_value = mock_ctx

            result = await compute_profile_metrics(
                mock_db, mock_client, user_id=1, bundle=bundle
            )

        # Bundle methods should be called, not client methods
        assert bundle.get_top_artists.await_count == 2  # short_term + long_term
        assert bundle.get_top_tracks.await_count == 1  # long_term
        mock_client.get_top_artists.assert_not_awaited()
        mock_client.get_top_tracks.assert_not_awaited()

        assert "obscurity_score" in result
        assert "genre_diversity_index" in result

    @pytest.mark.asyncio
    async def test_without_bundle_uses_client(self):
        """When bundle is None, falls back to retry_with_backoff(client.get_top_*)."""
        mock_client = MagicMock()
        mock_client.get_top_artists = AsyncMock(return_value={"items": []})
        mock_client.get_top_tracks = AsyncMock(return_value={"items": []})

        mock_db = AsyncMock()
        mock_scalar = MagicMock()
        mock_scalar.scalar.return_value = 0
        mock_scalar.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = mock_scalar

        with patch("app.services.profile_metrics.async_session") as mock_session_factory:
            mock_write_db = AsyncMock()
            mock_write_result = MagicMock()
            mock_write_result.scalar_one_or_none.return_value = None
            mock_write_db.execute.return_value = mock_write_result

            mock_ctx = AsyncMock()
            mock_ctx.__aenter__ = AsyncMock(return_value=mock_write_db)
            mock_ctx.__aexit__ = AsyncMock(return_value=False)
            mock_session_factory.return_value = mock_ctx

            result = await compute_profile_metrics(
                mock_db, mock_client, user_id=1, bundle=None
            )

        # Client methods should be called (via retry_with_backoff)
        assert mock_client.get_top_artists.await_count >= 1
        assert "obscurity_score" in result
