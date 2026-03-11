"""Aggregazione e analisi audio features."""

import asyncio
import json
import logging
from collections import Counter

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.constants import FEATURE_KEYS
from app.models.listening_history import ListeningSnapshot
from app.models.track import AudioFeatures
from app.services.spotify_client import SpotifyClient
from app.utils.rate_limiter import retry_with_backoff

logger = logging.getLogger(__name__)


async def compute_profile(
    db: AsyncSession, client: SpotifyClient, time_range: str = "medium_term"
) -> dict:
    """Calcola il profilo audio completo dell'utente per un periodo."""
    data = await retry_with_backoff(client.get_top_tracks, time_range=time_range, limit=50)
    items = data.get("items", [])

    if not items:
        return {"features": {}, "genres": {}, "track_count": 0,
                "popularity_avg": 0, "unique_artists": 0, "top_artist": "—"}

    track_ids = [t["id"] for t in items]

    # Stats sempre disponibili (non dipendono da audio features)
    popularities = [t.get("popularity", 0) for t in items]
    popularity_avg = round(sum(popularities) / len(popularities), 1) if popularities else 0

    artist_counter = Counter()
    for t in items:
        for a in t.get("artists", []):
            if a.get("name"):
                artist_counter[a["name"]] += 1
    unique_artists = len(artist_counter)
    top_artist = artist_counter.most_common(1)[0][0] if artist_counter else "—"

    # Audio features (possono essere vuote se API deprecata)
    features = await get_or_fetch_features(db, client, track_ids)

    averages = {}
    for key in FEATURE_KEYS:
        vals = [f[key] for f in features.values() if f.get(key) is not None]
        averages[key] = round(sum(vals) / len(vals), 3) if vals else 0

    # Tempo medio (separato perche' scala diversa)
    tempos = [f["tempo"] for f in features.values() if f.get("tempo") is not None]
    averages["tempo"] = round(sum(tempos) / len(tempos), 1) if tempos else 0

    # Distribuzione generi (dai top artists)
    genres = await _extract_genres(client, items)

    return {
        "features": averages,
        "genres": genres,
        "track_count": len(items),
        "popularity_avg": popularity_avg,
        "unique_artists": unique_artists,
        "top_artist": top_artist,
    }


async def compute_trends(
    db: AsyncSession, client: SpotifyClient, user_id: int
) -> list[dict]:
    """Calcola i trend confrontando short, medium e long term."""
    trends = []
    for time_range in ["short_term", "medium_term", "long_term"]:
        profile = await compute_profile(db, client, time_range)
        trends.append({
            "period": time_range,
            "label": {
                "short_term": "Ultimo mese",
                "medium_term": "Ultimi 6 mesi",
                "long_term": "Sempre",
            }[time_range],
            **profile,
        })

    return trends


async def save_snapshot(
    db: AsyncSession, user_id: int, period: str, profile: dict
):
    """Salva uno snapshot delle medie per tracking storico (max 1 per giorno/periodo)."""
    from datetime import datetime, timezone

    features = profile.get("features", {})
    genres = profile.get("genres", {})
    today = datetime.now(timezone.utc).date()

    # Check if snapshot already exists for this user/period/day
    from sqlalchemy import func
    result = await db.execute(
        select(ListeningSnapshot).where(
            ListeningSnapshot.user_id == user_id,
            ListeningSnapshot.period == period,
            func.date(ListeningSnapshot.snapshot_date) == today,
        )
    )
    existing = result.scalar_one_or_none()

    if existing:
        # Update existing snapshot
        existing.avg_energy = features.get("energy")
        existing.avg_valence = features.get("valence")
        existing.avg_danceability = features.get("danceability")
        existing.avg_acousticness = features.get("acousticness")
        existing.avg_instrumentalness = features.get("instrumentalness")
        existing.avg_speechiness = features.get("speechiness")
        existing.avg_liveness = features.get("liveness")
        existing.avg_tempo = features.get("tempo")
        existing.top_genre = max(genres, key=genres.get) if genres else None
        existing.genre_distribution = json.dumps(genres) if genres else None
        existing.track_count = profile.get("track_count", 0)
    else:
        snapshot = ListeningSnapshot(
            user_id=user_id,
            period=period,
            avg_energy=features.get("energy"),
            avg_valence=features.get("valence"),
            avg_danceability=features.get("danceability"),
            avg_acousticness=features.get("acousticness"),
            avg_instrumentalness=features.get("instrumentalness"),
            avg_speechiness=features.get("speechiness"),
            avg_liveness=features.get("liveness"),
            avg_tempo=features.get("tempo"),
            top_genre=max(genres, key=genres.get) if genres else None,
            genre_distribution=json.dumps(genres) if genres else None,
            track_count=profile.get("track_count", 0),
        )
        db.add(snapshot)
    await db.commit()


async def get_historical_snapshots(
    db: AsyncSession, user_id: int
) -> list[dict]:
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


async def _extract_genres(client: SpotifyClient, tracks: list[dict]) -> dict[str, float]:
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
    artist_list = list(artist_ids)[:15]  # cap to limit API calls (reduced for dev mode rate limits)
    sem = asyncio.Semaphore(2)

    async def _fetch_genres(aid: str) -> list[str]:
        async with sem:
            try:
                artist = await retry_with_backoff(client.get_artist, aid)
                return artist.get("genres", [])
            except Exception:
                return []

    results = await asyncio.gather(
        *[_fetch_genres(aid) for aid in artist_list],
        return_exceptions=True,
    )
    for r in results:
        if isinstance(r, list):
            all_genres.extend(r)

    if not all_genres:
        return {}

    counter = Counter(all_genres)
    total = sum(counter.values())
    return {
        genre: round(count / total * 100, 1)
        for genre, count in counter.most_common(15)
    }


async def get_or_fetch_features(
    db: AsyncSession, client: SpotifyClient, track_ids: list[str]
) -> dict[str, dict]:
    """Recupera audio features dalla cache o da Spotify API."""
    if not track_ids:
        return {}

    # Cerca nella cache
    result = await db.execute(
        select(AudioFeatures).where(AudioFeatures.track_spotify_id.in_(track_ids))
    )
    cached = {f.track_spotify_id: f for f in result.scalars().all()}

    # Identifica ID mancanti
    missing = [tid for tid in track_ids if tid not in cached]

    # Fetch da Spotify in batch da 100
    if missing:
        for i in range(0, len(missing), 100):
            batch = missing[i : i + 100]
            try:
                resp = await retry_with_backoff(client.get_audio_features, batch)
                for feat in resp.get("audio_features", []):
                    if not feat:
                        continue
                    af = AudioFeatures(
                        track_spotify_id=feat["id"],
                        danceability=feat.get("danceability"),
                        energy=feat.get("energy"),
                        valence=feat.get("valence"),
                        acousticness=feat.get("acousticness"),
                        instrumentalness=feat.get("instrumentalness"),
                        liveness=feat.get("liveness"),
                        speechiness=feat.get("speechiness"),
                        tempo=feat.get("tempo"),
                        loudness=feat.get("loudness"),
                        key=feat.get("key"),
                        mode=feat.get("mode"),
                        time_signature=feat.get("time_signature"),
                    )
                    db.add(af)
                    cached[feat["id"]] = af
                await db.commit()
            except Exception as exc:
                logger.warning("Failed to fetch audio features batch %d-%d: %s", i, i + len(batch), exc)

    # Converti in dizionari
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
