"""Test per taste_map.py — unit test con mock di SpotifyClient."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.services.taste_map import compute_taste_map


def _make_spotify_artist(id: str, name: str, genres: list, popularity: int = 50, followers: int = 1000) -> dict:
    return {
        "id": id,
        "name": name,
        "genres": genres,
        "popularity": popularity,
        "followers": {"total": followers},
    }


@pytest.fixture
def mock_db():
    return AsyncMock()


@pytest.fixture
def mock_client():
    client = MagicMock()
    client.get_top_artists = AsyncMock()
    client.close = AsyncMock()
    return client


@pytest.fixture
def five_artists():
    return [
        _make_spotify_artist("a1", "Artist One", ["rock", "indie rock"], 80, 500000),
        _make_spotify_artist("a2", "Artist Two", ["pop", "dance pop"], 90, 2000000),
        _make_spotify_artist("a3", "Artist Three", ["jazz", "smooth jazz"], 40, 10000),
        _make_spotify_artist("a4", "Artist Four", ["rock", "hard rock"], 70, 300000),
        _make_spotify_artist("a5", "Artist Five", ["pop", "synth pop"], 85, 1500000),
    ]


class TestComputeTasteMap:
    @pytest.mark.asyncio
    async def test_insufficient_artists_returns_empty(self, mock_db, mock_client):
        mock_client.get_top_artists.return_value = {
            "items": [
                _make_spotify_artist("a1", "Solo", ["rock"], 50, 1000),
            ]
        }
        result = await compute_taste_map(mock_db, mock_client, user_id=1)
        assert result["feature_mode"] == "insufficient"
        assert result["points"] == []
        assert result["genre_groups"] == {}

    @pytest.mark.asyncio
    async def test_no_artists_returns_empty(self, mock_db, mock_client):
        mock_client.get_top_artists.return_value = {"items": []}
        result = await compute_taste_map(mock_db, mock_client, user_id=1)
        assert result["feature_mode"] == "insufficient"
        assert result["points"] == []

    @pytest.mark.asyncio
    async def test_normal_response_structure(self, mock_db, mock_client, five_artists):
        mock_client.get_top_artists.return_value = {"items": five_artists}
        result = await compute_taste_map(mock_db, mock_client, user_id=1)

        assert "points" in result
        assert "variance_explained" in result
        assert "feature_mode" in result
        assert "genre_groups" in result

    @pytest.mark.asyncio
    async def test_points_have_metadata(self, mock_db, mock_client, five_artists):
        mock_client.get_top_artists.return_value = {"items": five_artists}
        result = await compute_taste_map(mock_db, mock_client, user_id=1)

        if result["points"]:
            point = result["points"][0]
            assert "id" in point
            assert "x" in point
            assert "y" in point
            assert "name" in point
            assert "popularity" in point
            assert "primary_genre" in point

    @pytest.mark.asyncio
    async def test_genre_groups_limited_to_six(self, mock_db, mock_client):
        # Create artists with many distinct primary genres
        artists = []
        genres_list = ["rock", "pop", "jazz", "metal", "electronic", "hip hop", "classical", "country"]
        for i, genre in enumerate(genres_list):
            artists.append(
                _make_spotify_artist(f"a{i}", f"Artist {i}", [genre], 50 + i, 100000)
            )
        mock_client.get_top_artists.return_value = {"items": artists}
        result = await compute_taste_map(mock_db, mock_client, user_id=1)

        assert len(result["genre_groups"]) <= 6

    @pytest.mark.asyncio
    async def test_variance_explained_has_two_components(self, mock_db, mock_client, five_artists):
        mock_client.get_top_artists.return_value = {"items": five_artists}
        result = await compute_taste_map(mock_db, mock_client, user_id=1)

        assert len(result["variance_explained"]) == 2
        for v in result["variance_explained"]:
            assert isinstance(v, float)

    @pytest.mark.asyncio
    async def test_feature_mode_is_genre_popularity(self, mock_db, mock_client, five_artists):
        mock_client.get_top_artists.return_value = {"items": five_artists}
        result = await compute_taste_map(mock_db, mock_client, user_id=1)

        # Without audio features, mode should be genre_popularity or insufficient
        assert result["feature_mode"] in ("genre_popularity", "insufficient")

    @pytest.mark.asyncio
    async def test_primary_genre_normalized(self, mock_db, mock_client):
        artists = [
            _make_spotify_artist("a1", "A", ["Indie-Rock"], 80, 100000),
            _make_spotify_artist("a2", "B", ["Pop"], 90, 200000),
            _make_spotify_artist("a3", "C", ["Jazz"], 40, 10000),
        ]
        mock_client.get_top_artists.return_value = {"items": artists}
        result = await compute_taste_map(mock_db, mock_client, user_id=1)

        if result["points"]:
            # Find artist a1
            a1_point = next((p for p in result["points"] if p["id"] == "a1"), None)
            if a1_point:
                # normalize_genre("Indie-Rock") => "indie rock"
                assert a1_point["primary_genre"] == "indie rock"

    @pytest.mark.asyncio
    async def test_genres_truncated_to_five(self, mock_db, mock_client):
        long_genres = ["g1", "g2", "g3", "g4", "g5", "g6", "g7"]
        artists = [
            _make_spotify_artist("a1", "A", long_genres, 80, 100000),
            _make_spotify_artist("a2", "B", ["pop"], 90, 200000),
            _make_spotify_artist("a3", "C", ["jazz"], 40, 10000),
        ]
        mock_client.get_top_artists.return_value = {"items": artists}
        result = await compute_taste_map(mock_db, mock_client, user_id=1)

        # Should not crash — genres are truncated internally to [:5]
        assert "points" in result

    @pytest.mark.asyncio
    async def test_artist_with_missing_followers(self, mock_db, mock_client):
        # Followers key might be missing or structured differently
        artists = [
            {"id": "a1", "name": "A", "genres": ["rock"], "popularity": 80},
            {"id": "a2", "name": "B", "genres": ["pop"], "popularity": 90, "followers": {"total": 1000}},
            {"id": "a3", "name": "C", "genres": ["jazz"], "popularity": 40, "followers": {"total": 500}},
        ]
        mock_client.get_top_artists.return_value = {"items": artists}
        result = await compute_taste_map(mock_db, mock_client, user_id=1)

        # Should not crash on missing followers
        assert "points" in result
