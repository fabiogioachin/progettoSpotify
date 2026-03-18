"""Test per artist_network.py — unit test con mock di SpotifyClient."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.services.artist_network import build_artist_network, _empty_result


def _make_artist(id: str, name: str, genres: list, popularity: int = 50):
    """Helper per creare un artista mock."""
    return {
        "id": id,
        "name": name,
        "genres": genres,
        "popularity": popularity,
        "images": [{"url": f"https://img/{id}"}],
        "followers": {"total": 1000},
    }


def _make_client(short_items=None, medium_items=None, long_items=None):
    """Crea un mock SpotifyClient con risposte configurabili."""
    client = MagicMock()
    client.get_top_artists = AsyncMock(
        side_effect=lambda time_range="medium_term", limit=15: {
            "items": {
                "short_term": short_items or [],
                "medium_term": medium_items or [],
                "long_term": long_items or [],
            }.get(time_range, [])
        }
    )
    client.close = AsyncMock()
    return client


class TestEmptyResult:
    def test_has_all_required_keys(self):
        result = _empty_result()
        assert "nodes" in result
        assert "edges" in result
        assert "clusters" in result
        assert "cluster_names" in result
        assert "bridges" in result
        assert "top_genres" in result
        assert "data_quality" in result
        assert "metrics" in result

    def test_metrics_fields(self):
        result = _empty_result()
        assert result["metrics"]["total_nodes"] == 0
        assert result["metrics"]["total_edges"] == 0
        assert result["metrics"]["cluster_count"] == 0
        assert result["metrics"]["density"] == 0

    def test_data_quality_fields(self):
        result = _empty_result()
        assert result["data_quality"]["artists_without_genres"] == 0
        assert result["data_quality"]["warning"] is None


class TestBuildArtistNetwork:
    @pytest.mark.asyncio
    async def test_empty_when_no_artists(self):
        client = _make_client()
        result = await build_artist_network(client)
        assert result["nodes"] == []
        assert result["metrics"]["total_nodes"] == 0

    @pytest.mark.asyncio
    async def test_basic_graph_construction(self):
        artists = [
            _make_artist("a1", "Artist 1", ["rock", "indie rock"]),
            _make_artist("a2", "Artist 2", ["rock", "pop"]),
            _make_artist("a3", "Artist 3", ["jazz", "smooth jazz"]),
        ]
        client = _make_client(medium_items=artists)
        result = await build_artist_network(client)

        assert result["metrics"]["total_nodes"] == 3
        # a1 and a2 share "rock" -> should have an edge
        assert result["metrics"]["total_edges"] >= 1

    @pytest.mark.asyncio
    async def test_dedup_across_time_ranges(self):
        artist = _make_artist("a1", "Artist 1", ["rock"])
        client = _make_client(
            short_items=[artist],
            medium_items=[artist],
            long_items=[artist],
        )
        result = await build_artist_network(client)
        assert result["metrics"]["total_nodes"] == 1

    @pytest.mark.asyncio
    async def test_nodes_have_pagerank_and_betweenness(self):
        artists = [
            _make_artist("a1", "Artist 1", ["rock", "pop"]),
            _make_artist("a2", "Artist 2", ["rock", "indie"]),
        ]
        client = _make_client(medium_items=artists)
        result = await build_artist_network(client)

        for node in result["nodes"]:
            assert "pagerank" in node
            assert "betweenness" in node
            assert isinstance(node["pagerank"], float)
            assert isinstance(node["betweenness"], float)

    @pytest.mark.asyncio
    async def test_nodes_have_cluster_assignment(self):
        artists = [
            _make_artist("a1", "Artist 1", ["rock"]),
            _make_artist("a2", "Artist 2", ["rock"]),
        ]
        client = _make_client(medium_items=artists)
        result = await build_artist_network(client)

        for node in result["nodes"]:
            assert "cluster" in node
            assert isinstance(node["cluster"], int)

    @pytest.mark.asyncio
    async def test_edge_weight_is_float(self):
        artists = [
            _make_artist("a1", "Artist 1", ["rock", "indie rock"]),
            _make_artist("a2", "Artist 2", ["rock", "pop rock"]),
        ]
        client = _make_client(medium_items=artists)
        result = await build_artist_network(client)

        if result["edges"]:
            for edge in result["edges"]:
                assert isinstance(edge["weight"], float)
                assert 0.0 < edge["weight"] <= 1.0

    @pytest.mark.asyncio
    async def test_data_quality_warning_many_genreless(self):
        artists = [
            _make_artist("a1", "Artist 1", []),
            _make_artist("a2", "Artist 2", []),
            _make_artist("a3", "Artist 3", []),
            _make_artist("a4", "Artist 4", []),
            _make_artist("a5", "Artist 5", ["rock"]),
        ]
        client = _make_client(medium_items=artists)
        result = await build_artist_network(client)

        assert result["data_quality"]["artists_without_genres"] == 4
        assert result["data_quality"]["warning"] is not None
        assert "4" in result["data_quality"]["warning"]

    @pytest.mark.asyncio
    async def test_data_quality_no_warning_few_genreless(self):
        artists = [
            _make_artist("a1", "Artist 1", ["rock"]),
            _make_artist("a2", "Artist 2", ["pop"]),
            _make_artist("a3", "Artist 3", []),
        ]
        client = _make_client(medium_items=artists)
        result = await build_artist_network(client)

        assert result["data_quality"]["warning"] is None

    @pytest.mark.asyncio
    async def test_bridges_sorted_by_score(self):
        # Create a network where some nodes are more central
        artists = [
            _make_artist("a1", "A1", ["rock", "indie"]),
            _make_artist("a2", "A2", ["rock", "pop"]),
            _make_artist("a3", "A3", ["pop", "dance"]),
            _make_artist("a4", "A4", ["dance", "electronic"]),
            _make_artist("a5", "A5", ["electronic", "techno"]),
        ]
        client = _make_client(medium_items=artists)
        result = await build_artist_network(client)

        if len(result["bridges"]) > 1:
            scores = [b["bridge_score"] for b in result["bridges"]]
            assert scores == sorted(scores, reverse=True)

    @pytest.mark.asyncio
    async def test_density_in_metrics(self):
        artists = [
            _make_artist("a1", "A1", ["rock"]),
            _make_artist("a2", "A2", ["rock"]),
            _make_artist("a3", "A3", ["rock"]),
        ]
        client = _make_client(medium_items=artists)
        result = await build_artist_network(client)

        assert "density" in result["metrics"]
        assert isinstance(result["metrics"]["density"], float)
        assert 0.0 <= result["metrics"]["density"] <= 1.0

    @pytest.mark.asyncio
    async def test_spotify_auth_error_propagated(self):
        from app.utils.rate_limiter import SpotifyAuthError

        client = MagicMock()
        client.get_top_artists = AsyncMock(side_effect=SpotifyAuthError("expired"))
        client.close = AsyncMock()

        with pytest.raises(SpotifyAuthError):
            await build_artist_network(client)

    @pytest.mark.asyncio
    async def test_cluster_names_generated(self):
        artists = [
            _make_artist("a1", "A1", ["rock", "indie"]),
            _make_artist("a2", "A2", ["rock", "pop"]),
        ]
        client = _make_client(medium_items=artists)
        result = await build_artist_network(client)

        assert isinstance(result["cluster_names"], dict)
        # Should have at least one cluster name
        if result["metrics"]["cluster_count"] > 0:
            assert len(result["cluster_names"]) > 0

    @pytest.mark.asyncio
    async def test_max_five_bridges(self):
        # Create many connected artists
        artists = [
            _make_artist(f"a{i}", f"Artist {i}", ["rock", "pop"])
            for i in range(20)
        ]
        client = _make_client(medium_items=artists)
        result = await build_artist_network(client)

        assert len(result["bridges"]) <= 5
