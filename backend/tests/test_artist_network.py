"""Test per artist_network.py — unit test con mock di SpotifyClient."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.artist_network import build_artist_network, _dedup_cluster_names, _empty_result
from app.services.data_bundle import RequestDataBundle


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

    @pytest.mark.asyncio
    async def test_genreless_artists_remain_isolated(self):
        """Artists without genres should NOT get connected via popularity fallback."""
        artists = [
            _make_artist("a1", "Artist 1", [], popularity=50),
            _make_artist("a2", "Artist 2", [], popularity=55),
            _make_artist("a3", "Artist 3", ["rock"]),
        ]
        client = _make_client(medium_items=artists)
        result = await build_artist_network(client)

        # a1 and a2 have no genres — they should remain isolated (no edges)
        edge_pairs = {
            tuple(sorted([e["source"], e["target"]])) for e in result["edges"]
        }
        assert ("a1", "a2") not in edge_pairs

    @pytest.mark.asyncio
    async def test_all_genreless_zero_edges(self):
        """When all artists lack genres, there should be zero edges."""
        artists = [
            _make_artist("a1", "Artist 1", [], popularity=0),
            _make_artist("a2", "Artist 2", [], popularity=0),
            _make_artist("a3", "Artist 3", [], popularity=0),
        ]
        client = _make_client(medium_items=artists)
        result = await build_artist_network(client)

        assert result["metrics"]["total_edges"] == 0


class TestSingletonFiltering:
    """Singleton clusters (1 artist) should be excluded from display dicts."""

    @pytest.mark.asyncio
    async def test_singletons_excluded_from_cluster_names(self):
        """cluster_names should not contain clusters with only 1 artist."""
        artists = [
            _make_artist("a1", "A1", ["rock", "indie"]),
            _make_artist("a2", "A2", ["rock", "pop"]),
            _make_artist("a3", "A3", ["jazz"]),  # isolated → singleton
        ]
        client = _make_client(medium_items=artists)
        result = await build_artist_network(client)

        # a1 and a2 share "rock" → same cluster. a3 is isolated → singleton.
        # cluster_names should only contain the multi-artist cluster.
        for cid, name in result["cluster_names"].items():
            # Count how many nodes belong to this cluster
            cluster_node_count = sum(
                1 for n in result["nodes"] if n["cluster"] == cid
            )
            assert cluster_node_count > 1, (
                f"Singleton cluster {cid} ('{name}') should not be in cluster_names"
            )

    @pytest.mark.asyncio
    async def test_singletons_excluded_from_cluster_rankings(self):
        """cluster_rankings should not contain singleton clusters."""
        artists = [
            _make_artist("a1", "A1", ["rock", "indie"]),
            _make_artist("a2", "A2", ["rock", "pop"]),
            _make_artist("a3", "A3", []),  # no genres → isolated
        ]
        client = _make_client(medium_items=artists)
        result = await build_artist_network(client)

        for cid_str in result["cluster_rankings"]:
            cid = int(cid_str)
            cluster_node_count = sum(
                1 for n in result["nodes"] if n["cluster"] == cid
            )
            assert cluster_node_count > 1

    @pytest.mark.asyncio
    async def test_cluster_count_excludes_singletons(self):
        """metrics.cluster_count should only count multi-artist clusters."""
        artists = [
            _make_artist("a1", "A1", ["rock", "indie"]),
            _make_artist("a2", "A2", ["rock", "pop"]),
            _make_artist("a3", "A3", []),
            _make_artist("a4", "A4", []),
        ]
        client = _make_client(medium_items=artists)
        result = await build_artist_network(client)

        # Only the rock cluster has >1 artist. The genreless ones are singletons.
        assert result["metrics"]["cluster_count"] <= 1

    @pytest.mark.asyncio
    async def test_all_singletons_zero_cluster_count(self):
        """When all clusters are singletons, cluster_count should be 0."""
        artists = [
            _make_artist("a1", "A1", []),
            _make_artist("a2", "A2", []),
        ]
        client = _make_client(medium_items=artists)
        result = await build_artist_network(client)

        assert result["metrics"]["cluster_count"] == 0
        assert result["cluster_names"] == {}
        assert result["cluster_rankings"] == {}

    @pytest.mark.asyncio
    async def test_node_cluster_field_preserved_for_singletons(self):
        """Nodes in singleton clusters still have their cluster field (for SVG coloring)."""
        artists = [
            _make_artist("a1", "A1", ["rock", "pop"]),
            _make_artist("a2", "A2", ["rock", "indie"]),
            _make_artist("a3", "A3", []),  # singleton
        ]
        client = _make_client(medium_items=artists)
        result = await build_artist_network(client)

        # Every node must have a cluster field
        for node in result["nodes"]:
            assert "cluster" in node
            assert isinstance(node["cluster"], int)


class TestClusterNameDeduplication:
    """When two clusters have the same name, they should be differentiated."""

    @pytest.mark.asyncio
    async def test_duplicate_names_get_suffix(self):
        """Two clusters with the same primary genre get differentiated."""
        # Build a scenario with two separate hip-hop groups
        # Group 1: hip-hop + trap artists
        # Group 2: hip-hop + r&b artists
        # They don't share edges, so Louvain puts them in separate clusters.
        artists = [
            _make_artist("a1", "A1", ["hip-hop", "trap", "drill"]),
            _make_artist("a2", "A2", ["hip-hop", "trap"]),
            _make_artist("a3", "A3", ["hip-hop", "trap", "drill"]),
            _make_artist("a4", "A4", ["hip-hop", "r&b", "soul"]),
            _make_artist("a5", "A5", ["hip-hop", "r&b"]),
            _make_artist("a6", "A6", ["hip-hop", "r&b", "soul"]),
        ]
        client = _make_client(medium_items=artists)
        result = await build_artist_network(client)

        # Cluster names should all be unique
        names = list(result["cluster_names"].values())
        assert len(names) == len(set(names)), (
            f"Duplicate cluster names found: {names}"
        )


class TestDedupClusterNamesUnit:
    """Unit tests for _dedup_cluster_names — deterministic, no Louvain involved."""

    @staticmethod
    def _build_nodes(artists_by_cluster):
        """Helper: {cid: [(id, name, genres, pop), ...]} -> (nodes, louvain_labels)."""
        nodes = {}
        labels = {}
        for cid, artists in artists_by_cluster.items():
            for aid, name, genres, pop in artists:
                nodes[aid] = {
                    "id": aid,
                    "name": name,
                    "genres": genres,
                    "popularity": pop,
                }
                labels[aid] = cid
        return nodes, labels

    def test_no_duplicates_unchanged(self):
        """Names that are already unique stay unchanged."""
        nodes, labels = self._build_nodes({
            0: [("a1", "A1", ["rock"], 50)],
            1: [("a2", "A2", ["pop"], 50)],
        })
        names = {0: "Rock", 1: "Pop"}
        result = _dedup_cluster_names(names, labels, nodes)
        assert result == {0: "Rock", 1: "Pop"}

    def test_secondary_genre_differentiates(self):
        """Pass 1: secondary genre suffix resolves collision."""
        nodes, labels = self._build_nodes({
            0: [("a1", "A1", ["hip-hop", "trap"], 50),
                ("a2", "A2", ["hip-hop", "trap"], 40)],
            1: [("a3", "A3", ["hip-hop", "r&b"], 60),
                ("a4", "A4", ["hip-hop", "r&b"], 30)],
        })
        names = {0: "Hip Hop", 1: "Hip Hop"}
        result = _dedup_cluster_names(names, labels, nodes)
        values = list(result.values())
        assert len(values) == len(set(values)), f"Duplicate names: {values}"
        # Both should have "/" separator from genre suffix
        assert all("/" in v for v in values)

    def test_tertiary_genre_when_secondary_collides(self):
        """Pass 2: tertiary genre resolves when secondary is the same."""
        nodes, labels = self._build_nodes({
            0: [("a1", "A1", ["hip-hop", "trap", "drill"], 50),
                ("a2", "A2", ["hip-hop", "trap", "drill"], 40)],
            1: [("a3", "A3", ["hip-hop", "trap", "grime"], 60),
                ("a4", "A4", ["hip-hop", "trap", "grime"], 30)],
        })
        names = {0: "Hip Hop", 1: "Hip Hop"}
        result = _dedup_cluster_names(names, labels, nodes)
        values = list(result.values())
        assert len(values) == len(set(values)), f"Duplicate names: {values}"

    def test_artist_name_fallback_when_genres_identical(self):
        """Pass 3: top artist name resolves when all genres are identical."""
        nodes, labels = self._build_nodes({
            0: [("a1", "Sfera Ebbasta", ["hip-hop", "trap"], 80),
                ("a2", "A2", ["hip-hop", "trap"], 40)],
            1: [("a3", "Travis Scott", ["hip-hop", "trap"], 90),
                ("a4", "A4", ["hip-hop", "trap"], 30)],
        })
        names = {0: "Hip Hop", 1: "Hip Hop"}
        result = _dedup_cluster_names(names, labels, nodes)
        values = list(result.values())
        assert len(values) == len(set(values)), f"Duplicate names: {values}"
        # Should contain "(Artist)" pattern
        assert any("(Sfera)" in v for v in values)
        assert any("(Travis)" in v for v in values)

    def test_roman_numeral_safety_net(self):
        """Pass 4: roman numerals as last resort when even artist names collide."""
        # Same genres, same top artist name (unlikely but must be handled)
        nodes, labels = self._build_nodes({
            0: [("a1", "Same Name", ["hip-hop", "trap"], 80)],
            1: [("a2", "Same Name", ["hip-hop", "trap"], 80)],
        })
        names = {0: "Hip Hop", 1: "Hip Hop"}
        result = _dedup_cluster_names(names, labels, nodes)
        values = list(result.values())
        assert len(values) == len(set(values)), f"Duplicate names: {values}"

    def test_three_way_collision(self):
        """Three clusters with the same name all get unique names."""
        nodes, labels = self._build_nodes({
            0: [("a1", "A1", ["hip-hop", "trap"], 50),
                ("a2", "A2", ["hip-hop", "trap"], 40)],
            1: [("a3", "A3", ["hip-hop", "r&b"], 60),
                ("a4", "A4", ["hip-hop", "r&b"], 30)],
            2: [("a5", "A5", ["hip-hop", "soul"], 70),
                ("a6", "A6", ["hip-hop", "soul"], 20)],
        })
        names = {0: "Hip Hop", 1: "Hip Hop", 2: "Hip Hop"}
        result = _dedup_cluster_names(names, labels, nodes)
        values = list(result.values())
        assert len(values) == len(set(values)), f"Duplicate names: {values}"

    def test_single_cluster_unchanged(self):
        """Single cluster returns immediately, no processing."""
        nodes, labels = self._build_nodes({
            0: [("a1", "A1", ["rock"], 50)],
        })
        names = {0: "Rock"}
        result = _dedup_cluster_names(names, labels, nodes)
        assert result == {0: "Rock"}

    def test_empty_input(self):
        """Empty dict returns empty dict."""
        result = _dedup_cluster_names({}, {}, {})
        assert result == {}

    def test_mixed_collisions(self):
        """Some names collide, others don't — only colliding ones change."""
        nodes, labels = self._build_nodes({
            0: [("a1", "A1", ["rock", "indie"], 50)],
            1: [("a2", "A2", ["rock", "metal"], 50)],
            2: [("a3", "A3", ["jazz"], 50)],
        })
        names = {0: "Rock", 1: "Rock", 2: "Jazz"}
        result = _dedup_cluster_names(names, labels, nodes)
        values = list(result.values())
        assert len(values) == len(set(values)), f"Duplicate names: {values}"
        # Jazz should remain unchanged
        assert result[2] == "Jazz"

    def test_no_genres_uses_artist_name(self):
        """Clusters with no genres at all fall through to artist name."""
        nodes, labels = self._build_nodes({
            0: [("a1", "Sfera Ebbasta", [], 80)],
            1: [("a2", "Travis Scott", [], 90)],
        })
        names = {0: "Cerchia 1", 1: "Cerchia 1"}
        result = _dedup_cluster_names(names, labels, nodes)
        values = list(result.values())
        assert len(values) == len(set(values)), f"Duplicate names: {values}"


class TestGenreEnrichment:
    @pytest.mark.asyncio
    @patch("app.services.artist_network.get_artist_genres_cached")
    async def test_enriches_empty_genres_via_cache(self, mock_cache):
        """When db is provided, artists with empty genres get enriched from cache."""
        mock_cache.return_value = {
            "a1": ["rock", "indie rock"],
            "a2": ["jazz", "smooth jazz"],
        }
        artists = [
            _make_artist("a1", "Artist 1", []),
            _make_artist("a2", "Artist 2", []),
            _make_artist("a3", "Artist 3", ["pop", "dance"]),
        ]
        client = _make_client(medium_items=artists)
        db = MagicMock()  # mock db session

        result = await build_artist_network(client, db=db)

        # Cache should have been called with the two empty-genre artist IDs
        mock_cache.assert_called_once()
        call_args = mock_cache.call_args
        called_ids = call_args[0][2]  # third positional arg = artist_ids
        assert set(called_ids) == {"a1", "a2"}

        # Nodes should now have genres from cache
        nodes_by_id = {n["id"]: n for n in result["nodes"]}
        assert nodes_by_id["a1"]["genres"] == ["rock", "indie rock"]
        assert nodes_by_id["a2"]["genres"] == ["jazz", "smooth jazz"]
        assert nodes_by_id["a3"]["genres"] == ["pop", "dance"]  # unchanged

    @pytest.mark.asyncio
    @patch("app.services.artist_network.get_artist_genres_cached")
    async def test_no_enrichment_without_db(self, mock_cache):
        """When db is None, genre cache is not called."""
        artists = [
            _make_artist("a1", "Artist 1", []),
        ]
        client = _make_client(medium_items=artists)

        result = await build_artist_network(client, db=None)

        mock_cache.assert_not_called()
        nodes_by_id = {n["id"]: n for n in result["nodes"]}
        assert nodes_by_id["a1"]["genres"] == []

    @pytest.mark.asyncio
    @patch("app.services.artist_network.get_artist_genres_cached")
    async def test_enrichment_creates_genre_edges(self, mock_cache):
        """Enriched genres should produce edges between previously disconnected artists."""
        mock_cache.return_value = {
            "a1": ["rock", "indie"],
            "a2": ["rock", "pop"],
        }
        artists = [
            _make_artist("a1", "Artist 1", []),
            _make_artist("a2", "Artist 2", []),
        ]
        client = _make_client(medium_items=artists)
        db = MagicMock()

        result = await build_artist_network(client, db=db)

        # After enrichment, both share "rock" -> should have at least 1 edge
        assert result["metrics"]["total_edges"] >= 1

    @pytest.mark.asyncio
    @patch("app.services.artist_network.get_artist_genres_cached")
    async def test_enrichment_failure_does_not_crash(self, mock_cache):
        """Genre cache failure should be logged but not crash the endpoint."""
        mock_cache.side_effect = RuntimeError("DB connection lost")
        artists = [
            _make_artist("a1", "Artist 1", []),
            _make_artist("a2", "Artist 2", ["rock"]),
        ]
        client = _make_client(medium_items=artists)
        db = MagicMock()

        # Should not raise
        result = await build_artist_network(client, db=db)
        assert result["metrics"]["total_nodes"] == 2


# ---------------------------------------------------------------------------
# Bundle integration
# ---------------------------------------------------------------------------


def _make_bundle(short_items=None, medium_items=None, long_items=None):
    """Crea un mock RequestDataBundle con risposte configurabili."""
    bundle = MagicMock(spec=RequestDataBundle)
    bundle.get_top_artists = AsyncMock(
        side_effect=lambda time_range="medium_term", limit=50: {
            "items": {
                "short_term": short_items or [],
                "medium_term": medium_items or [],
                "long_term": long_items or [],
            }.get(time_range, [])
        }
    )
    return bundle


class TestBundleIntegration:
    @pytest.mark.asyncio
    async def test_bundle_path_constructs_graph(self):
        """Using bundle produces a valid artist network."""
        artists = [
            _make_artist("a1", "Artist 1", ["rock", "indie rock"]),
            _make_artist("a2", "Artist 2", ["rock", "pop"]),
        ]
        bundle = _make_bundle(medium_items=artists)
        client = MagicMock()
        client.get_top_artists = AsyncMock()

        result = await build_artist_network(client, bundle=bundle)

        assert result["metrics"]["total_nodes"] == 2
        assert result["metrics"]["total_edges"] >= 1

    @pytest.mark.asyncio
    async def test_bundle_uses_bundle_not_client(self):
        """When bundle is provided, client.get_top_artists should NOT be called."""
        bundle = _make_bundle()
        client = MagicMock()
        client.get_top_artists = AsyncMock()

        await build_artist_network(client, bundle=bundle)

        client.get_top_artists.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_bundle_dedup_across_ranges(self):
        """Bundle path deduplicates artists across time ranges."""
        artist = _make_artist("a1", "Artist 1", ["rock"])
        bundle = _make_bundle(
            short_items=[artist],
            medium_items=[artist],
            long_items=[artist],
        )
        client = MagicMock()

        result = await build_artist_network(client, bundle=bundle)
        assert result["metrics"]["total_nodes"] == 1

    @pytest.mark.asyncio
    async def test_bundle_none_falls_back_to_client(self):
        """When bundle=None, uses client (backward compat)."""
        client = _make_client(
            medium_items=[_make_artist("a1", "A1", ["rock"])],
        )

        result = await build_artist_network(client, bundle=None)
        assert result["metrics"]["total_nodes"] == 1
