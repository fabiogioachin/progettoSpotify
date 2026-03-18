"""Servizio pure-compute per il layer social: compatibilità, leaderboard.

Modulo pure-compute: NON importa SpotifyClient, NON fa chiamate HTTP.
Lavora esclusivamente su dati locali passati come argomento.
"""

import math
from collections import Counter

from app.services.genre_utils import compute_genre_similarity, normalize_genre


def compute_compatibility(user_a_data: dict, user_b_data: dict) -> dict:
    """Calcola la compatibilità musicale tra due utenti.

    Args:
        user_a_data: dict con top_artists, top_genres, popularity_distribution
        user_b_data: dict con top_artists, top_genres, popularity_distribution

    Returns:
        dict con score (0-100), dettagli parziali, e liste unisce/distingue.
    """
    genres_a = user_a_data.get("top_genres", [])
    genres_b = user_b_data.get("top_genres", [])
    artists_a = user_a_data.get("top_artists", [])
    artists_b = user_b_data.get("top_artists", [])
    pops_a = user_a_data.get("popularity_distribution", [])
    pops_b = user_b_data.get("popularity_distribution", [])

    genre_sim = _jaccard_genres(genres_a, genres_b)
    artist_result = _artist_overlap(artists_a, artists_b)
    artist_overlap_ratio = artist_result["overlap_ratio"]
    pop_sim = _popularity_similarity(pops_a, pops_b)

    score = round(
        (0.4 * genre_sim + 0.35 * artist_overlap_ratio + 0.25 * pop_sim) * 100
    )

    unisce, distingue = _compute_unisce_distingue(
        genre_sim, artist_result, genres_a, genres_b
    )

    return {
        "score": score,
        "genre_score": round(genre_sim, 4),
        "artist_score": round(artist_overlap_ratio, 4),
        "popularity_score": round(pop_sim, 4),
        "shared_artists": artist_result["shared"],
        "unisce": unisce,
        "distingue": distingue,
    }


def _jaccard_genres(genres_a: list[str], genres_b: list[str]) -> float:
    """Similarità generi tramite fuzzy matching di genre_utils.

    Returns:
        float 0.0-1.0
    """
    return compute_genre_similarity(genres_a, genres_b)


def _artist_overlap(artists_a: list[dict], artists_b: list[dict]) -> dict:
    """Calcola overlap artisti tra due utenti.

    Match per spotify_id (campo 'id' nel dict artista).

    Returns:
        dict con shared, only_a, only_b, overlap_ratio.
    """
    ids_a = {a.get("id") for a in artists_a if a.get("id")}
    ids_b = {b.get("id") for b in artists_b if b.get("id")}

    shared_ids = ids_a & ids_b

    # Collect full artist dicts for shared artists
    name_by_id_a = {a["id"]: a for a in artists_a if a.get("id")}
    name_by_id_b = {b["id"]: b for b in artists_b if b.get("id")}

    shared = []
    for sid in shared_ids:
        artist = name_by_id_a.get(sid) or name_by_id_b.get(sid)
        if artist:
            shared.append(
                {
                    "id": sid,
                    "name": artist.get("name", ""),
                    "images": artist.get("images", []),
                }
            )

    only_a = [
        name_by_id_a[aid].get("name", "")
        for aid in (ids_a - ids_b)
        if aid in name_by_id_a
    ]
    only_b = [
        name_by_id_b[bid].get("name", "")
        for bid in (ids_b - ids_a)
        if bid in name_by_id_b
    ]

    union_size = len(ids_a | ids_b)
    overlap_ratio = len(shared_ids) / union_size if union_size > 0 else 0.0

    return {
        "shared": shared,
        "only_a": only_a,
        "only_b": only_b,
        "overlap_ratio": overlap_ratio,
    }


def _popularity_similarity(pops_a: list[int], pops_b: list[int]) -> float:
    """Cosine similarity tra le distribuzioni di popolarità.

    Returns:
        float 0.0-1.0
    """
    if not pops_a or not pops_b:
        return 0.0

    dot = sum(a * b for a, b in zip(pops_a, pops_b))
    mag_a = math.sqrt(sum(a * a for a in pops_a))
    mag_b = math.sqrt(sum(b * b for b in pops_b))

    if mag_a == 0 or mag_b == 0:
        return 0.0

    return max(0.0, min(1.0, dot / (mag_a * mag_b)))


def _compute_unisce_distingue(
    genre_overlap_score: float,
    artist_overlap: dict,
    genres_a: list[str],
    genres_b: list[str],
) -> tuple[list, list]:
    """Calcola cosa unisce e cosa distingue due utenti.

    'Vi unisce': artisti condivisi + generi comuni (top 5).
    'Vi distingue': artisti/generi esclusivi per utente (top 5).
    """
    # --- Vi unisce ---
    unisce = []

    # Shared artists (max 5)
    for artist in artist_overlap["shared"][:5]:
        unisce.append({"type": "artist", "name": artist["name"]})

    # Common genres via normalized intersection
    norm_a = Counter(normalize_genre(g) for g in genres_a if g)
    norm_b = Counter(normalize_genre(g) for g in genres_b if g)
    common_genres = set(norm_a.keys()) & set(norm_b.keys())
    # Sort by combined frequency
    common_sorted = sorted(
        common_genres, key=lambda g: norm_a[g] + norm_b[g], reverse=True
    )
    slots_left = 5 - len(unisce)
    for genre in common_sorted[:slots_left]:
        unisce.append({"type": "genre", "name": genre})

    # --- Vi distingue ---
    distingue = []

    # Exclusive artists per user (max 3 each)
    for name in artist_overlap["only_a"][:3]:
        distingue.append({"type": "artist", "user": "a", "name": name})
    for name in artist_overlap["only_b"][:3]:
        distingue.append({"type": "artist", "user": "b", "name": name})

    # Exclusive genres (if space)
    exclusive_a = set(norm_a.keys()) - set(norm_b.keys())
    exclusive_b = set(norm_b.keys()) - set(norm_a.keys())
    slots_left = 5 - len(distingue)
    if slots_left > 0:
        for genre in sorted(exclusive_a, key=lambda g: norm_a[g], reverse=True)[
            : slots_left // 2 + 1
        ]:
            distingue.append({"type": "genre", "user": "a", "name": genre})
    slots_left = 5 - len(distingue)
    if slots_left > 0:
        for genre in sorted(exclusive_b, key=lambda g: norm_b[g], reverse=True)[
            :slots_left
        ]:
            distingue.append({"type": "genre", "user": "b", "name": genre})

    return unisce[:5], distingue[:5]


def compute_leaderboard_rankings(friends_metrics: list[dict]) -> dict:
    """Calcola le classifiche per diverse metriche tra amici.

    Args:
        friends_metrics: lista di dict con user_id, display_name, avatar_url,
            obscurity_score, total_plays, listening_consistency, new_artists_count

    Returns:
        dict con chiavi obscurity, plays, consistency, new_artists — ciascuna
        una lista ordinata con rank.
    """
    if not friends_metrics:
        return {"obscurity": [], "plays": [], "consistency": [], "new_artists": []}

    def _rank(items: list[dict], key: str, reverse: bool = True) -> list[dict]:
        """Ordina e assegna rank."""
        sorted_items = sorted(items, key=lambda x: x.get(key, 0) or 0, reverse=reverse)
        ranked = []
        for i, item in enumerate(sorted_items, 1):
            ranked.append(
                {
                    "rank": i,
                    "user_id": item["user_id"],
                    "display_name": item.get("display_name", ""),
                    "avatar_url": item.get("avatar_url"),
                    "value": item.get(key, 0) or 0,
                }
            )
        return ranked

    return {
        "obscurity": _rank(friends_metrics, "obscurity_score"),
        "plays": _rank(friends_metrics, "total_plays"),
        "consistency": _rank(friends_metrics, "listening_consistency"),
        "new_artists": _rank(friends_metrics, "new_artists_count"),
    }
