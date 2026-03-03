"""Aggregazione e analisi audio features."""

import json
from collections import Counter

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.constants import FEATURE_KEYS
from app.models.listening_history import ListeningSnapshot
from app.routers.library import _get_or_fetch_features
from app.services.spotify_client import SpotifyClient
from app.utils.rate_limiter import retry_with_backoff


async def compute_profile(
    db: AsyncSession, client: SpotifyClient, time_range: str = "medium_term"
) -> dict:
    """Calcola il profilo audio completo dell'utente per un periodo."""
    data = await retry_with_backoff(client.get_top_tracks, time_range=time_range, limit=50)
    items = data.get("items", [])

    if not items:
        return {"features": {}, "genres": {}, "track_count": 0}

    track_ids = [t["id"] for t in items]
    features = await _get_or_fetch_features(db, client, track_ids)

    # Medie features
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
    """Salva uno snapshot delle medie per tracking storico."""
    features = profile.get("features", {})
    genres = profile.get("genres", {})

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

    # Fetch artisti in batch
    all_genres: list[str] = []
    artist_list = list(artist_ids)
    for i in range(0, len(artist_list), 50):
        batch = artist_list[i : i + 50]
        try:
            resp = await retry_with_backoff(client.get_artists, batch)
            for artist in resp.get("artists", []):
                if artist and artist.get("genres"):
                    all_genres.extend(artist["genres"])
        except Exception:
            pass

    if not all_genres:
        return {}

    counter = Counter(all_genres)
    total = sum(counter.values())
    return {
        genre: round(count / total * 100, 1)
        for genre, count in counter.most_common(15)
    }
