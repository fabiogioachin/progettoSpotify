"""Background tasks per sync periodico dati Spotify.

Eseguiti da APScheduler nel lifespan di FastAPI.
"""

import json
import logging
from datetime import date, datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import async_session
from app.models.listening_history import RecentPlay, UserSnapshot
from app.models.track import TrackPopularity
from app.models.user import SpotifyToken, User
from app.services.profile_metrics import compute_daily_stats
from app.services.spotify_client import SpotifyClient
from app.utils.rate_limiter import RateLimitError, SpotifyAuthError, retry_with_backoff

logger = logging.getLogger(__name__)


async def sync_recent_plays():
    """Sincronizza gli ascolti recenti per tutti gli utenti con token valido.

    Eseguito ogni 60 minuti da APScheduler.
    """
    logger.info("Background sync: inizio sincronizzazione ascolti recenti")
    synced_count = 0

    async with async_session() as db:
        # Trova tutti gli utenti con un token
        result = await db.execute(
            select(User.id).join(SpotifyToken, SpotifyToken.user_id == User.id)
        )
        user_ids = [row[0] for row in result.all()]

    for user_id in user_ids:
        try:
            async with async_session() as db:
                await _sync_user_recent_plays(db, user_id)
                synced_count += 1
        except SpotifyAuthError:
            logger.warning(
                "Background sync: token scaduto/invalido per user_id=%d, skip", user_id
            )
        except RateLimitError as e:
            logger.warning(
                "Background sync: rate limited (retry_after=%s) — interrompo sync per tutti gli utenti rimanenti",
                e.retry_after,
            )
            break
        except Exception as exc:
            logger.error("Background sync: errore per user_id=%d: %s", user_id, exc)

    logger.info(
        "Background sync: completato per %d/%d utenti", synced_count, len(user_ids)
    )


async def _sync_user_recent_plays(db: AsyncSession, user_id: int):
    """Sincronizza ascolti recenti per un singolo utente."""
    client = SpotifyClient(db, user_id)
    try:
        data = await retry_with_backoff(client.get_recently_played, limit=50)
        items = data.get("items", [])

        stored = 0
        for item in items:
            played_at_str = item.get("played_at")
            if not played_at_str:
                continue
            dt = datetime.fromisoformat(played_at_str.replace("Z", "+00:00"))
            dt_naive = dt.replace(tzinfo=None)
            track = item.get("track", {})
            track_id = track.get("id", "")
            if not track_id:
                continue

            # Check duplicato
            exists = await db.execute(
                select(func.count(RecentPlay.id)).where(
                    RecentPlay.user_id == user_id,
                    RecentPlay.track_spotify_id == track_id,
                    RecentPlay.played_at == dt_naive,
                )
            )
            if exists.scalar() > 0:
                continue

            db.add(
                RecentPlay(
                    user_id=user_id,
                    track_spotify_id=track_id,
                    track_name=track.get("name", ""),
                    artist_name=(
                        track.get("artists", [{}])[0].get("name", "")
                        if track.get("artists")
                        else ""
                    ),
                    artist_spotify_id=(
                        track.get("artists", [{}])[0].get("id", "")
                        if track.get("artists")
                        else ""
                    ),
                    duration_ms=track.get("duration_ms", 0),
                    played_at=dt_naive,
                )
            )
            stored += 1

        if stored > 0:
            await db.commit()
            logger.info(
                "Background sync: user_id=%d — %d nuovi ascolti salvati",
                user_id,
                stored,
            )

        # Upsert track popularity from recently-played response (zero extra API calls)
        now_utc = datetime.now(timezone.utc)
        pop_count = 0
        for item in items:
            track = item.get("track", {})
            track_id = track.get("id", "")
            popularity = track.get("popularity")
            if not track_id or popularity is None or popularity == 0:
                continue
            stmt = (
                sqlite_insert(TrackPopularity)
                .values(
                    track_spotify_id=track_id,
                    popularity=popularity,
                    cached_at=now_utc,
                )
                .on_conflict_do_update(
                    index_elements=["track_spotify_id"],
                    set_={
                        "popularity": popularity,
                        "cached_at": now_utc,
                    },
                )
            )
            await db.execute(stmt)
            pop_count += 1
        if pop_count > 0:
            await db.commit()
            logger.info(
                "Background sync: user_id=%d — %d popularity aggiornate",
                user_id,
                pop_count,
            )
    finally:
        await client.close()


async def save_daily_snapshot(user_id: int):
    """Salva snapshot giornaliero al primo login del giorno.

    Chiamato dal router auth/profile. Idempotente: non crea duplicati.
    """
    today = date.today()

    async with async_session() as db:
        # Controlla se esiste già uno snapshot per oggi
        result = await db.execute(
            select(func.count(UserSnapshot.id)).where(
                UserSnapshot.user_id == user_id,
                UserSnapshot.captured_at == today,
            )
        )
        if result.scalar() > 0:
            return  # Già salvato oggi

        # Fetch top artists e top tracks da Spotify
        client = SpotifyClient(db, user_id)
        try:
            top_artists_data = await retry_with_backoff(
                client.get_top_artists, time_range="short_term", limit=50
            )
            top_tracks_data = await retry_with_backoff(
                client.get_top_tracks, time_range="short_term", limit=50
            )

            # Serializza solo i campi essenziali
            artists_summary = [
                {
                    "id": a.get("id"),
                    "name": a.get("name"),
                    "genres": a.get("genres", []),
                    "popularity": a.get("popularity", 0),
                }
                for a in top_artists_data.get("items", [])
            ]
            tracks_summary = [
                {
                    "id": t.get("id"),
                    "name": t.get("name"),
                    "artist": t.get("artists", [{}])[0].get("name", "")
                    if t.get("artists")
                    else "",
                    "popularity": t.get("popularity", 0),
                }
                for t in top_tracks_data.get("items", [])
            ]

            # Conta ascolti accumulati
            plays_count_result = await db.execute(
                select(func.count(RecentPlay.id)).where(RecentPlay.user_id == user_id)
            )
            plays_count = plays_count_result.scalar() or 0

            snapshot = UserSnapshot(
                user_id=user_id,
                captured_at=today,
                top_artists_json=json.dumps(artists_summary, ensure_ascii=False),
                top_tracks_json=json.dumps(tracks_summary, ensure_ascii=False),
                recent_plays_count=plays_count,
            )
            db.add(snapshot)
            await db.commit()
            logger.info("Daily snapshot salvato per user_id=%d", user_id)
        except SpotifyAuthError:
            logger.warning(
                "Daily snapshot: token invalido per user_id=%d, skip", user_id
            )
        except Exception as exc:
            logger.warning("Daily snapshot: errore per user_id=%d: %s", user_id, exc)
            await db.rollback()
        finally:
            await client.close()


async def compute_daily_aggregates():
    """Computa statistiche giornaliere per tutti gli utenti. Eseguito alle 02:00."""
    yesterday = date.today() - timedelta(days=1)
    logger.info("Daily aggregates: calcolo per %s", yesterday)

    async with async_session() as db:
        result = await db.execute(
            select(User.id).join(SpotifyToken, SpotifyToken.user_id == User.id)
        )
        user_ids = [row[0] for row in result.all()]

    computed = 0
    for user_id in user_ids:
        try:
            async with async_session() as db:
                await compute_daily_stats(db, user_id, yesterday)
                computed += 1
        except Exception as exc:
            logger.error("Daily aggregates: errore per user_id=%d: %s", user_id, exc)

    logger.info(
        "Daily aggregates: completato per %d/%d utenti", computed, len(user_ids)
    )
