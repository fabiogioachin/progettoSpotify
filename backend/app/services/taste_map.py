"""Calcolo TasteMap — proiezione PCA 2D del gusto musicale.

Modulo che orchestra il calcolo della mappa del gusto. Usa SpotifyClient per
il fetch iniziale degli artisti, poi delega a taste_clustering per il calcolo
puro (feature matrix, PCA).
"""

import logging
from collections import defaultdict

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.constants import FEATURE_KEYS
from app.models.listening_history import RecentPlay
from app.models.track import AudioFeatures
from app.services.genre_utils import normalize_genre
from app.services.spotify_client import SpotifyClient
from app.services.taste_clustering import build_feature_matrix, compute_taste_pca
from app.utils.rate_limiter import retry_with_backoff

logger = logging.getLogger(__name__)


async def _load_audio_features_by_artist(
    db: AsyncSession, user_id: int, artists: list[dict]
) -> dict[str, dict] | None:
    """Carica audio features dal DB e le media per artista.

    Usa la tabella RecentPlay per mappare artist → track, poi AudioFeatures
    per ottenere le feature. Ritorna {artist_id: {energy, danceability, ...}}
    oppure None se nessun dato disponibile.

    Pure DB lookup — nessuna chiamata API.
    """
    artist_ids = [a["id"] for a in artists if a.get("id")]
    if not artist_ids:
        return None

    try:
        # Step 1: Get track IDs for these artists from RecentPlay
        result = await db.execute(
            select(
                RecentPlay.artist_spotify_id,
                RecentPlay.track_spotify_id,
            )
            .where(
                RecentPlay.user_id == user_id,
                RecentPlay.artist_spotify_id.in_(artist_ids),
            )
            .distinct()
        )
        artist_track_rows = result.all()

        if not artist_track_rows:
            return None

        # Build mapping: artist_id → [track_ids]
        artist_to_tracks: dict[str, list[str]] = defaultdict(list)
        all_track_ids: set[str] = set()
        for artist_id, track_id in artist_track_rows:
            artist_to_tracks[artist_id].append(track_id)
            all_track_ids.add(track_id)

        # Step 2: Fetch AudioFeatures for all track IDs
        result = await db.execute(
            select(AudioFeatures).where(
                AudioFeatures.track_spotify_id.in_(list(all_track_ids))
            )
        )
        features_by_track = {af.track_spotify_id: af for af in result.scalars().all()}

        if not features_by_track:
            return None

        # Step 3: Average features per artist
        audio_features: dict[str, dict] = {}
        for artist_id, track_ids in artist_to_tracks.items():
            feature_accum: dict[str, list[float]] = defaultdict(list)
            for tid in track_ids:
                af = features_by_track.get(tid)
                if af is None:
                    continue
                for key in FEATURE_KEYS:
                    val = getattr(af, key, None)
                    if val is not None:
                        feature_accum[key].append(val)

            if feature_accum:
                audio_features[artist_id] = {
                    key: sum(vals) / len(vals) for key, vals in feature_accum.items()
                }

        if not audio_features:
            return None

        logger.info(
            "TasteMap: audio features caricate per %d/%d artisti",
            len(audio_features),
            len(artist_ids),
        )
        return audio_features

    except Exception as exc:
        logger.warning("TasteMap: caricamento audio features fallito: %s", exc)
        return None


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
    # AudioFeatures is keyed by track_spotify_id; we need {artist_id: avg_features}.
    # Use RecentPlay to map artist_spotify_id → track_spotify_id, then average.
    audio_features = await _load_audio_features_by_artist(db, user_id, artists)

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
