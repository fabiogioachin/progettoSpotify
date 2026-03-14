"""Costruzione del grafo di artisti basato su generi condivisi e rilevamento cluster.

Non usa l'endpoint /related-artists (rimosso in dev mode Feb 2026).
Costruisce edges tra artisti che condividono generi — piu' generi in comune,
connessione piu' forte.
"""

import asyncio
from collections import defaultdict

from app.services.spotify_client import SpotifyClient
from app.utils.rate_limiter import SpotifyAuthError, retry_with_backoff


async def build_artist_network(client: SpotifyClient, max_seed_artists: int = 15) -> dict:
    """Costruisce il grafo di artisti basato su generi condivisi."""

    # Fetch top artists from multiple time ranges for richer data
    medium_task = retry_with_backoff(
        client.get_top_artists, time_range="medium_term", limit=max_seed_artists
    )
    long_task = retry_with_backoff(
        client.get_top_artists, time_range="long_term", limit=max_seed_artists
    )

    medium_data, long_data = await asyncio.gather(
        medium_task, long_task, return_exceptions=True
    )

    for result in (medium_data, long_data):
        if isinstance(result, SpotifyAuthError):
            raise result

    if isinstance(medium_data, BaseException):
        medium_data = {"items": []}
    if isinstance(long_data, BaseException):
        long_data = {"items": []}

    # Merge artists from both ranges, dedup by ID
    seen_ids = set()
    all_artists = []
    for artist in medium_data.get("items", []) + long_data.get("items", []):
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

    # Build genre-based edges: connect artists sharing >= 1 genre
    edges = []
    seen_edges = set()
    artist_ids = list(nodes.keys())

    for i, aid_a in enumerate(artist_ids):
        genres_a = set(nodes[aid_a]["genres"])
        if not genres_a:
            continue
        for aid_b in artist_ids[i + 1:]:
            genres_b = set(nodes[aid_b]["genres"])
            shared = genres_a & genres_b
            if shared:
                edge_key = tuple(sorted([aid_a, aid_b]))
                if edge_key not in seen_edges:
                    seen_edges.add(edge_key)
                    edges.append({
                        "source": aid_a,
                        "target": aid_b,
                        "weight": len(shared),
                        "shared_genres": list(shared)[:3],
                    })

    # Connection count per node
    conn_count = defaultdict(int)
    for edge in edges:
        conn_count[edge["source"]] += 1
        conn_count[edge["target"]] += 1
    for nid in nodes:
        nodes[nid]["connections"] = conn_count.get(nid, 0)

    # Cluster detection (BFS connected components)
    clusters = _detect_clusters(nodes, edges)

    # Bridge artists: nodes connecting different clusters
    bridges = _find_bridges(nodes, edges, clusters)

    # Cluster names from dominant genres
    cluster_ids = set(c["cluster"] for c in clusters)
    cluster_genres = defaultdict(lambda: defaultdict(int))
    cluster_map = {c["id"]: c["cluster"] for c in clusters}
    for nid, node in nodes.items():
        cid = cluster_map.get(nid)
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

    return {
        "nodes": list(nodes.values()),
        "edges": edges,
        "clusters": clusters,
        "cluster_names": cluster_names,
        "bridges": bridges[:5],
        "top_genres": [{"genre": g, "count": c} for g, c in top_genres],
        "metrics": {
            "total_nodes": len(nodes),
            "total_edges": len(edges),
            "cluster_count": len(cluster_ids),
            "top_artists_count": len(nodes),
        },
    }


def _detect_clusters(nodes: dict, edges: list) -> list:
    """Rileva componenti connesse tramite BFS."""
    adj = defaultdict(set)
    for edge in edges:
        adj[edge["source"]].add(edge["target"])
        adj[edge["target"]].add(edge["source"])

    visited = set()
    cluster_id = 0
    node_clusters = {}

    for node_id in nodes:
        if node_id in visited:
            continue
        queue = [node_id]
        visited.add(node_id)
        while queue:
            current = queue.pop(0)
            node_clusters[current] = cluster_id
            for neighbor in adj.get(current, []):
                if neighbor not in visited and neighbor in nodes:
                    visited.add(neighbor)
                    queue.append(neighbor)
        cluster_id += 1

    return [
        {"id": nid, "name": nodes[nid]["name"], "cluster": cid}
        for nid, cid in node_clusters.items()
    ]


def _find_bridges(nodes: dict, edges: list, clusters: list) -> list:
    """Trova artisti che collegano cluster diversi."""
    cluster_map = {c["id"]: c["cluster"] for c in clusters}

    bridge_scores = defaultdict(int)
    for edge in edges:
        s_cluster = cluster_map.get(edge["source"])
        t_cluster = cluster_map.get(edge["target"])
        if s_cluster is not None and t_cluster is not None and s_cluster != t_cluster:
            bridge_scores[edge["source"]] += 1
            bridge_scores[edge["target"]] += 1

    bridges = sorted(bridge_scores.items(), key=lambda x: x[1], reverse=True)
    return [
        {
            "id": nid,
            "name": nodes[nid]["name"],
            "bridge_score": score,
            "image": nodes[nid].get("image"),
            "genres": nodes[nid].get("genres", []),
            "popularity": nodes[nid].get("popularity", 0),
        }
        for nid, score in bridges
        if nid in nodes
    ]


def _empty_result():
    return {
        "nodes": [],
        "edges": [],
        "clusters": [],
        "bridges": [],
        "metrics": {
            "total_nodes": 0,
            "total_edges": 0,
            "cluster_count": 0,
            "top_artists_count": 0,
        },
    }
