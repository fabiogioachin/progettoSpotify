"""Costruzione del grafo di artisti basato su generi condivisi e rilevamento cluster.

Non usa l'endpoint /related-artists (rimosso in dev mode Feb 2026).
Costruisce edges tra artisti con similarita' di genere (fuzzy matching).
Usa NetworkX per Louvain communities, PageRank e betweenness centrality.
"""

import asyncio
import logging
from collections import defaultdict

import networkx as nx
from networkx.algorithms.community import louvain_communities

from app.services.genre_utils import compute_genre_similarity, normalize_genre
from app.services.spotify_client import SpotifyClient
from app.services.taste_clustering import (
    build_feature_matrix,
    name_clusters,
    rank_within_cluster,
)
from app.utils.rate_limiter import SpotifyAuthError, retry_with_backoff

logger = logging.getLogger(__name__)


async def _safe_fetch(coro):
    """Una chiamata fallita non deve crashare l'intera pagina."""
    try:
        return await coro
    except SpotifyAuthError:
        raise  # DEVE ri-lanciare
    except Exception as exc:
        logger.warning("Chiamata API fallita: %s", exc)
        return {"items": []}


async def build_artist_network(
    client: SpotifyClient, max_seed_artists: int = 15
) -> dict:
    """Costruisce il grafo di artisti basato su generi condivisi."""

    # Fetch top artists from 3 time ranges for richer data (~45 unique artists)
    # Always use default limit=50 to maximise cache hits with other endpoints
    short_task = _safe_fetch(
        retry_with_backoff(client.get_top_artists, time_range="short_term")
    )
    medium_task = _safe_fetch(
        retry_with_backoff(client.get_top_artists, time_range="medium_term")
    )
    long_task = _safe_fetch(
        retry_with_backoff(client.get_top_artists, time_range="long_term")
    )

    short_data, medium_data, long_data = await asyncio.gather(
        short_task, medium_task, long_task, return_exceptions=True
    )

    # Re-raise SpotifyAuthError before handling generic exceptions
    for result in (short_data, medium_data, long_data):
        if isinstance(result, SpotifyAuthError):
            raise result

    if isinstance(short_data, BaseException):
        short_data = {"items": []}
    if isinstance(medium_data, BaseException):
        medium_data = {"items": []}
    if isinstance(long_data, BaseException):
        long_data = {"items": []}

    # Merge artists from all ranges, dedup by ID
    seen_ids = set()
    all_artists = []
    all_items = (
        short_data.get("items", [])
        + medium_data.get("items", [])
        + long_data.get("items", [])
    )
    for artist in all_items:
        if artist["id"] not in seen_ids:
            seen_ids.add(artist["id"])
            all_artists.append(artist)

    if not all_artists:
        return _empty_result()

    # Build nodes
    nodes = {}
    for artist in all_artists:
        images = artist.get("images", [])
        nodes[artist["id"]] = {
            "id": artist["id"],
            "name": artist.get("name", ""),
            "image": images[0]["url"] if images else None,
            "is_top": True,
            "genres": artist.get("genres", [])[:5],
            "popularity": artist.get("popularity", 0),
            "followers": artist.get("followers", {}).get("total", 0),
        }

    # Build genre-based edges with fuzzy matching
    edges = []
    seen_edges = set()
    artist_ids = list(nodes.keys())

    for i, aid_a in enumerate(artist_ids):
        genres_a = nodes[aid_a]["genres"]
        if not genres_a:
            continue
        for aid_b in artist_ids[i + 1 :]:
            genres_b = nodes[aid_b]["genres"]
            if not genres_b:
                continue
            similarity = compute_genre_similarity(genres_a, genres_b)
            if similarity > 0.15:  # threshold for edge creation
                edge_key = tuple(sorted([aid_a, aid_b]))
                if edge_key not in seen_edges:
                    seen_edges.add(edge_key)
                    # Compute shared genres for tooltip display
                    shared_genres = []
                    for ga in genres_a:
                        norm_a = normalize_genre(ga)
                        for gb in genres_b:
                            norm_b = normalize_genre(gb)
                            if norm_a == norm_b:
                                shared_genres.append(ga)
                                break
                    edges.append(
                        {
                            "source": aid_a,
                            "target": aid_b,
                            "weight": round(similarity, 3),
                            "shared_genres": shared_genres[:3],
                        }
                    )

    # Build NetworkX graph
    G = nx.Graph()
    for nid in nodes:
        G.add_node(nid)
    for edge in edges:
        G.add_edge(edge["source"], edge["target"], weight=edge["weight"])

    # Connection count per node
    conn_count = defaultdict(int)
    for edge in edges:
        conn_count[edge["source"]] += 1
        conn_count[edge["target"]] += 1
    for nid in nodes:
        nodes[nid]["connections"] = conn_count.get(nid, 0)

    # Louvain communities replacing BFS
    if G.number_of_nodes() > 0 and G.number_of_edges() > 0:
        try:
            communities = louvain_communities(
                G, weight="weight", resolution=1.0, seed=42
            )
            # If too few clusters for a decent-sized graph, increase resolution
            if len(communities) < 3 and G.number_of_nodes() > 15:
                communities = louvain_communities(
                    G, weight="weight", resolution=1.5, seed=42
                )
        except Exception as exc:
            logger.warning("Louvain fallito, fallback a componenti connesse: %s", exc)
            communities = [set(c) for c in nx.connected_components(G)]
    else:
        communities = [{nid} for nid in nodes]  # each node is its own cluster

    # Convert communities to cluster assignments
    louvain_labels = {}
    for idx, community in enumerate(communities):
        for nid in community:
            louvain_labels[nid] = idx

    # PageRank + Betweenness centrality
    if G.number_of_edges() > 0:
        pagerank = nx.pagerank(G, weight="weight")
        betweenness = nx.betweenness_centrality(G, weight="weight")
    else:
        pagerank = {nid: 1.0 / len(nodes) for nid in nodes}
        betweenness = {nid: 0.0 for nid in nodes}

    # Add metrics to nodes
    for nid in nodes:
        nodes[nid]["pagerank"] = round(pagerank.get(nid, 0), 4)
        nodes[nid]["betweenness"] = round(betweenness.get(nid, 0), 4)
        nodes[nid]["cluster"] = louvain_labels.get(nid, 0)

    # Clusters list
    clusters = [
        {"id": nid, "name": nodes[nid]["name"], "cluster": louvain_labels.get(nid, 0)}
        for nid in nodes
    ]

    # Bridge artists from betweenness centrality
    bridges = sorted(
        [
            {
                "id": nid,
                "name": nodes[nid]["name"],
                "bridge_score": round(betweenness.get(nid, 0), 3),
                "image": nodes[nid].get("image"),
                "genres": nodes[nid].get("genres", []),
                "popularity": nodes[nid].get("popularity", 0),
            }
            for nid in nodes
            if betweenness.get(nid, 0) > 0
        ],
        key=lambda x: x["bridge_score"],
        reverse=True,
    )[:5]

    # Cluster names + rankings via sklearn (TF-IDF naming, composite ranking)
    cluster_ids = set(louvain_labels.values())
    try:
        matrix, artist_ids_matrix, _ = build_feature_matrix(list(nodes.values()))
        # Replace simple genre-counting cluster naming with TF-IDF-like naming
        sklearn_names = name_clusters(louvain_labels, list(nodes.values()))
        if sklearn_names:
            cluster_names = sklearn_names
        else:
            raise ValueError("sklearn name_clusters returned empty")
        # Rank artists within each cluster
        cluster_rankings = rank_within_cluster(
            louvain_labels, list(nodes.values()), pagerank
        )
    except Exception as exc:
        logger.warning(
            "Sklearn naming/ranking fallito, fallback a conteggio generi: %s", exc
        )
        cluster_rankings = {}
        # Fallback: genre-counting cluster naming
        cluster_genres = defaultdict(lambda: defaultdict(int))
        for nid, node in nodes.items():
            cid = louvain_labels.get(nid)
            if cid is not None:
                for g in node.get("genres", []):
                    cluster_genres[cid][g] += 1
        cluster_names = {}
        for cid in sorted(cluster_ids):
            genres = cluster_genres.get(cid, {})
            if genres:
                top_genre = max(genres, key=genres.get)
                cluster_names[cid] = top_genre.replace("-", " ").title()
            else:
                cluster_names[cid] = f"Cerchia {cid + 1}"

    # Genre summary
    genre_counter = defaultdict(int)
    for n in nodes.values():
        for g in n.get("genres", []):
            genre_counter[g] += 1
    top_genres = sorted(genre_counter.items(), key=lambda x: x[1], reverse=True)[:10]

    # Data quality
    artists_without_genres = sum(1 for n in nodes.values() if not n.get("genres"))
    data_quality = {
        "artists_without_genres": artists_without_genres,
        "warning": (
            f"{artists_without_genres} artisti senza generi"
            if artists_without_genres > 3
            else None
        ),
    }

    # Density
    density = nx.density(G) if G.number_of_nodes() > 1 else 0

    return {
        "nodes": list(nodes.values()),
        "edges": edges,
        "clusters": clusters,
        "cluster_names": cluster_names,
        "cluster_rankings": {str(k): v for k, v in cluster_rankings.items()},
        "bridges": bridges,
        "top_genres": [{"genre": g, "count": c} for g, c in top_genres],
        "data_quality": data_quality,
        "metrics": {
            "total_nodes": len(nodes),
            "total_edges": len(edges),
            "cluster_count": len(cluster_ids),
            "density": round(density, 3),
        },
    }


def _empty_result():
    return {
        "nodes": [],
        "edges": [],
        "clusters": [],
        "cluster_names": {},
        "cluster_rankings": {},
        "bridges": [],
        "top_genres": [],
        "data_quality": {"artists_without_genres": 0, "warning": None},
        "metrics": {
            "total_nodes": 0,
            "total_edges": 0,
            "cluster_count": 0,
            "density": 0,
        },
    }
