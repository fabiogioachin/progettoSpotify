"""Background tasks per sync periodico dati Spotify.

Eseguiti da APScheduler nel lifespan di FastAPI.
"""

import asyncio
import json
import logging
from datetime import date, datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import async_session
from app.models.listening_history import RecentPlay, UserSnapshot
from app.models.track import TrackPopularity
from app.models.user import SpotifyToken, User
from app.services.api_budget import Priority
from app.services.genre_cache import get_artist_genres_cached
from app.services.profile_metrics import compute_daily_stats
from app.services.redis_client import get_redis
from app.services.spotify_client import SpotifyClient
from app.utils.rate_limiter import (
    RateLimitError,
    SpotifyAuthError,
    ThrottleError,
    retry_with_backoff,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Skip tracking (Redis)
# ---------------------------------------------------------------------------


async def _mark_skipped(user_id: int):
    """Mark user as skipped for retry in next cycle."""
    try:
        redis = get_redis()
        await redis.set(f"sync:skipped:{user_id}", "1", ex=7200)  # 2h TTL
    except Exception:
        pass


async def _clear_skipped(user_id: int):
    """Clear skip flag after successful sync."""
    try:
        redis = get_redis()
        await redis.delete(f"sync:skipped:{user_id}")
    except Exception:
        pass


# ---------------------------------------------------------------------------
# User prioritization
# ---------------------------------------------------------------------------


async def _get_syncable_users() -> list[int]:
    """Get all user IDs with valid tokens, prioritizing previously skipped ones."""
    async with async_session() as db:
        result = await db.execute(
            select(User.id).join(SpotifyToken, SpotifyToken.user_id == User.id)
        )
        all_ids = [row[0] for row in result.all()]

    # Check Redis for skipped users — prioritize them
    skipped = []
    rest = []
    try:
        redis = get_redis()
        for uid in all_ids:
            if await redis.exists(f"sync:skipped:{uid}"):
                skipped.append(uid)
            else:
                rest.append(uid)
    except Exception:
        return all_ids  # fail-open

    return skipped + rest  # skipped first


# ---------------------------------------------------------------------------
# Single-user sync (with priority + skip tracking)
# ---------------------------------------------------------------------------


async def _sync_single_user(user_id: int):
    """Sync a single user with P2 priority and skip tracking."""
    async with async_session() as db:
        client = SpotifyClient(db, user_id, priority=Priority.P2_BATCH)
        try:
            await _sync_user_recent_plays(db, user_id, client)
            await _clear_skipped(user_id)
        finally:
            await client.close()


# ---------------------------------------------------------------------------
# Main sync orchestrator (staggered)
# ---------------------------------------------------------------------------


async def sync_recent_plays():
    """Sincronizza gli ascolti recenti per tutti gli utenti con token valido.

    Eseguito ogni 60 minuti da APScheduler.
    Users are staggered across ~55 minutes to spread API load.
    """
    logger.info("Background sync: inizio sincronizzazione ascolti recenti")
    synced_count = 0

    user_ids = await _get_syncable_users()
    if not user_ids:
        logger.info("Background sync: nessun utente da sincronizzare")
        return

    # Stagger: distribute users across ~55 minutes (leave 5 min buffer)
    interval = min(55 * 60 / max(len(user_ids), 1), 180)  # max 3 min gap

    for i, user_id in enumerate(user_ids):
        if i > 0:
            await asyncio.sleep(interval)
        try:
            await _sync_single_user(user_id)
            synced_count += 1
        except SpotifyAuthError:
            logger.warning(
                "Background sync: token scaduto/invalido per user_id=%d, skip", user_id
            )
        except (RateLimitError, ThrottleError):
            logger.warning(
                "Background sync: rate limited — interrompo sync, marko user_id=%d come skipped",
                user_id,
            )
            await _mark_skipped(user_id)
            break  # Critical: stop all syncing on rate limit (app-wide)
        except Exception as exc:
            logger.warning("Background sync: errore per user_id=%d: %s", user_id, exc)

    logger.info(
        "Background sync: completato per %d/%d utenti", synced_count, len(user_ids)
    )


# ---------------------------------------------------------------------------
# Per-user sync logic (unchanged, now accepts optional client)
# ---------------------------------------------------------------------------


async def _sync_user_recent_plays(
    db: AsyncSession,
    user_id: int,
    client: SpotifyClient | None = None,
    max_pages: int = 1,
):
    """Sincronizza ascolti recenti per un singolo utente.

    Paginazione con cursore `before` per recuperare piu' di 50 brani.
    max_pages=1 (default, login/hourly) → 50 brani.
    max_pages=3 (startup sync) → fino a 150 brani se il buffer Spotify li ha.
    """
    owns_client = client is None
    if owns_client:
        client = SpotifyClient(db, user_id)
    try:
        # Ultimo ascolto nel DB: se lo incontriamo, smettiamo di paginare
        last_db_result = await db.execute(
            select(func.max(RecentPlay.played_at)).where(
                RecentPlay.user_id == user_id
            )
        )
        last_db_played_at = last_db_result.scalar()

        total_stored = 0
        before_cursor: int | None = None
        all_items: list[dict] = []
        reached_db = False

        for page in range(max_pages):
            if reached_db:
                break
            try:
                data = await retry_with_backoff(
                    client.get_recently_played, limit=50, before=before_cursor
                )
            except (RateLimitError, ThrottleError):
                logger.warning(
                    "Sync user_id=%d: rate limited alla pagina %d, salvo %d items",
                    user_id, page, len(all_items),
                )
                break

            items = data.get("items", [])
            if not items:
                break

            for item in items:
                played_at_str = item.get("played_at")
                if played_at_str and last_db_played_at:
                    dt = datetime.fromisoformat(
                        played_at_str.replace("Z", "+00:00")
                    )
                    if dt <= last_db_played_at:
                        reached_db = True
                        break
                all_items.append(item)

            if reached_db:
                break

            # Cursore per la pagina successiva
            cursors = data.get("cursors") or {}
            before_val = cursors.get("before")
            if not before_val:
                break
            before_cursor = int(before_val)

        for item in all_items:
            played_at_str = item.get("played_at")
            if not played_at_str:
                continue
            dt = datetime.fromisoformat(played_at_str.replace("Z", "+00:00"))
            track = item.get("track", {})
            track_id = track.get("id", "")
            if not track_id:
                continue

            # Check duplicato
            exists = await db.execute(
                select(func.count(RecentPlay.id)).where(
                    RecentPlay.user_id == user_id,
                    RecentPlay.track_spotify_id == track_id,
                    RecentPlay.played_at == dt,
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
                    played_at=dt,
                )
            )
            total_stored += 1

        if total_stored > 0:
            await db.commit()
            logger.info(
                "Background sync: user_id=%d — %d nuovi ascolti salvati (%d pagine)",
                user_id,
                total_stored,
                min(max_pages, len(all_items) // 50 + 1),
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
                pg_insert(TrackPopularity)
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

        # Populate genre cache for artists seen in this batch (non-critical)
        try:
            artist_ids = list(
                {
                    item.get("track", {}).get("artists", [{}])[0].get("id", "")
                    for item in items
                    if item.get("track", {}).get("artists")
                }
                - {""}
            )
            if artist_ids:
                await get_artist_genres_cached(db, client, artist_ids)
                logger.info(
                    "Background sync: user_id=%d — genre cache aggiornata per %d artisti",
                    user_id,
                    len(artist_ids),
                )
        except (SpotifyAuthError, RateLimitError):
            raise
        except Exception as exc:
            logger.warning(
                "Background sync: genre cache non-critical failure user_id=%d: %s",
                user_id,
                exc,
            )
    finally:
        if owns_client:
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
        client = SpotifyClient(db, user_id, priority=Priority.P1_BACKGROUND_SYNC)
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
        except (RateLimitError, ThrottleError):
            logger.warning("Daily snapshot: rate limited per user_id=%d, skip", user_id)
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
