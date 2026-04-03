"""Aggregazione e analisi audio features."""

from __future__ import annotations

import logging
from collections import Counter
from typing import TYPE_CHECKING

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.constants import FEATURE_KEYS
from app.models.track import AudioFeatures
from app.services.genre_cache import get_artist_genres_cached
from app.services.popularity_cache import read_popularity_cache
from app.services.spotify_client import SpotifyClient
from app.utils.rate_limiter import (
    SpotifyAuthError,
    retry_with_backoff,
)

if TYPE_CHECKING:
    from app.services.data_bundle import RequestDataBundle

# NOTE: Spotify Audio Features API è deprecata (403 permanente da Feb 2026).
# get_or_fetch_features() fa solo cache lookup — non chiama mai l'API.

logger = logging.getLogger(__name__)


async def compute_profile(
    db: AsyncSession,
    client: SpotifyClient,
    time_range: str = "medium_term",
    pre_genres: dict[str, float] | None = None,
    bundle: RequestDataBundle | None = None,
) -> dict:
    """Calcola il profilo audio completo dell'utente per un periodo.

    Args:
        pre_genres: if provided, skip _extract_genres and use these directly.
        bundle: if provided, use cached data from the request-scoped bundle
                instead of making direct Spotify API calls.
    """
    if bundle is not None:
        data = await bundle.get_top_tracks(time_range=time_range, limit=50)
    else:
        data = await retry_with_backoff(
            client.get_top_tracks, time_range=time_range, limit=50
        )
    items = data.get("items", [])

    if not items:
        return {
            "features": {},
            "genres": {},
            "track_count": 0,
            "popularity_avg": 0,
            "unique_artists": 0,
            "top_artist": "—",
        }

    track_ids = [t["id"] for t in items]

    # Popularity: leggi dalla cache DB (zero API calls)
    await read_popularity_cache(items, db)

    # Stats sempre disponibili (non dipendono da audio features)
    popularities = [t.get("popularity", 0) for t in items]
    popularity_avg = (
        round(sum(popularities) / len(popularities), 1) if popularities else 0
    )

    artist_counter = Counter()
    for t in items:
        for a in t.get("artists", []):
            if a.get("name"):
                artist_counter[a["name"]] += 1
    unique_artists = len(artist_counter)
    top_artist = artist_counter.most_common(1)[0][0] if artist_counter else "—"

    # Audio features (solo cache — API deprecata)
    features = await get_or_fetch_features(db, track_ids)

    averages = {}
    for key in FEATURE_KEYS:
        vals = [f[key] for f in features.values() if f.get(key) is not None]
        averages[key] = round(sum(vals) / len(vals), 3) if vals else 0

    # Tempo medio (separato perche' scala diversa)
    tempos = [f["tempo"] for f in features.values() if f.get("tempo") is not None]
    averages["tempo"] = round(sum(tempos) / len(tempos), 1) if tempos else 0

    # Distribuzione generi — usa pre_genres se forniti, altrimenti fetch
    genres = (
        pre_genres
        if pre_genres is not None
        else await _extract_genres(db, client, items)
    )

    return {
        "features": averages,
        "genres": genres,
        "track_count": len(items),
        "popularity_avg": popularity_avg,
        "unique_artists": unique_artists,
        "top_artist": top_artist,
    }


async def _safe_compute(coro, time_range: str):
    """Una chiamata fallita non deve crashare l'intero endpoint trends."""
    try:
        return await coro
    except SpotifyAuthError:
        raise
    except Exception as exc:
        logger.warning("compute_profile(%s) fallito: %s", time_range, exc)
        return None


async def compute_trends(
    db: AsyncSession,
    client: SpotifyClient,
    user_id: int,
    bundle: RequestDataBundle | None = None,
) -> list[dict]:
    """Calcola i trend confrontando short, medium e long term.

    Fetches genres ONCE for all unique artists across the 3 time ranges,
    then passes pre-computed genre distributions to each compute_profile call.

    Args:
        bundle: if provided, use cached data from the request-scoped bundle
                instead of making direct Spotify API calls. The bundle is also
                forwarded to compute_profile so that the same cached data is reused.
    """
    labels = {
        "short_term": "Ultimo mese",
        "medium_term": "Ultimi 6 mesi",
        "long_term": "Sempre",
    }
    time_ranges = ["short_term", "medium_term", "long_term"]

    # Step 1: Fetch top_tracks for all 3 ranges (bundle deduplicates API calls)
    all_period_tracks: dict[str, list] = {}
    for tr in time_ranges:
        try:
            if bundle is not None:
                data = await bundle.get_top_tracks(time_range=tr, limit=50)
            else:
                data = await retry_with_backoff(
                    client.get_top_tracks, time_range=tr, limit=50
                )
            all_period_tracks[tr] = data.get("items", [])
        except SpotifyAuthError:
            raise
        except Exception as exc:
            logger.warning("compute_trends: fetch top_tracks(%s) fallito: %s", tr, exc)
            all_period_tracks[tr] = []

    # Step 2: Collect ALL unique artist IDs across all periods
    all_artist_ids: set[str] = set()
    for tracks in all_period_tracks.values():
        for t in tracks:
            for a in t.get("artists", []):
                if a.get("id"):
                    all_artist_ids.add(a["id"])

    # Step 3: Fetch genres ONCE for unique artists (DB-cached, 7d TTL, no cap)
    artist_genres_map = await get_artist_genres_cached(db, client, list(all_artist_ids))

    # Step 4: Build per-period genre distributions from cached genres
    def _genres_for_period(tracks: list[dict]) -> dict[str, float]:
        counter = Counter()
        for t in tracks:
            for a in t.get("artists", []):
                aid = a.get("id")
                if aid and aid in artist_genres_map:
                    for g in artist_genres_map[aid]:
                        counter[g] += 1
        if not counter:
            return {}
        total = sum(counter.values())
        return {g: round(c / total * 100, 1) for g, c in counter.most_common(15)}

    # Step 5: Compute profiles with pre-computed genres
    trends = []
    for tr in time_ranges:
        pre_genres = _genres_for_period(all_period_tracks[tr])
        profile = await _safe_compute(
            compute_profile(db, client, tr, pre_genres=pre_genres, bundle=bundle), tr
        )
        if profile is not None:
            trends.append({"period": tr, "label": labels[tr], **profile})
    return trends


async def _extract_genres(
    db: AsyncSession, client: SpotifyClient, tracks: list[dict]
) -> dict[str, float]:
    """Estrae distribuzione generi dagli artisti dei brani (DB-cached, 7d TTL)."""
    artist_ids: set[str] = set()
    for t in tracks:
        for a in t.get("artists", []):
            if a.get("id"):
                artist_ids.add(a["id"])

    if not artist_ids:
        return {}

    # Fetch genres via DB cache + Spotify API fallback (no cap — cache handles dedup)
    artist_genres_map = await get_artist_genres_cached(db, client, list(artist_ids))

    all_genres: list[str] = []
    for genres in artist_genres_map.values():
        all_genres.extend(genres)

    if not all_genres:
        return {}

    counter = Counter(all_genres)
    total = sum(counter.values())
    return {
        genre: round(count / total * 100, 1) for genre, count in counter.most_common(15)
    }


async def get_or_fetch_features(
    db: AsyncSession, track_ids: list[str]
) -> dict[str, dict]:
    """Recupera audio features dalla cache DB (pure lookup, no API call).

    L'endpoint Spotify /v1/audio-features è deprecato (403 permanente da Feb 2026).
    Restituisce solo i dati storici già presenti nel DB.
    """
    if not track_ids:
        return {}

    result = await db.execute(
        select(AudioFeatures).where(AudioFeatures.track_spotify_id.in_(track_ids))
    )
    cached = {f.track_spotify_id: f for f in result.scalars().all()}

    missing_count = sum(1 for tid in track_ids if tid not in cached)
    if missing_count:
        logger.debug(
            "Audio features cache miss: %d/%d track IDs not in DB (API deprecated, skipping fetch)",
            missing_count,
            len(track_ids),
        )

    features_map = {}
    for tid in track_ids:
        af = cached.get(tid)
        if af:
            features_map[tid] = {
                "danceability": af.danceability,
                "energy": af.energy,
                "valence": af.valence,
                "acousticness": af.acousticness,
                "instrumentalness": af.instrumentalness,
                "liveness": af.liveness,
                "speechiness": af.speechiness,
                "tempo": af.tempo,
            }
    return features_map
