"""Aggregazione e analisi audio features."""

import json
import logging
from collections import Counter

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.constants import ARTIST_GENRE_CAP_TRENDS, FEATURE_KEYS
from app.models.listening_history import ListeningSnapshot
from app.models.track import AudioFeatures
from app.services.popularity_cache import read_popularity_cache
from app.services.spotify_client import SpotifyClient
from app.utils.rate_limiter import (
    RateLimitError,
    SpotifyAuthError,
    gather_in_chunks,
    retry_with_backoff,
)

# NOTE: Spotify Audio Features API è deprecata (403 permanente da Feb 2026).
# get_or_fetch_features() fa solo cache lookup — non chiama mai l'API.

logger = logging.getLogger(__name__)


async def compute_profile(
    db: AsyncSession,
    client: SpotifyClient,
    time_range: str = "medium_term",
    pre_genres: dict[str, float] | None = None,
) -> dict:
    """Calcola il profilo audio completo dell'utente per un periodo.

    Args:
        pre_genres: if provided, skip _extract_genres and use these directly.
    """
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
        pre_genres if pre_genres is not None else await _extract_genres(client, items)
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
    db: AsyncSession, client: SpotifyClient, user_id: int
) -> list[dict]:
    """Calcola i trend confrontando short, medium e long term.

    Fetches genres ONCE for all unique artists across the 3 time ranges,
    then passes pre-computed genre distributions to each compute_profile call.
    """
    labels = {
        "short_term": "Ultimo mese",
        "medium_term": "Ultimi 6 mesi",
        "long_term": "Sempre",
    }
    time_ranges = ["short_term", "medium_term", "long_term"]

    # Step 1: Fetch top_tracks for all 3 ranges (cached, ~0 API calls)
    all_period_tracks: dict[str, list] = {}
    for tr in time_ranges:
        try:
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

    # Step 3: Fetch genres ONCE for unique artists (cap=50)
    artist_genres_map: dict[str, list[str]] = {}
    capped = list(all_artist_ids)[:ARTIST_GENRE_CAP_TRENDS]

    async def _fetch_artist_genres(aid: str) -> tuple[str, list[str]]:
        try:
            artist = await retry_with_backoff(client.get_artist, aid)
            return aid, artist.get("genres", [])
        except SpotifyAuthError:
            raise
        except Exception:
            return aid, []

    results = await gather_in_chunks(
        [_fetch_artist_genres(aid) for aid in capped],
        chunk_size=4,
    )
    for r in results:
        if isinstance(r, (SpotifyAuthError, RateLimitError)):
            raise r
        if isinstance(r, tuple):
            artist_genres_map[r[0]] = r[1]

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
            compute_profile(db, client, tr, pre_genres=pre_genres), tr
        )
        if profile is not None:
            trends.append({"period": tr, "label": labels[tr], **profile})
    return trends


async def save_snapshot(db: AsyncSession, user_id: int, period: str, profile: dict):
    """Salva uno snapshot delle medie per tracking storico (max 1 per giorno/periodo)."""
    from datetime import datetime, timezone

    from sqlalchemy import func

    features = profile.get("features", {})
    genres = profile.get("genres", {})
    today = datetime.now(timezone.utc).date()

    fields = {
        "avg_energy": features.get("energy"),
        "avg_valence": features.get("valence"),
        "avg_danceability": features.get("danceability"),
        "avg_acousticness": features.get("acousticness"),
        "avg_instrumentalness": features.get("instrumentalness"),
        "avg_speechiness": features.get("speechiness"),
        "avg_liveness": features.get("liveness"),
        "avg_tempo": features.get("tempo"),
        "top_genre": max(genres, key=genres.get) if genres else None,
        "genre_distribution": json.dumps(genres) if genres else None,
        "track_count": profile.get("track_count", 0),
    }

    result = await db.execute(
        select(ListeningSnapshot).where(
            ListeningSnapshot.user_id == user_id,
            ListeningSnapshot.period == period,
            func.date(ListeningSnapshot.snapshot_date) == today,
        )
    )
    existing = result.scalar_one_or_none()

    if existing:
        for attr, value in fields.items():
            setattr(existing, attr, value)
    else:
        snapshot = ListeningSnapshot(user_id=user_id, period=period, **fields)
        db.add(snapshot)
    await db.commit()


async def get_historical_snapshots(db: AsyncSession, user_id: int) -> list[dict]:
    """Recupera gli snapshot storici dell'utente."""
    result = await db.execute(
        select(ListeningSnapshot)
        .where(ListeningSnapshot.user_id == user_id)
        .order_by(ListeningSnapshot.snapshot_date.asc())
    )
    snapshots = result.scalars().all()
    return [
        {
            "date": s.snapshot_date.isoformat() if s.snapshot_date else None,
            "period": s.period,
            "energy": s.avg_energy,
            "valence": s.avg_valence,
            "danceability": s.avg_danceability,
            "acousticness": s.avg_acousticness,
            "instrumentalness": s.avg_instrumentalness,
            "speechiness": s.avg_speechiness,
            "liveness": s.avg_liveness,
            "tempo": s.avg_tempo,
            "top_genre": s.top_genre,
            "genres": json.loads(s.genre_distribution) if s.genre_distribution else {},
            "track_count": s.track_count,
        }
        for s in snapshots
    ]


async def _extract_genres(
    client: SpotifyClient, tracks: list[dict]
) -> dict[str, float]:
    """Estrae distribuzione generi dagli artisti dei brani."""
    artist_ids = set()
    for t in tracks:
        for a in t.get("artists", []):
            if a.get("id"):
                artist_ids.add(a["id"])

    if not artist_ids:
        return {}

    # Fetch artists individually (batch GET /artists removed in dev mode Feb 2026)
    all_genres: list[str] = []
    artist_list = list(artist_ids)[:ARTIST_GENRE_CAP_TRENDS]

    async def _fetch_genres(aid: str) -> list[str]:
        try:
            artist = await retry_with_backoff(client.get_artist, aid)
            return artist.get("genres", [])
        except SpotifyAuthError:
            raise
        except Exception:
            return []

    results = await gather_in_chunks(
        [_fetch_genres(aid) for aid in artist_list],
        chunk_size=4,
    )
    for r in results:
        if isinstance(r, SpotifyAuthError):
            raise r
        if isinstance(r, list):
            all_genres.extend(r)

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
