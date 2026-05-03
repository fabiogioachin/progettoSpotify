"""Costruzione del grafo di artisti basato su generi condivisi e rilevamento cluster.

Non usa l'endpoint /related-artists (rimosso in dev mode Feb 2026).
Costruisce edges tra artisti con similarita' di genere (fuzzy matching).
Usa NetworkX per Louvain communities, PageRank e betweenness centrality.
"""

from __future__ import annotations

import asyncio
import logging
from collections import defaultdict
from typing import TYPE_CHECKING

import networkx as nx
from networkx.algorithms.community import louvain_communities

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.listening_history import RecentPlay

from app.services.genre_cache import get_artist_genres_cached
from app.services.genre_utils import compute_genre_similarity, normalize_genre
from app.services.spotify_client import SpotifyClient
from app.services.taste_clustering import (
    build_feature_matrix,
    name_clusters,
    rank_within_cluster,
)
from app.utils.rate_limiter import RateLimitError, SpotifyAuthError, retry_with_backoff

if TYPE_CHECKING:
    from app.services.data_bundle import RequestDataBundle

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
    client: SpotifyClient,
    db: AsyncSession | None = None,
    max_seed_artists: int = 15,
    bundle: RequestDataBundle | None = None,
) -> dict:
    """Costruisce il grafo di artisti basato su generi condivisi."""

    # Fetch top artists from 3 time ranges for richer data (~45 unique artists)
    # Always use default limit=50 to maximise cache hits with other endpoints
    if bundle:
        # Bundle already has data prefetched — just retrieve it
        short_task = _safe_fetch(bundle.get_top_artists(time_range="short_term"))
        medium_task = _safe_fetch(bundle.get_top_artists(time_range="medium_term"))
        long_task = _safe_fetch(bundle.get_top_artists(time_range="long_term"))
    else:
        # Original path — direct client calls
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

    # Enrich empty genres via genre cache (invariant #7)
    if db:
        empty_genre_ids = [aid for aid, node in nodes.items() if not node.get("genres")]
        if empty_genre_ids:
            try:
                cached_genres = await get_artist_genres_cached(
                    db, client, empty_genre_ids
                )
                enriched = 0
                for aid, genres in cached_genres.items():
                    if genres and aid in nodes:
                        nodes[aid]["genres"] = genres[:5]
                        enriched += 1
                if enriched:
                    logger.info(
                        "Arricchiti generi per %d/%d artisti via genre cache",
                        enriched,
                        len(empty_genre_ids),
                    )
            except (SpotifyAuthError, RateLimitError):
                raise
            except Exception as exc:
                logger.warning("Genre cache enrichment fallito: %s", exc)

    # Per-artist play count from recent_plays
    if db:
        try:
            artist_ids_list = list(nodes.keys())
            stmt = (
                select(
                    RecentPlay.artist_spotify_id,
                    func.count().label("play_count"),
                )
                .where(
                    RecentPlay.user_id == client.user_id,
                    RecentPlay.artist_spotify_id.in_(artist_ids_list),
                )
                .group_by(RecentPlay.artist_spotify_id)
            )
            result = await db.execute(stmt)
            play_counts = {row.artist_spotify_id: row.play_count for row in result}
            for nid in nodes:
                nodes[nid]["play_count"] = play_counts.get(nid, 0)
            logger.debug(
                "Play count caricati per %d/%d artisti",
                len(play_counts),
                len(nodes),
            )
        except Exception as exc:
            logger.warning("Query play count fallita: %s", exc)
            for nid in nodes:
                nodes[nid]["play_count"] = 0
    else:
        for nid in nodes:
            nodes[nid]["play_count"] = 0

    # Build genre-based edges with fuzzy matching
    edges = []
    seen_edges = set()
    artist_ids = list(nodes.keys())

    for i, aid_a in enumerate(artist_ids):
        genres_a = nodes[aid_a]["genres"]
        for aid_b in artist_ids[i + 1 :]:
            genres_b = nodes[aid_b]["genres"]

            # Genre-based similarity (primary)
            if genres_a and genres_b:
                similarity = compute_genre_similarity(genres_a, genres_b)
                if similarity > 0.15:
                    edge_key = tuple(sorted([aid_a, aid_b]))
                    if edge_key not in seen_edges:
                        seen_edges.add(edge_key)
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
            # Artists without genres remain unconnected (isolated nodes).
            # Popularity-based fallback removed: Spotify dev mode returns
            # popularity=0 for all artists, making it useless for edges.

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
                # Fallback: use most popular artist name in cluster
                cluster_aids = [aid for aid, c in louvain_labels.items() if c == cid]
                cluster_nodes = [nodes[aid] for aid in cluster_aids if aid in nodes]
                if cluster_nodes:
                    best = max(cluster_nodes, key=lambda n: n.get("popularity", 0))
                    cluster_names[cid] = (
                        f"Cerchia di {best.get('name', f'Cerchia {cid + 1}')}"
                    )
                else:
                    cluster_names[cid] = f"Cerchia {cid + 1}"

    # --- Filter singleton clusters from display dicts (Problem 2) ---
    # Nodes keep their cluster field for SVG coloring, but cluster_names
    # and cluster_rankings shown to the user exclude singletons.
    multi_artist_clusters = {
        cid
        for cid in cluster_ids
        if sum(1 for c in louvain_labels.values() if c == cid) > 1
    }

    filtered_names = {
        cid: name for cid, name in cluster_names.items() if cid in multi_artist_clusters
    }
    filtered_rankings = {
        str(k): v
        for k, v in cluster_rankings.items()
        if (k if isinstance(k, int) else int(k)) in multi_artist_clusters
    }

    # --- Deduplicate cluster names (Problem 3) ---
    # Post-processing pass: guarantee unique names regardless of naming source
    # (TF-IDF from taste_clustering or fallback genre-counting).
    filtered_names = _dedup_cluster_names(filtered_names, louvain_labels, nodes)

    # --- Genre nodes and edges for KG visualization ---
    genre_nodes_list = []
    genre_edges_list = []

    for cid in sorted(cluster_ids):
        cluster_aids = [aid for aid, c in louvain_labels.items() if c == cid]
        cluster_genre_freq = defaultdict(int)
        for aid in cluster_aids:
            for g in nodes[aid].get("genres", []):
                cluster_genre_freq[g] += 1

        # Top 3 genres for this cluster
        top_cluster_genres = sorted(
            cluster_genre_freq.items(), key=lambda x: x[1], reverse=True
        )[:3]

        for genre_name, count in top_cluster_genres:
            normalized = genre_name.lower().replace(" ", "_").replace("-", "_")
            genre_id = f"genre_{normalized}"

            existing = next(
                (gn for gn in genre_nodes_list if gn["id"] == genre_id), None
            )
            if existing:
                # Keep in cluster where it's most frequent
                if count > existing["artist_count"]:
                    existing["cluster"] = cid
                    existing["artist_count"] = count
            else:
                genre_nodes_list.append(
                    {
                        "id": genre_id,
                        "name": genre_name.replace("-", " ").title(),
                        "type": "genre",
                        "cluster": cid,
                        "artist_count": count,
                    }
                )

    # Genre IDs set for O(1) lookup
    genre_ids_set = {gn["id"] for gn in genre_nodes_list}
    seen_genre_edges = set()

    for cid in sorted(cluster_ids):
        cluster_aids = [aid for aid, c in louvain_labels.items() if c == cid]
        for aid in cluster_aids:
            for g in nodes[aid].get("genres", []):
                normalized = g.lower().replace(" ", "_").replace("-", "_")
                genre_id = f"genre_{normalized}"
                if genre_id in genre_ids_set:
                    edge_key = (aid, genre_id)
                    if edge_key not in seen_genre_edges:
                        seen_genre_edges.add(edge_key)
                        genre_edges_list.append(
                            {
                                "source": aid,
                                "target": genre_id,
                                "type": "genre_link",
                            }
                        )

    # --- Genre rankings: artists grouped by genre node, sorted by connections ---
    genre_artists: dict[str, list[str]] = defaultdict(list)
    for ge in genre_edges_list:
        source, target = ge["source"], ge["target"]
        # One end is the genre node (id starts with "genre_"), the other is the artist
        if target.startswith("genre_"):
            genre_artists[target].append(source)
        elif source.startswith("genre_"):
            genre_artists[source].append(target)

    genre_rankings: dict[str, list[dict]] = {}
    for genre_id, artist_ids_in_genre in genre_artists.items():
        # Deduplicate (should already be unique via seen_genre_edges, but be safe)
        unique_aids = list(dict.fromkeys(artist_ids_in_genre))
        artist_entries = []
        for aid in unique_aids:
            node = nodes.get(aid)
            if node:
                artist_entries.append(
                    {
                        "name": node["name"],
                        "image": node.get("image"),
                        "genres": node.get("genres", []),
                        "popularity": node.get("popularity", 0),
                        "connections": node.get("connections", 0),
                    }
                )
        # Sort by connections descending
        artist_entries.sort(key=lambda a: a["connections"], reverse=True)
        # Normalize score 0-1 within the group
        max_conn = artist_entries[0]["connections"] if artist_entries else 1
        if max_conn == 0:
            max_conn = 1  # avoid division by zero
        for entry in artist_entries:
            entry["score"] = round(entry["connections"] / max_conn, 3)
        genre_rankings[genre_id] = artist_entries

    # Genre names: genre node id -> display name
    genre_names: dict[str, str] = {gn["id"]: gn["name"] for gn in genre_nodes_list}

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
        "cluster_names": filtered_names,
        "cluster_rankings": filtered_rankings,
        "bridges": bridges,
        "top_genres": [{"genre": g, "count": c} for g, c in top_genres],
        "genre_nodes": genre_nodes_list,
        "genre_edges": genre_edges_list,
        "genre_rankings": genre_rankings,
        "genre_names": genre_names,
        "data_quality": data_quality,
        "metrics": {
            "total_nodes": len(nodes),
            "total_edges": len(edges),
            "cluster_count": len(multi_artist_clusters),
            "density": round(density, 3),
        },
    }


def _dedup_cluster_names(
    names: dict[int, str],
    louvain_labels: dict[str, int],
    nodes: dict[str, dict],
) -> dict[int, str]:
    """Guarantee unique cluster names via cascading differentiation.

    Cascade order for duplicates sharing the same base name:
    1. Secondary genre suffix (e.g. "Hip Hop / Trap" vs "Hip Hop / R&B")
    2. Tertiary genre suffix (if secondary also collides)
    3. Top artist name in parentheses (e.g. "Hip Hop (Sfera)" vs "Hip Hop (Travis)")
    4. Roman numeral safety net (I, II, III, ...)

    Works as a post-processing pass on already-computed names.
    """
    result = dict(names)
    if len(result) <= 1:
        return result

    # Pre-compute per-cluster data: sorted genre list (excl. primary) + top artist
    _cluster_info: dict[int, dict] = {}
    for cid in result:
        cluster_aids = [aid for aid, c in louvain_labels.items() if c == cid]
        # Genre frequency within this cluster
        genre_freq: dict[str, int] = defaultdict(int)
        for aid in cluster_aids:
            for g in nodes.get(aid, {}).get("genres", []):
                genre_freq[g] += 1
        sorted_genres = [g for g, _ in sorted(genre_freq.items(), key=lambda x: -x[1])]
        # Top artist by popularity within this cluster
        cluster_nodes = [nodes[aid] for aid in cluster_aids if aid in nodes]
        top_artist = ""
        if cluster_nodes:
            best = max(cluster_nodes, key=lambda n: n.get("popularity", 0))
            top_artist = best.get("name", "")
            # Use first name/word only for brevity
            top_artist = top_artist.split()[0] if top_artist else ""
        _cluster_info[cid] = {
            "sorted_genres": sorted_genres,
            "top_artist": top_artist,
        }

    def _find_duplicates(d: dict[int, str]) -> dict[str, list[int]]:
        """Return {name: [cid, ...]} for names appearing more than once."""
        from collections import Counter

        counts = Counter(d.values())
        dups: dict[str, list[int]] = {}
        for name, cnt in counts.items():
            if cnt > 1:
                dups[name] = sorted(cid for cid, n in d.items() if n == name)
        return dups

    def _non_primary_genres(cid: int, base_name: str) -> list[str]:
        """Return genres for cid excluding those matching base_name."""
        primary_norm = base_name.lower().replace(" ", "-")
        return [
            g
            for g in _cluster_info.get(cid, {}).get("sorted_genres", [])
            if g.lower().replace(" ", "-") != primary_norm
        ]

    # --- Pass 1: secondary genre suffix ---
    dups = _find_duplicates(result)
    for base_name, cids in dups.items():
        for cid in cids:
            secondary = _non_primary_genres(cid, base_name)
            if secondary:
                suffix = secondary[0].replace("-", " ").title()
                result[cid] = f"{base_name} / {suffix}"
            # If no secondary genre available, leave name unchanged for now

    # --- Pass 2: tertiary genre suffix (when secondary also collided) ---
    dups = _find_duplicates(result)
    for dup_name, cids in dups.items():
        # Extract the base name (before " / ") for genre exclusion
        base_name = dup_name.split(" / ")[0]
        for cid in cids:
            non_primary = _non_primary_genres(cid, base_name)
            # Skip the secondary (index 0) which already collided; try tertiary
            if len(non_primary) >= 2:
                tertiary_suffix = non_primary[1].replace("-", " ").title()
                result[cid] = f"{base_name} / {tertiary_suffix}"

    # --- Pass 3: top artist name fallback ---
    dups = _find_duplicates(result)
    for dup_name, cids in dups.items():
        for cid in cids:
            artist = _cluster_info.get(cid, {}).get("top_artist", "")
            if artist:
                result[cid] = f"{dup_name} ({artist})"

    # --- Pass 4: roman numeral safety net ---
    _roman = ["I", "II", "III", "IV", "V", "VI", "VII", "VIII", "IX", "X"]
    dups = _find_duplicates(result)
    for dup_name, cids in dups.items():
        for i, cid in enumerate(cids):
            numeral = _roman[i] if i < len(_roman) else str(i + 1)
            result[cid] = f"{dup_name} {numeral}"

    return result


def _empty_result():
    return {
        "nodes": [],
        "edges": [],
        "clusters": [],
        "cluster_names": {},
        "cluster_rankings": {},
        "bridges": [],
        "top_genres": [],
        "genre_nodes": [],
        "genre_edges": [],
        "genre_rankings": {},
        "genre_names": {},
        "data_quality": {"artists_without_genres": 0, "warning": None},
        "metrics": {
            "total_nodes": 0,
            "total_edges": 0,
            "cluster_count": 0,
            "density": 0,
        },
    }
