"""Calcolo TasteMap — proiezione PCA 2D del gusto musicale.

Modulo che orchestra il calcolo della mappa del gusto. Usa SpotifyClient per
il fetch iniziale degli artisti, poi delega a taste_clustering per il calcolo
puro (feature matrix, PCA).
"""

import logging

from sqlalchemy.ext.asyncio import AsyncSession

from app.services.genre_utils import normalize_genre
from app.services.spotify_client import SpotifyClient
from app.services.taste_clustering import build_feature_matrix, compute_taste_pca
from app.utils.rate_limiter import retry_with_backoff

logger = logging.getLogger(__name__)


async def compute_taste_map(
    db: AsyncSession, client: SpotifyClient, user_id: int
) -> dict:
    """Calcola la TasteMap per il profilo utente.

    1. Fetch top artists (medium_term, limit=50)
    2. Get audio features from DB cache (optional)
    3. Build feature matrix (genres + popularity, enriched with audio if available)
    4. PCA 2D
    5. Return {points, variance_explained, feature_mode, genre_groups}
    """
    # 1. Fetch top artists
    artists_data = await retry_with_backoff(
        client.get_top_artists, time_range="medium_term", limit=50
    )

    artists = artists_data.get("items", [])
    if len(artists) < 3:
        return {
            "points": [],
            "variance_explained": [0.0, 0.0],
            "feature_mode": "insufficient",
            "genre_groups": {},
        }

    # 2. Try to get audio features from DB cache (optional enrichment)
    # Audio features are keyed by artist_id with averaged feature values
    # For now, we work with genres + popularity only (audio is optional enrichment)
    audio_features = None  # TODO: fetch from AudioFeatures table if available

    # 3. Build feature matrix
    artist_dicts = []
    for a in artists:
        artist_dicts.append(
            {
                "id": a["id"],
                "name": a.get("name", ""),
                "genres": a.get("genres", [])[:5],
                "popularity": a.get("popularity", 0),
                "followers": a.get("followers", {}).get("total", 0),
            }
        )

    matrix, artist_ids, feature_names = build_feature_matrix(
        artist_dicts, audio_features=audio_features
    )

    if matrix.shape[0] < 3:
        return {
            "points": [],
            "variance_explained": [0.0, 0.0],
            "feature_mode": "insufficient",
            "genre_groups": {},
        }

    # 4. PCA 2D
    pca_result = compute_taste_pca(matrix, artist_ids)

    # 5. Enrich points with artist metadata
    artist_map = {a["id"]: a for a in artist_dicts}
    for point in pca_result.get("points", []):
        a = artist_map.get(point["id"], {})
        point["name"] = a.get("name", "")
        point["popularity"] = a.get("popularity", 0)
        genres = a.get("genres", [])
        point["primary_genre"] = normalize_genre(genres[0]) if genres else ""

    # 6. Build genre groups for coloring
    genre_counter: dict[str, int] = {}
    for a in artist_dicts:
        for g in a.get("genres", [])[:1]:  # primary genre only
            ng = normalize_genre(g)
            if ng:
                genre_counter[ng] = genre_counter.get(ng, 0) + 1

    # Top 6 genres for distinct colors, rest = "altro"
    top_genres = sorted(genre_counter.items(), key=lambda x: x[1], reverse=True)[:6]
    genre_groups = {g: c for g, c in top_genres}

    return {
        "points": pca_result.get("points", []),
        "variance_explained": pca_result.get("variance_explained", [0.0, 0.0]),
        "feature_mode": pca_result.get("feature_mode", "genre_popularity"),
        "genre_groups": genre_groups,
    }
