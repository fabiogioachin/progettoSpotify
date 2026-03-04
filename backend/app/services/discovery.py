"""Discovery engine — trova brani e artisti nuovi in base al profilo d'ascolto.

Funziona anche senza audio features (API deprecata): usa la popolarita'
e i generi degli artisti come fallback per outliers e raccomandazioni.
"""

import asyncio
import logging
import math
from collections import Counter

from sqlalchemy.ext.asyncio import AsyncSession

from app.constants import FEATURE_KEYS
from app.services.audio_analyzer import get_or_fetch_features
from app.services.spotify_client import SpotifyClient
from app.utils.rate_limiter import retry_with_backoff

logger = logging.getLogger(__name__)


def _euclidean_distance(a: dict, b: dict) -> float:
    """Distanza euclidea normalizzata tra due profili audio."""
    total = 0.0
    count = 0
    for key in FEATURE_KEYS:
        va, vb = a.get(key), b.get(key)
        if va is not None and vb is not None:
            total += (va - vb) ** 2
            count += 1
    return math.sqrt(total / count) if count else 1.0


def _compute_centroid(features_list: list[dict]) -> dict:
    """Calcola il centroide (media) di una lista di profili audio."""
    if not features_list:
        return {}
    centroid = {}
    for key in FEATURE_KEYS:
        vals = [f[key] for f in features_list if f.get(key) is not None]
        centroid[key] = sum(vals) / len(vals) if vals else 0
    return centroid


async def discover(
    db: AsyncSession,
    client: SpotifyClient,
) -> dict:
    """Esegue l'algoritmo di discovery."""
    # 1. Recupera top tracks + top artists in parallelo
    top_tracks_task = retry_with_backoff(
        client.get_top_tracks, time_range="medium_term", limit=50
    )
    top_artists_task = retry_with_backoff(
        client.get_top_artists, time_range="medium_term", limit=50
    )
    # Short-term per confronto novita'
    short_tracks_task = retry_with_backoff(
        client.get_top_tracks, time_range="short_term", limit=50
    )

    top_data, artists_data, short_data = await asyncio.gather(
        top_tracks_task, top_artists_task, short_tracks_task
    )

    top_items = top_data.get("items", [])
    top_artists = artists_data.get("items", [])
    short_items = short_data.get("items", [])

    if not top_items:
        return {
            "recommendations": [],
            "outliers": [],
            "centroid": {},
            "genre_distribution": {},
            "popularity_distribution": [],
        }

    top_ids = [t["id"] for t in top_items]
    top_features = await get_or_fetch_features(db, client, top_ids)
    has_features = bool(top_features)

    # 2. Centroide audio (puo' essere vuoto se API deprecata)
    centroid = _compute_centroid(list(top_features.values()))

    # 3. Distribuzione generi (sempre disponibile)
    genre_counter = Counter()
    for artist in top_artists:
        for g in artist.get("genres", []):
            genre_counter[g] += 1
    total_genres = sum(genre_counter.values())
    genre_distribution = {
        g: round(c / total_genres * 100, 1)
        for g, c in genre_counter.most_common(12)
    } if total_genres else {}

    # 4. Outlier — usa features se disponibili, altrimenti popolarita'
    outliers = []
    if has_features and centroid:
        for tid, feat in top_features.items():
            dist = _euclidean_distance(centroid, feat)
            track_info = next((t for t in top_items if t["id"] == tid), None)
            if track_info:
                outliers.append({
                    "id": tid,
                    "name": track_info["name"],
                    "artist": track_info["artists"][0]["name"] if track_info.get("artists") else "",
                    "album_image": (track_info.get("album", {}).get("images", [{}])[0].get("url")
                                    if track_info.get("album", {}).get("images") else None),
                    "distance": round(dist, 3),
                    "metric_label": "distanza audio",
                })
        outliers.sort(key=lambda x: x["distance"], reverse=True)
    else:
        # Fallback: trova hidden gems (brani meno popolari nella tua top)
        avg_pop = sum(t.get("popularity", 0) for t in top_items) / len(top_items)
        for t in top_items:
            pop = t.get("popularity", 0)
            diff = abs(pop - avg_pop)
            outliers.append({
                "id": t["id"],
                "name": t["name"],
                "artist": t["artists"][0]["name"] if t.get("artists") else "",
                "album_image": (t.get("album", {}).get("images", [{}])[0].get("url")
                                if t.get("album", {}).get("images") else None),
                "distance": round(diff / 100, 3),
                "metric_label": "hidden gem" if pop < avg_pop else "mainstream",
            })
        # Ordina: meno popolari prima (hidden gems)
        outliers.sort(key=lambda x: x.get("distance", 0), reverse=True)

    # 5. Scoperte recenti: brani in short_term non presenti in medium_term
    medium_ids = set(top_ids)
    new_discoveries = []
    for t in short_items:
        if t["id"] not in medium_ids:
            new_discoveries.append({
                "id": t["id"],
                "name": t["name"],
                "artist": t["artists"][0]["name"] if t.get("artists") else "",
                "album": t.get("album", {}).get("name", ""),
                "album_image": (t.get("album", {}).get("images", [{}])[0].get("url")
                                if t.get("album", {}).get("images") else None),
                "popularity": t.get("popularity", 0),
                "is_new_artist": True,
            })

    # 6. Raccomandazioni: prova l'API Spotify, fallback a scoperte recenti
    recommendations = []
    seed_tracks = top_ids[:5]
    known_artist_ids = set()
    for t in top_items:
        for a in t.get("artists", []):
            if a.get("id"):
                known_artist_ids.add(a["id"])

    try:
        rec_data = await retry_with_backoff(
            client.get_recommendations, seed_tracks=seed_tracks, limit=20
        )
        for track in rec_data.get("tracks", []):
            track_artist_ids = {a["id"] for a in track.get("artists", []) if a.get("id")}
            is_new = not track_artist_ids.intersection(known_artist_ids)
            recommendations.append({
                "id": track["id"],
                "name": track["name"],
                "artist": track["artists"][0]["name"] if track.get("artists") else "",
                "album": track.get("album", {}).get("name", ""),
                "album_image": (track.get("album", {}).get("images", [{}])[0].get("url")
                                if track.get("album", {}).get("images") else None),
                "popularity": track.get("popularity", 0),
                "preview_url": track.get("preview_url"),
                "is_new_artist": is_new,
                "distance_from_profile": None,
            })
    except Exception as exc:
        logger.info("Recommendations API non disponibile: %s — uso scoperte recenti", exc)
        # Fallback: le scoperte recenti diventano i suggerimenti
        recommendations = new_discoveries[:20]

    # Se non ci sono raccomandazioni ne' scoperte, usa artisti correlati
    if not recommendations:
        recommendations = new_discoveries[:20]

    # Ordinamento: nuovi artisti prima, poi per popolarita' decrescente
    recommendations.sort(key=lambda x: (not x.get("is_new_artist", False), -(x.get("popularity", 0))))

    # 7. Distribuzione popolarita'
    popularity_buckets = {"0-20": 0, "21-40": 0, "41-60": 0, "61-80": 0, "81-100": 0}
    for t in top_items:
        pop = t.get("popularity", 0)
        if pop <= 20:
            popularity_buckets["0-20"] += 1
        elif pop <= 40:
            popularity_buckets["21-40"] += 1
        elif pop <= 60:
            popularity_buckets["41-60"] += 1
        elif pop <= 80:
            popularity_buckets["61-80"] += 1
        else:
            popularity_buckets["81-100"] += 1

    popularity_distribution = [
        {"range": k, "count": v} for k, v in popularity_buckets.items()
    ]

    return {
        "recommendations": recommendations[:20],
        "outliers": outliers[:10],
        "centroid": {k: round(v, 3) for k, v in centroid.items()} if centroid else {},
        "genre_distribution": genre_distribution,
        "popularity_distribution": popularity_distribution,
        "has_audio_features": has_features,
    }
