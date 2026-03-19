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
from app.services.popularity_cache import read_popularity_cache
from app.services.spotify_client import SpotifyClient
from app.services.taste_clustering import (
    build_feature_matrix,
    compute_cosine_similarities,
    detect_outliers_isolation_forest,
)
from app.utils.rate_limiter import (
    SpotifyAuthError,
    retry_with_backoff,
)

logger = logging.getLogger(__name__)


def _album_image(track: dict) -> str | None:
    """Estrae l'URL della prima immagine dell'album di un brano."""
    images = track.get("album", {}).get("images")
    return images[0].get("url") if images else None


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
        top_tracks_task,
        top_artists_task,
        short_tracks_task,
        return_exceptions=True,
    )
    # Re-raise auth errors; gracefully degrade on other failures
    for result in (top_data, artists_data, short_data):
        if isinstance(result, SpotifyAuthError):
            raise result
    if isinstance(top_data, BaseException):
        top_data = {"items": []}
    if isinstance(artists_data, BaseException):
        artists_data = {"items": []}
    if isinstance(short_data, BaseException):
        short_data = {"items": []}

    top_items = top_data.get("items", [])
    top_artists = artists_data.get("items", [])
    short_items = short_data.get("items", [])

    # Popularity: leggi dalla cache DB (zero API calls)
    all_track_items = top_items + short_items
    await read_popularity_cache(all_track_items, db)

    if not top_items:
        return {
            "recommendations": [],
            "outliers": [],
            "centroid": {},
            "genre_distribution": {},
            "popularity_distribution": [],
        }

    top_ids = [t["id"] for t in top_items]
    top_features = await get_or_fetch_features(db, top_ids)
    has_features = bool(top_features)

    # 2. Centroide audio (puo' essere vuoto se API deprecata)
    centroid = _compute_centroid(list(top_features.values()))

    # 3. Distribuzione generi (sempre disponibile)
    genre_counter = Counter()
    for artist in top_artists:
        for g in artist.get("genres", []):
            genre_counter[g] += 1
    total_genres = sum(genre_counter.values())
    genre_distribution = (
        {g: round(c / total_genres * 100, 1) for g, c in genre_counter.most_common(12)}
        if total_genres
        else {}
    )

    # 4. Outlier — tre livelli: Isolation Forest → distanza euclidea → popolarita'
    outliers = []

    # 4a. Isolation Forest (sklearn) — se abbiamo features e abbastanza tracce
    if has_features and len(top_features) >= 5:
        try:
            track_dicts = []
            for t in top_items:
                tid = t["id"]
                if tid in top_features:
                    track_dicts.append(
                        {
                            "id": tid,
                            "genres": [],  # tracce non hanno generi direttamente
                            "popularity": t.get("popularity", 0),
                            "followers": 0,
                        }
                    )

            track_matrix, track_ids, _ = build_feature_matrix(
                track_dicts,
                audio_features={
                    t["id"]: top_features[t["id"]]
                    for t in top_items
                    if t["id"] in top_features
                },
            )

            outlier_ids = detect_outliers_isolation_forest(track_matrix, track_ids)

            for tid in outlier_ids:
                track_info = next((t for t in top_items if t["id"] == tid), None)
                if track_info:
                    outliers.append(
                        {
                            "id": tid,
                            "name": track_info["name"],
                            "artist": track_info["artists"][0]["name"]
                            if track_info.get("artists")
                            else "",
                            "album_image": _album_image(track_info),
                            "distance": 0,  # Non applicabile per Isolation Forest
                            "metric_label": "outlier",
                        }
                    )
        except Exception as exc:
            logger.warning("Isolation Forest fallito, fallback euclidea: %s", exc)
            outliers = []

    # 4b. Fallback distanza euclidea — se sklearn non ha prodotto risultati
    if not outliers and has_features and centroid:
        for tid, feat in top_features.items():
            dist = _euclidean_distance(centroid, feat)
            track_info = next((t for t in top_items if t["id"] == tid), None)
            if track_info:
                outliers.append(
                    {
                        "id": tid,
                        "name": track_info["name"],
                        "artist": track_info["artists"][0]["name"]
                        if track_info.get("artists")
                        else "",
                        "album_image": _album_image(track_info),
                        "distance": round(dist, 3),
                        "metric_label": "distanza audio",
                    }
                )
        outliers.sort(key=lambda x: x["distance"], reverse=True)

    # 4c. Fallback popolarita' — hidden gems sotto la media
    if not outliers:
        avg_pop = sum(t.get("popularity", 0) for t in top_items) / len(top_items)
        for t in top_items:
            pop = t.get("popularity", 0)
            if pop < avg_pop:
                outliers.append(
                    {
                        "id": t["id"],
                        "name": t["name"],
                        "artist": t["artists"][0]["name"] if t.get("artists") else "",
                        "album_image": _album_image(t),
                        "distance": round(pop / 100, 3),
                        "metric_label": f"Pop. {pop}",
                    }
                )
        # Ordina per popolarità crescente (veri hidden gems prima)
        outliers.sort(key=lambda x: x["distance"])

    # 5. Scoperte recenti: brani in short_term non presenti in medium_term
    medium_ids = set(top_ids)
    new_discoveries = []
    for t in short_items:
        if t["id"] not in medium_ids:
            new_discoveries.append(
                {
                    "id": t["id"],
                    "name": t["name"],
                    "artist": t["artists"][0]["name"] if t.get("artists") else "",
                    "album": t.get("album", {}).get("name", ""),
                    "album_image": _album_image(t),
                    "popularity": t.get("popularity", 0),
                    "is_new_artist": True,
                }
            )

    # 5b. Raccomandazioni: scoperte recenti (related_artists API rimossa in dev mode)
    recommendations = new_discoveries[:20]
    recommendations_source = "recent_discoveries"

    # Ordinamento: nuovi artisti prima, poi per popolarita' decrescente
    recommendations.sort(
        key=lambda x: (not x.get("is_new_artist", False), -(x.get("popularity", 0)))
    )

    # 6. Similarity scoring con coseno (additive, non-blocking)
    try:
        if len(top_artists) >= 5:
            artist_dicts = [
                {
                    "id": a["id"],
                    "genres": a.get("genres", [])[:5],
                    "popularity": a.get("popularity", 0),
                    "followers": a.get("followers", {}).get("total", 0),
                }
                for a in top_artists
            ]
            artist_matrix, artist_ids_list, _ = build_feature_matrix(artist_dicts)
            similarity_scores = compute_cosine_similarities(
                artist_matrix, artist_ids_list
            )

            # Build id->similarity map for fast lookup
            artist_name_to_id = {a.get("name", ""): a["id"] for a in top_artists}
            for rec in recommendations:
                artist_id = artist_name_to_id.get(rec.get("artist", ""))
                if artist_id:
                    rec["similarity_score"] = similarity_scores.get(artist_id)
    except Exception as exc:
        logger.warning("Similarity scoring fallito: %s", exc)

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
        "recommendations_source": recommendations_source,
    }
