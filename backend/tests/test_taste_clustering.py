"""Test per taste_clustering.py — unit test puro, nessuna dipendenza esterna."""

import numpy as np
import pytest

from app.services.taste_clustering import (
    build_feature_matrix,
    compute_cosine_similarities,
    compute_taste_pca,
    detect_outliers_isolation_forest,
    name_clusters,
    rank_within_cluster,
)


def _make_artist(id: str, name: str, genres: list, popularity: int = 50, followers: int = 1000, image: str | None = None) -> dict:
    return {
        "id": id,
        "name": name,
        "genres": genres,
        "popularity": popularity,
        "followers": followers,
        "image": image,
    }


# --- Sample fixtures ---

@pytest.fixture
def sample_artists():
    return [
        _make_artist("a1", "Artist One", ["rock", "indie rock"], 80, 500000),
        _make_artist("a2", "Artist Two", ["pop", "dance pop"], 90, 2000000),
        _make_artist("a3", "Artist Three", ["jazz", "smooth jazz"], 40, 10000),
        _make_artist("a4", "Artist Four", ["rock", "hard rock"], 70, 300000),
        _make_artist("a5", "Artist Five", ["pop", "synth pop"], 85, 1500000),
    ]


@pytest.fixture
def sample_audio_features():
    return {
        "a1": {"energy": 0.8, "danceability": 0.5, "valence": 0.6, "acousticness": 0.1, "instrumentalness": 0.0, "speechiness": 0.05, "liveness": 0.2},
        "a2": {"energy": 0.9, "danceability": 0.9, "valence": 0.8, "acousticness": 0.05, "instrumentalness": 0.0, "speechiness": 0.1, "liveness": 0.15},
        "a3": {"energy": 0.3, "danceability": 0.4, "valence": 0.5, "acousticness": 0.8, "instrumentalness": 0.3, "speechiness": 0.03, "liveness": 0.1},
    }


# =============================================================================
# build_feature_matrix
# =============================================================================

class TestBuildFeatureMatrix:
    def test_empty_artists(self):
        matrix, ids, names = build_feature_matrix([])
        assert matrix.shape == (0, 0)
        assert ids == []
        assert names == []

    def test_shape_without_audio(self, sample_artists):
        matrix, ids, names = build_feature_matrix(sample_artists)
        assert matrix.shape[0] == 5
        assert matrix.shape[1] == 22  # 20 genre + popularity + followers_log
        assert len(ids) == 5
        assert len(names) == 22

    def test_shape_with_audio(self, sample_artists, sample_audio_features):
        matrix, ids, names = build_feature_matrix(sample_artists, audio_features=sample_audio_features)
        assert matrix.shape[0] == 5
        assert matrix.shape[1] == 29  # 22 + 7 audio cols
        assert len(names) == 29

    def test_ids_preserved(self, sample_artists):
        matrix, ids, _ = build_feature_matrix(sample_artists)
        assert ids == ["a1", "a2", "a3", "a4", "a5"]

    def test_custom_genre_vocab(self, sample_artists):
        vocab = ["rock", "pop", "jazz"]
        matrix, ids, names = build_feature_matrix(sample_artists, genre_vocab=vocab)
        assert matrix.shape[1] == 22  # vocab padded to 20 + 2

    def test_feature_names_include_genres(self, sample_artists):
        _, _, names = build_feature_matrix(sample_artists)
        # First 20 are genre columns
        assert all(n.startswith("genre_") for n in names[:20])
        assert names[20] == "popularity"
        assert names[21] == "followers_log"

    def test_standardized_output(self, sample_artists):
        matrix, _, _ = build_feature_matrix(sample_artists)
        # StandardScaler: each column should have mean ~0, std ~1 (with 5 samples)
        col_means = matrix.mean(axis=0)
        assert np.allclose(col_means, 0, atol=1e-10)

    def test_single_artist(self):
        artists = [_make_artist("a1", "Solo", ["rock"], 50, 1000)]
        matrix, ids, names = build_feature_matrix(artists)
        assert matrix.shape[0] == 1
        # StandardScaler on 1 sample => all zeros (no variance)
        assert np.allclose(matrix, 0)

    def test_empty_audio_features_dict(self, sample_artists):
        matrix, _, names = build_feature_matrix(sample_artists, audio_features={})
        # Empty dict => no audio columns
        assert matrix.shape[1] == 22


# =============================================================================
# name_clusters
# =============================================================================

class TestNameClusters:
    def test_empty_inputs(self):
        assert name_clusters({}, []) == {}

    def test_single_cluster(self, sample_artists):
        labels = {"a1": 0, "a2": 0, "a3": 0, "a4": 0, "a5": 0}
        names = name_clusters(labels, sample_artists)
        assert 0 in names
        assert isinstance(names[0], str)
        assert len(names[0]) > 0

    def test_two_clusters(self, sample_artists):
        labels = {"a1": 0, "a4": 0, "a2": 1, "a5": 1, "a3": 1}
        names = name_clusters(labels, sample_artists)
        assert len(names) == 2
        assert 0 in names
        assert 1 in names

    def test_fallback_name(self):
        # Artists with no genres
        artists = [_make_artist("a1", "No Genre", [], 50, 1000)]
        labels = {"a1": 0}
        names = name_clusters(labels, artists)
        assert names[0] == "Cerchia 1"

    def test_names_are_title_cased(self, sample_artists):
        labels = {"a1": 0, "a4": 0}
        names = name_clusters(labels, sample_artists)
        # The name should be title-cased
        assert names[0] == names[0].title()


# =============================================================================
# rank_within_cluster
# =============================================================================

class TestRankWithinCluster:
    def test_empty_inputs(self):
        assert rank_within_cluster({}, [], {}) == {}

    def test_basic_ranking(self, sample_artists):
        labels = {"a1": 0, "a2": 0, "a3": 1}
        pagerank = {"a1": 0.5, "a2": 0.3, "a3": 0.1}
        result = rank_within_cluster(labels, sample_artists, pagerank)

        assert 0 in result
        assert 1 in result
        assert len(result[0]) == 2
        assert len(result[1]) == 1

    def test_ranks_are_one_based(self, sample_artists):
        labels = {"a1": 0, "a2": 0, "a4": 0}
        pagerank = {"a1": 0.5, "a2": 0.3, "a4": 0.2}
        result = rank_within_cluster(labels, sample_artists, pagerank)

        ranks = [item["rank"] for item in result[0]]
        assert sorted(ranks) == [1, 2, 3]

    def test_output_fields(self, sample_artists):
        labels = {"a1": 0}
        pagerank = {"a1": 0.5}
        result = rank_within_cluster(labels, sample_artists, pagerank)

        item = result[0][0]
        assert "id" in item
        assert "name" in item
        assert "image" in item
        assert "score" in item
        assert "rank" in item
        assert item["rank"] == 1

    def test_score_range(self, sample_artists):
        labels = {a["id"]: 0 for a in sample_artists}
        pagerank = {a["id"]: 0.2 for a in sample_artists}
        result = rank_within_cluster(labels, sample_artists, pagerank)

        for item in result[0]:
            assert 0.0 <= item["score"] <= 1.0

    def test_missing_pagerank_defaults_to_zero(self, sample_artists):
        labels = {"a1": 0, "a2": 0}
        pagerank = {"a1": 0.5}  # a2 missing
        result = rank_within_cluster(labels, sample_artists, pagerank)
        assert len(result[0]) == 2


# =============================================================================
# compute_taste_pca
# =============================================================================

class TestComputeTastePca:
    def test_insufficient_data_few_artists(self):
        matrix = np.array([[1, 2], [3, 4]])
        result = compute_taste_pca(matrix, ["a1", "a2"])
        assert result["feature_mode"] == "insufficient"
        assert result["points"] == []

    def test_genre_popularity_mode(self, sample_artists):
        matrix, ids, _ = build_feature_matrix(sample_artists)
        result = compute_taste_pca(matrix, ids)
        assert result["feature_mode"] in ("genre_popularity", "insufficient")
        assert len(result["variance_explained"]) == 2
        if result["feature_mode"] != "insufficient":
            assert len(result["points"]) == 5

    def test_audio_mode(self, sample_artists, sample_audio_features):
        matrix, ids, _ = build_feature_matrix(sample_artists, audio_features=sample_audio_features)
        result = compute_taste_pca(matrix, ids)
        # 29 cols > 22 => audio mode (unless insufficient variance)
        if result["feature_mode"] != "insufficient":
            assert result["feature_mode"] == "audio"

    def test_points_have_x_y(self, sample_artists):
        matrix, ids, _ = build_feature_matrix(sample_artists)
        result = compute_taste_pca(matrix, ids)
        if result["points"]:
            point = result["points"][0]
            assert "id" in point
            assert "x" in point
            assert "y" in point

    def test_variance_explained_values(self, sample_artists):
        matrix, ids, _ = build_feature_matrix(sample_artists)
        result = compute_taste_pca(matrix, ids)
        for v in result["variance_explained"]:
            assert 0.0 <= v <= 1.0


# =============================================================================
# compute_cosine_similarities
# =============================================================================

class TestComputeCosineSimilarities:
    def test_empty_matrix(self):
        result = compute_cosine_similarities(np.empty((0, 5)), [])
        assert result == {}

    def test_single_artist(self):
        matrix = np.array([[1.0, 2.0, 3.0]])
        result = compute_cosine_similarities(matrix, ["a1"])
        assert "a1" in result
        # Single artist IS the centroid => similarity = 100
        assert result["a1"] == 100

    def test_returns_numeric_scores(self, sample_artists):
        matrix, ids, _ = build_feature_matrix(sample_artists)
        result = compute_cosine_similarities(matrix, ids)
        assert len(result) == 5
        for aid, score in result.items():
            assert isinstance(score, (int, float))
            assert 0 <= score <= 100

    def test_identical_artists_all_high(self):
        # All identical rows => all same as centroid
        matrix = np.tile([1, 0, 1, 0], (5, 1)).astype(float)
        ids = [f"a{i}" for i in range(5)]
        result = compute_cosine_similarities(matrix, ids)
        for score in result.values():
            assert score == 100


# =============================================================================
# detect_outliers_isolation_forest
# =============================================================================

class TestDetectOutliersIsolationForest:
    def test_too_few_rows(self):
        matrix = np.random.rand(3, 5)
        result = detect_outliers_isolation_forest(matrix, ["a1", "a2", "a3"])
        assert result == []

    def test_returns_list_of_ids(self, sample_artists):
        matrix, ids, _ = build_feature_matrix(sample_artists)
        result = detect_outliers_isolation_forest(matrix, ids)
        assert isinstance(result, list)
        for aid in result:
            assert aid in ids

    def test_obvious_outlier(self):
        # 9 similar artists + 1 very different
        normal = np.tile([1, 1, 1, 1, 1], (9, 1)).astype(float)
        outlier = np.array([[100, 100, 100, 100, 100]], dtype=float)
        matrix = np.vstack([normal, outlier])
        ids = [f"a{i}" for i in range(10)]
        result = detect_outliers_isolation_forest(matrix, ids, contamination=0.1)
        # The outlier should be detected
        assert "a9" in result

    def test_empty_matrix(self):
        result = detect_outliers_isolation_forest(np.empty((0, 5)), [])
        assert result == []

    def test_deterministic(self, sample_artists):
        matrix, ids, _ = build_feature_matrix(sample_artists)
        r1 = detect_outliers_isolation_forest(matrix, ids)
        r2 = detect_outliers_isolation_forest(matrix, ids)
        assert r1 == r2  # random_state=42 ensures determinism
