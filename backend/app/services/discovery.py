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
            "hidden_gems": [],
            "new_discoveries": [],
            "related_suggestions": [],
            "centroid": {},
            "genre_distribution": {},
            "popularity_distribution": [],
            "has_audio_features": False,
            "recommendations_source": "recent_discoveries",
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

    # 4. Chicche Nascoste — bottom quartile di popolarita' tra i tuoi top
    all_pops = sorted(t.get("popularity", 0) for t in top_items)
    q1_index = max(1, len(all_pops) // 4)
    q1_threshold = all_pops[q1_index - 1]  # 25th percentile

    hidden_gems = []
    for t in top_items:
        pop = t.get("popularity", 0)
        if pop <= q1_threshold:
            hidden_gems.append({
                "id": t["id"],
                "name": t["name"],
                "artist": t["artists"][0]["name"] if t.get("artists") else "",
                "album_image": (t.get("album", {}).get("images", [{}])[0].get("url")
                                if t.get("album", {}).get("images") else None),
                "popularity": pop,
                "metric_label": f"Pop. {pop}",
            })
    hidden_gems.sort(key=lambda x: x["popularity"])

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
    recommendations_source = "spotify"
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
        recommendations = new_discoveries[:20]
        recommendations_source = "recent_discoveries"

    if not recommendations:
        recommendations = new_discoveries[:20]
        recommendations_source = "recent_discoveries"

    recommendations.sort(key=lambda x: (not x.get("is_new_artist", False), -(x.get("popularity", 0))))

    # 7. Da Artisti Simili — brani da artisti correlati ai tuoi preferiti
    related_suggestions = []
    top_artist_ids_list = [a["id"] for a in top_artists[:8]]
    top_artist_names = {a["id"]: a.get("name", "") for a in top_artists}

    sem = asyncio.Semaphore(3)

    async def _fetch_related_tracks(artist_id):
        async with sem:
            try:
                related_data = await retry_with_backoff(
                    client.get_related_artists, artist_id
                )
                related_list = related_data.get("artists", [])
                results = []
                for rel in related_list[:3]:
                    rel_id = rel["id"]
                    if rel_id in known_artist_ids:
                        continue
                    try:
                        top_tr = await retry_with_backoff(
                            client.get_artist_top_tracks, rel_id
                        )
                        tracks_list = top_tr.get("tracks", [])
                        if tracks_list:
                            best = tracks_list[0]
                            results.append({
                                "id": best["id"],
                                "name": best["name"],
                                "artist": rel.get("name", ""),
                                "album": best.get("album", {}).get("name", ""),
                                "album_image": (best.get("album", {}).get("images", [{}])[0].get("url")
                                                if best.get("album", {}).get("images") else None),
                                "popularity": best.get("popularity", 0),
                                "related_to": top_artist_names.get(artist_id, ""),
                            })
                    except Exception:
                        pass
                return results
            except Exception as exc:
                logger.warning("Errore fetch related per %s: %s", artist_id, exc)
                return []

    related_tasks = [_fetch_related_tracks(aid) for aid in top_artist_ids_list]
    related_results = await asyncio.gather(*related_tasks, return_exceptions=True)

    seen_related_ids = set()
    for result in related_results:
        if isinstance(result, Exception):
            continue
        for item in result:
            if item["id"] not in seen_related_ids:
                seen_related_ids.add(item["id"])
                related_suggestions.append(item)

    related_suggestions.sort(key=lambda x: -x.get("popularity", 0))

    # 8. Distribuzione popolarita'
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
        "hidden_gems": hidden_gems[:8],
        "new_discoveries": new_discoveries[:10],
        "related_suggestions": related_suggestions[:10],
        "centroid": {k: round(v, 3) for k, v in centroid.items()} if centroid else {},
        "genre_distribution": genre_distribution,
        "popularity_distribution": popularity_distribution,
        "has_audio_features": has_features,
        "recommendations_source": recommendations_source,
    }
