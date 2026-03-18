"""Test per genre_utils.py — unit test puro, nessuna dipendenza esterna."""


from app.services.genre_utils import (
    build_genre_vocabulary,
    compute_genre_similarity,
    genres_are_related,
    normalize_genre,
)


class TestNormalizeGenre:
    def test_lowercase_and_strip(self):
        assert normalize_genre("  Indie Rock  ") == "indie rock"

    def test_hyphens_to_spaces(self):
        assert normalize_genre("indie-rock") == "indie rock"

    def test_collapse_multiple_spaces(self):
        assert normalize_genre("hip  hop   soul") == "hip hop soul"

    def test_empty_string(self):
        assert normalize_genre("") == ""

    def test_already_normalized(self):
        assert normalize_genre("jazz") == "jazz"

    def test_mixed_case_and_hyphens(self):
        assert normalize_genre("Neo-Soul") == "neo soul"


class TestGenresAreRelated:
    def test_exact_match_after_normalization(self):
        assert genres_are_related("Indie Rock", "indie-rock") is True

    def test_substring_match(self):
        assert genres_are_related("rock", "hard rock") is True

    def test_substring_match_reverse(self):
        assert genres_are_related("hard rock", "rock") is True

    def test_token_overlap_short_genres(self):
        # "indie rock" and "indie pop" share "indie" — both have 2 tokens
        assert genres_are_related("indie rock", "indie pop") is True

    def test_token_overlap_long_genres_needs_two(self):
        # "modern progressive rock" and "classic jazz rock" — 3+ tokens,
        # share only "rock" (1 token) -> not enough
        assert genres_are_related("modern progressive rock", "classic jazz rock") is False

    def test_token_overlap_long_genres_two_shared(self):
        # "modern progressive rock" and "progressive rock fusion" share
        # "progressive" and "rock" (2 tokens) -> enough
        assert genres_are_related("modern progressive rock", "progressive rock fusion") is True

    def test_no_relation(self):
        assert genres_are_related("jazz", "metal") is False

    def test_empty_input(self):
        assert genres_are_related("", "rock") is False
        assert genres_are_related("rock", "") is False

    def test_same_genre(self):
        assert genres_are_related("pop", "pop") is True


class TestComputeGenreSimilarity:
    def test_identical_sets(self):
        genres = ["rock", "pop", "jazz"]
        score = compute_genre_similarity(genres, genres)
        assert score == 1.0

    def test_empty_a(self):
        assert compute_genre_similarity([], ["rock"]) == 0.0

    def test_empty_b(self):
        assert compute_genre_similarity(["rock"], []) == 0.0

    def test_both_empty(self):
        assert compute_genre_similarity([], []) == 0.0

    def test_no_overlap(self):
        assert compute_genre_similarity(["jazz"], ["metal"]) == 0.0

    def test_partial_overlap(self):
        score = compute_genre_similarity(["rock", "pop"], ["rock", "jazz"])
        # "rock" exact match = 1.0, "pop" vs "jazz" = 0.0
        # total = 1.0 / max(2, 2) = 0.5
        assert score == 0.5

    def test_substring_scoring(self):
        score = compute_genre_similarity(["rock"], ["hard rock"])
        # "rock" is substring of "hard rock" -> 0.7
        # total = 0.7 / max(1, 1) = 0.7
        assert score == 0.7

    def test_asymmetric_sizes(self):
        score = compute_genre_similarity(["rock"], ["rock", "pop", "jazz"])
        # "rock" exact match = 1.0
        # total = 1.0 / max(1, 3) = 0.3333
        assert abs(score - 0.3333) < 0.01

    def test_returns_float_in_range(self):
        score = compute_genre_similarity(
            ["indie rock", "dream pop", "shoegaze"],
            ["indie pop", "synth pop", "new wave"],
        )
        assert 0.0 <= score <= 1.0


class TestBuildGenreVocabulary:
    def test_basic(self):
        genres = ["rock", "pop", "rock", "jazz", "pop", "pop"]
        vocab = build_genre_vocabulary(genres, max_features=2)
        assert vocab == ["pop", "rock"]

    def test_normalization(self):
        genres = ["Indie-Rock", "indie rock", "Jazz"]
        vocab = build_genre_vocabulary(genres, max_features=10)
        # "indie rock" appears twice after normalization
        assert vocab[0] == "indie rock"

    def test_empty_input(self):
        assert build_genre_vocabulary([]) == []

    def test_max_features_limits_output(self):
        genres = ["a", "b", "c", "d", "e"]
        vocab = build_genre_vocabulary(genres, max_features=3)
        assert len(vocab) == 3

    def test_filters_empty_strings(self):
        genres = ["rock", "", "  ", "pop"]
        vocab = build_genre_vocabulary(genres)
        assert "" not in vocab
        assert len(vocab) == 2
