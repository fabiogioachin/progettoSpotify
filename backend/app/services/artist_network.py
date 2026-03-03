"""Costruzione del grafo di artisti correlati e rilevamento cluster."""

import asyncio
from collections import defaultdict

from app.services.spotify_client import SpotifyClient
from app.utils.rate_limiter import retry_with_backoff


async def build_artist_network(client: SpotifyClient, max_seed_artists: int = 15) -> dict:
    """Costruisce il grafo di artisti correlati partendo dai top artists."""

    top_data = await retry_with_backoff(
        client.get_top_artists, time_range="medium_term", limit=max_seed_artists
    )
    top_items = top_data.get("items", [])

    if not top_items:
        return _empty_result()

    # Build nodes dict from top artists
    nodes = {}
    for artist in top_items:
        images = artist.get("images", [])
        nodes[artist["id"]] = {
            "id": artist["id"],
            "name": artist.get("name", ""),
            "image": images[0]["url"] if images else None,
            "is_top": True,
        }

    # Fetch related artists with concurrency control
    edges = []
    seen_edges = set()

    sem = asyncio.Semaphore(5)

    async def fetch_related(artist_id):
        async with sem:
            try:
                data = await retry_with_backoff(client.get_related_artists, artist_id)
                return artist_id, data.get("artists", [])
            except Exception:
                return artist_id, []

    tasks = [fetch_related(a["id"]) for a in top_items]
    results = await asyncio.gather(*tasks)

    for source_id, related_artists in results:
        for rel in related_artists[:10]:  # Limit to 10 related per artist
            rel_id = rel["id"]

            # Add node if new
            if rel_id not in nodes:
                images = rel.get("images", [])
                nodes[rel_id] = {
                    "id": rel_id,
                    "name": rel.get("name", ""),
                    "image": images[0]["url"] if images else None,
                    "is_top": False,
                }

            # Add edge (deduplicated)
            edge_key = tuple(sorted([source_id, rel_id]))
            if edge_key not in seen_edges:
                seen_edges.add(edge_key)
                edges.append({"source": source_id, "target": rel_id})

    # Cluster detection (BFS connected components)
    clusters = _detect_clusters(nodes, edges)

    # Bridge artists: nodes connecting different clusters
    bridges = _find_bridges(nodes, edges, clusters)

    # Count clusters
    cluster_ids = set(c["cluster"] for c in clusters)

    return {
        "nodes": list(nodes.values()),
        "edges": edges,
        "clusters": clusters,
        "bridges": bridges[:5],
        "metrics": {
            "total_nodes": len(nodes),
            "total_edges": len(edges),
            "cluster_count": len(cluster_ids),
            "top_artists_count": sum(1 for n in nodes.values() if n["is_top"]),
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
