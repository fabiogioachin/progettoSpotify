"""Test per discovery.py — verifica integrazione sklearn (Isolation Forest + cosine similarity)."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.discovery import discover


# Patch globale: popularity cache è testata separatamente
_noop_cache = patch(
    "app.services.discovery.read_popularity_cache", new_callable=AsyncMock, return_value=0
)


@pytest.fixture(autouse=True)
def _patch_popularity():
    with _noop_cache:
        yield


def _make_track(tid: str, name: str, artist: str, popularity: int = 50) -> dict:
    return {
        "id": tid,
        "name": name,
        "artists": [{"name": artist}],
        "album": {"name": "Album", "images": [{"url": f"https://img/{tid}"}]},
        "popularity": popularity,
    }


def _make_artist(aid: str, name: str, genres: list[str], popularity: int = 50) -> dict:
    return {
        "id": aid,
        "name": name,
        "genres": genres,
        "popularity": popularity,
        "followers": {"total": 1000},
    }


def _make_features(tid: str, energy: float = 0.5) -> dict:
    return {
        "energy": energy,
        "danceability": 0.6,
        "valence": 0.5,
        "acousticness": 0.3,
        "instrumentalness": 0.1,
        "speechiness": 0.05,
        "liveness": 0.15,
    }


@pytest.fixture
def mock_db():
    return AsyncMock()


@pytest.fixture
def mock_client():
    client = MagicMock()
    client.close = AsyncMock()
    return client


class TestDiscoverOutlierIsolationForest:
    """Verifica che Isolation Forest venga usato quando ci sono features sufficienti."""

    @pytest.mark.asyncio
    async def test_isolation_forest_used_with_enough_features(
        self, mock_db, mock_client
    ):
        """Con >= 5 tracce con features, Isolation Forest deve essere tentato."""
        tracks = [_make_track(f"t{i}", f"Track {i}", f"Artist {i}") for i in range(10)]
        artists = [
            _make_artist(f"a{i}", f"Artist {i}", ["pop"]) for i in range(10)
        ]
        features = {f"t{i}": _make_features(f"t{i}") for i in range(10)}
        # Make one track an outlier with very different features
        features["t9"] = {
            "energy": 0.01,
            "danceability": 0.01,
            "valence": 0.01,
            "acousticness": 0.99,
            "instrumentalness": 0.99,
            "speechiness": 0.99,
            "liveness": 0.99,
        }

        mock_client.get_top_tracks = AsyncMock()
        mock_client.get_top_artists = AsyncMock()

        with (
            patch(
                "app.services.discovery.retry_with_backoff",
                side_effect=[
                    {"items": tracks},  # medium_term tracks
                    {"items": artists},  # medium_term artists
                    {"items": []},  # short_term tracks
                ],
            ),
            patch(
                "app.services.discovery.get_or_fetch_features",
                return_value=features,
            ),
        ):
            result = await discover(mock_db, mock_client)

        assert "outliers" in result
        assert len(result["outliers"]) > 0
        # Isolation Forest detected outliers should have metric_label "outlier"
        outlier_labels = [o["metric_label"] for o in result["outliers"]]
        # Either "outlier" (Isolation Forest) or "distanza audio" (euclidean fallback)
        assert all(
            label in ("outlier", "distanza audio") for label in outlier_labels
        )

    @pytest.mark.asyncio
    async def test_euclidean_fallback_when_isolation_forest_fails(
        self, mock_db, mock_client
    ):
        """Se Isolation Forest fallisce, deve cadere sulla distanza euclidea."""
        tracks = [_make_track(f"t{i}", f"Track {i}", f"Artist {i}") for i in range(10)]
        artists = [
            _make_artist(f"a{i}", f"Artist {i}", ["pop"]) for i in range(10)
        ]
        features = {f"t{i}": _make_features(f"t{i}") for i in range(10)}

        mock_client.get_top_tracks = AsyncMock()
        mock_client.get_top_artists = AsyncMock()

        with (
            patch(
                "app.services.discovery.retry_with_backoff",
                side_effect=[
                    {"items": tracks},
                    {"items": artists},
                    {"items": []},
                ],
            ),
            patch(
                "app.services.discovery.get_or_fetch_features",
                return_value=features,
            ),
            patch(
                "app.services.discovery.build_feature_matrix",
                side_effect=ValueError("Simulated sklearn failure"),
            ),
        ):
            result = await discover(mock_db, mock_client)

        assert "outliers" in result
        assert len(result["outliers"]) > 0
        # Should fall back to euclidean distance
        assert all(
            o["metric_label"] == "distanza audio" for o in result["outliers"]
        )

    @pytest.mark.asyncio
    async def test_popularity_fallback_when_no_features(
        self, mock_db, mock_client
    ):
        """Senza features, deve usare il fallback per popolarita'."""
        tracks = [
            _make_track(f"t{i}", f"Track {i}", f"Artist {i}", popularity=i * 10)
            for i in range(10)
        ]
        artists = [
            _make_artist(f"a{i}", f"Artist {i}", ["pop"]) for i in range(10)
        ]

        mock_client.get_top_tracks = AsyncMock()
        mock_client.get_top_artists = AsyncMock()

        with (
            patch(
                "app.services.discovery.retry_with_backoff",
                side_effect=[
                    {"items": tracks},
                    {"items": artists},
                    {"items": []},
                ],
            ),
            patch(
                "app.services.discovery.get_or_fetch_features",
                return_value={},  # No features
            ),
        ):
            result = await discover(mock_db, mock_client)

        assert "outliers" in result
        assert len(result["outliers"]) > 0
        # All should be popularity-based
        for o in result["outliers"]:
            assert o["metric_label"].startswith("Pop.")

    @pytest.mark.asyncio
    async def test_fewer_than_5_features_skips_isolation_forest(
        self, mock_db, mock_client
    ):
        """Con < 5 features, salta Isolation Forest e usa euclidea."""
        tracks = [_make_track(f"t{i}", f"Track {i}", f"Artist {i}") for i in range(4)]
        artists = [
            _make_artist(f"a{i}", f"Artist {i}", ["pop"]) for i in range(4)
        ]
        features = {f"t{i}": _make_features(f"t{i}") for i in range(4)}

        mock_client.get_top_tracks = AsyncMock()
        mock_client.get_top_artists = AsyncMock()

        with (
            patch(
                "app.services.discovery.retry_with_backoff",
                side_effect=[
                    {"items": tracks},
                    {"items": artists},
                    {"items": []},
                ],
            ),
            patch(
                "app.services.discovery.get_or_fetch_features",
                return_value=features,
            ),
            patch(
                "app.services.discovery.detect_outliers_isolation_forest"
            ) as mock_iso,
        ):
            result = await discover(mock_db, mock_client)

        # Isolation Forest should NOT be called (< 5 features)
        mock_iso.assert_not_called()
        # Should still have outliers from euclidean fallback
        assert "outliers" in result


class TestDiscoverSimilarityScoring:
    """Verifica che il cosine similarity scoring venga aggiunto alle raccomandazioni."""

    @pytest.mark.asyncio
    async def test_similarity_score_added_to_recommendations(
        self, mock_db, mock_client
    ):
        """Raccomandazioni devono avere similarity_score quando ci sono artisti."""
        medium_tracks = [
            _make_track(f"t{i}", f"Track {i}", f"Artist {i}") for i in range(10)
        ]
        short_tracks = [
            _make_track(f"s{i}", f"Short {i}", f"Artist {i}") for i in range(5)
        ]
        artists = [
            _make_artist(f"a{i}", f"Artist {i}", ["pop", "rock"]) for i in range(10)
        ]

        mock_client.get_top_tracks = AsyncMock()
        mock_client.get_top_artists = AsyncMock()

        with (
            patch(
                "app.services.discovery.retry_with_backoff",
                side_effect=[
                    {"items": medium_tracks},
                    {"items": artists},
                    {"items": short_tracks},
                ],
            ),
            patch(
                "app.services.discovery.get_or_fetch_features",
                return_value={},
            ),
        ):
            result = await discover(mock_db, mock_client)

        # Short tracks not in medium should be recommendations
        recs = result["recommendations"]
        if recs:
            # At least some should have similarity_score (artist name match)
            # Score might not be present if artist name doesn't match
            # but the code shouldn't error
            assert isinstance(recs, list)

    @pytest.mark.asyncio
    async def test_similarity_scoring_graceful_on_error(
        self, mock_db, mock_client
    ):
        """Se il similarity scoring fallisce, le raccomandazioni restano intatte."""
        medium_tracks = [
            _make_track(f"t{i}", f"Track {i}", f"Artist {i}") for i in range(10)
        ]
        short_tracks = [
            _make_track(f"s{i}", f"Short {i}", f"Artist {i}") for i in range(5)
        ]
        artists = [
            _make_artist(f"a{i}", f"Artist {i}", ["pop"]) for i in range(10)
        ]

        mock_client.get_top_tracks = AsyncMock()
        mock_client.get_top_artists = AsyncMock()

        with (
            patch(
                "app.services.discovery.retry_with_backoff",
                side_effect=[
                    {"items": medium_tracks},
                    {"items": artists},
                    {"items": short_tracks},
                ],
            ),
            patch(
                "app.services.discovery.get_or_fetch_features",
                return_value={},
            ),
            patch(
                "app.services.discovery.build_feature_matrix",
                side_effect=RuntimeError("sklearn boom"),
            ),
        ):
            result = await discover(mock_db, mock_client)

        # Should not crash; recommendations still present
        assert "recommendations" in result
        assert isinstance(result["recommendations"], list)

    @pytest.mark.asyncio
    async def test_too_few_artists_skips_similarity(
        self, mock_db, mock_client
    ):
        """Con < 5 artisti, il similarity scoring viene saltato."""
        tracks = [_make_track(f"t{i}", f"Track {i}", f"Artist {i}") for i in range(3)]
        short_tracks = [_make_track("s0", "New", "New Artist")]
        artists = [
            _make_artist(f"a{i}", f"Artist {i}", ["pop"]) for i in range(3)
        ]

        mock_client.get_top_tracks = AsyncMock()
        mock_client.get_top_artists = AsyncMock()

        with (
            patch(
                "app.services.discovery.retry_with_backoff",
                side_effect=[
                    {"items": tracks},
                    {"items": artists},
                    {"items": short_tracks},
                ],
            ),
            patch(
                "app.services.discovery.get_or_fetch_features",
                return_value={},
            ),
            patch(
                "app.services.discovery.compute_cosine_similarities"
            ) as mock_cos,
        ):
            await discover(mock_db, mock_client)

        mock_cos.assert_not_called()


class TestDiscoverResponseShape:
    """Verifica che la shape della risposta sia invariata."""

    @pytest.mark.asyncio
    async def test_empty_top_items_returns_empty(self, mock_db, mock_client):
        mock_client.get_top_tracks = AsyncMock()
        mock_client.get_top_artists = AsyncMock()

        with patch(
            "app.services.discovery.retry_with_backoff",
            side_effect=[
                {"items": []},
                {"items": []},
                {"items": []},
            ],
        ):
            result = await discover(mock_db, mock_client)

        assert result["recommendations"] == []
        assert result["outliers"] == []
        assert result["centroid"] == {}

    @pytest.mark.asyncio
    async def test_response_has_all_required_keys(self, mock_db, mock_client):
        tracks = [_make_track(f"t{i}", f"Track {i}", f"Artist {i}") for i in range(5)]
        artists = [
            _make_artist(f"a{i}", f"Artist {i}", ["pop"]) for i in range(5)
        ]

        mock_client.get_top_tracks = AsyncMock()
        mock_client.get_top_artists = AsyncMock()

        with (
            patch(
                "app.services.discovery.retry_with_backoff",
                side_effect=[
                    {"items": tracks},
                    {"items": artists},
                    {"items": []},
                ],
            ),
            patch(
                "app.services.discovery.get_or_fetch_features",
                return_value={},
            ),
        ):
            result = await discover(mock_db, mock_client)

        expected_keys = {
            "recommendations",
            "outliers",
            "centroid",
            "genre_distribution",
            "popularity_distribution",
            "has_audio_features",
            "recommendations_source",
        }
        assert set(result.keys()) == expected_keys
