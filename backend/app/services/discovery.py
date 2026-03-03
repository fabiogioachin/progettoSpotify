"""Discovery engine — trova brani e artisti nuovi in base al profilo d'ascolto."""

import math

from sqlalchemy.ext.asyncio import AsyncSession

from app.constants import FEATURE_KEYS
from app.routers.library import _get_or_fetch_features
from app.services.spotify_client import SpotifyClient
from app.utils.rate_limiter import retry_with_backoff


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
    # 1. Recupera top tracks (seed)
    top_data = await retry_with_backoff(client.get_top_tracks, time_range="medium_term", limit=50)
    top_items = top_data.get("items", [])

    if not top_items:
        return {"recommendations": [], "outliers": [], "centroid": {}}

    top_ids = [t["id"] for t in top_items]
    top_features = await _get_or_fetch_features(db, client, top_ids)

    # 2. Calcola centroide
    centroid = _compute_centroid(list(top_features.values()))

    # 3. Trova outlier nella libreria (brani lontani dal centroide)
    outliers = []
    for tid, feat in top_features.items():
        dist = _euclidean_distance(centroid, feat)
        track_info = next((t for t in top_items if t["id"] == tid), None)
        if track_info:
            outliers.append({
                "id": tid,
                "name": track_info["name"],
                "artist": track_info["artists"][0]["name"] if track_info.get("artists") else "",
                "distance": round(dist, 3),
                "features": feat,
            })

    outliers.sort(key=lambda x: x["distance"], reverse=True)

    # 4. Chiama recommendations con seed dei top 5 tracks
    seed_tracks = top_ids[:5]
    known_artist_ids = set()
    for t in top_items:
        for a in t.get("artists", []):
            if a.get("id"):
                known_artist_ids.add(a["id"])

    recommendations = []
    try:
        rec_data = await retry_with_backoff(client.get_recommendations, seed_tracks=seed_tracks, limit=20)
        for track in rec_data.get("tracks", []):
            # Filtra artisti gia' noti
            track_artist_ids = {a["id"] for a in track.get("artists", []) if a.get("id")}
            is_new = not track_artist_ids.intersection(known_artist_ids)

            recommendations.append({
                "id": track["id"],
                "name": track["name"],
                "artist": track["artists"][0]["name"] if track.get("artists") else "",
                "artist_id": track["artists"][0]["id"] if track.get("artists") else None,
                "album": track.get("album", {}).get("name", ""),
                "album_image": (track.get("album", {}).get("images", [{}])[0].get("url")
                                if track.get("album", {}).get("images") else None),
                "popularity": track.get("popularity", 0),
                "preview_url": track.get("preview_url"),
                "is_new_artist": is_new,
            })
    except Exception:
        pass  # Recommendations opzionali

    # Fetch features per le recommendations
    rec_ids = [r["id"] for r in recommendations]
    rec_features = await _get_or_fetch_features(db, client, rec_ids)

    for rec in recommendations:
        feat = rec_features.get(rec["id"])
        if feat:
            rec["features"] = feat
            rec["distance_from_profile"] = round(_euclidean_distance(centroid, feat), 3)
        else:
            rec["distance_from_profile"] = None

    # Ordina: prima artisti nuovi, poi per distanza dal profilo
    recommendations.sort(key=lambda x: (not x["is_new_artist"], x.get("distance_from_profile") or 1))

    return {
        "recommendations": recommendations[:20],
        "outliers": outliers[:10],
        "centroid": {k: round(v, 3) for k, v in centroid.items()},
    }
