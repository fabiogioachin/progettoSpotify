"""FastAPI application entry point."""

import asyncio
import logging
import os
from contextlib import asynccontextmanager

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse, RedirectResponse

from app.config import settings
from app.database import async_session
from app.services.redis_client import close_redis, redis_ping
from app.routers import (
    admin,
    analysis,
    analytics,
    artist_network,
    auth,
    export,
    historical,
    library,
    playlist_analytics,
    playlists,
    privacy,
    profile,
    social,
    taste_evolution,
    temporal,
    wrapped,
)
from app.services.background_tasks import (
    compute_daily_aggregates,
    sync_recent_plays,
    _sync_user_recent_plays,
)
from app.services.data_retention import cleanup_expired_data
from app.services.spotify_client import SpotifyClient
from app.utils.rate_limiter import (
    APIRateLimiter,
    RateLimitError,
    SpotifyAuthError,
    SpotifyServerError,
    ThrottleError,
)

from app.middleware.request_context import (
    RequestContextFilter,
    RequestContextMiddleware,
)
from app.middleware.user_quota import UserQuotaMiddleware

# --- Structured logging setup ---
_root_logger = logging.getLogger()
_root_logger.setLevel(logging.INFO)

_context_filter = RequestContextFilter()

if settings.environment != "development":
    from pythonjsonlogger.json import JsonFormatter

    _json_formatter = JsonFormatter(
        fmt="%(asctime)s %(levelname)s %(name)s %(message)s %(request_id)s %(user_id)s",
        datefmt="%Y-%m-%dT%H:%M:%S%z",
        rename_fields={"asctime": "timestamp", "levelname": "level", "name": "logger"},
    )
    _handler = logging.StreamHandler()
    _handler.setFormatter(_json_formatter)
    _handler.addFilter(_context_filter)
    _root_logger.addHandler(_handler)
else:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    for h in _root_logger.handlers:
        h.addFilter(_context_filter)

logger = logging.getLogger(__name__)

scheduler = AsyncIOScheduler()


async def _warmup_genre_cache():
    """Fill artist_genres cache for known artists at low rate (P2_BATCH).

    Runs after startup sync completes. Collects all artist IDs from
    top_artists across all users and time ranges, then fills missing
    genre cache entries one-by-one with 3s delay between calls.
    """
    await asyncio.sleep(15)  # Let startup sync finish

    from datetime import timedelta

    from sqlalchemy import select

    from app.models.track import ArtistGenre
    from app.models.user import User
    from app.services.api_budget import Priority
    from app.services.genre_cache import get_artist_genres_cached

    try:
        async with async_session() as db:
            result = await db.execute(select(User.id))
            user_ids = [row[0] for row in result.fetchall()]

        if not user_ids:
            return

        # Collect artist IDs from top_artists (already cached from startup sync)
        all_artist_ids: set[str] = set()
        for uid in user_ids:
            async with async_session() as db:
                client = SpotifyClient(db, uid, priority=Priority.P2_BATCH)
                try:
                    for tr in ["short_term", "medium_term", "long_term"]:
                        try:
                            from app.utils.rate_limiter import retry_with_backoff as _rb

                            data = await _rb(client.get_top_artists, time_range=tr)
                            for artist in data.get("items", []):
                                if artist.get("id"):
                                    all_artist_ids.add(artist["id"])
                        except Exception:
                            pass
                finally:
                    await client.close()

        if not all_artist_ids:
            logger.info("Genre warmup: nessun artista da cachare")
            return

        # Check which are NOT already cached in DB (within TTL)
        async with async_session() as db:
            from datetime import datetime, timezone

            cutoff = datetime.now(timezone.utc) - timedelta(days=7)
            result = await db.execute(
                select(ArtistGenre.artist_spotify_id).where(
                    ArtistGenre.artist_spotify_id.in_(list(all_artist_ids)),
                    ArtistGenre.cached_at > cutoff,
                )
            )
            cached = {row[0] for row in result.fetchall()}

        missing = list(all_artist_ids - cached)
        if not missing:
            logger.info(
                "Genre warmup Spotify: tutti gli artisti gia' in cache (%d)",
                len(all_artist_ids),
            )
            # Still run MusicBrainz pass for cached artists with empty genres
            await _warmup_musicbrainz_pass(all_artist_ids)
            # Phase 3: Playlist-inferred genres for remaining genreless artists
            await _warmup_playlist_inferred_genres(user_ids, all_artist_ids)
            return

        logger.info(
            "Genre warmup: %d artisti da cachare (su %d totali)",
            len(missing),
            len(all_artist_ids),
        )

        # Fetch sequentially, 1 every 3 seconds
        for i, artist_id in enumerate(missing):
            try:
                async with async_session() as db:
                    client = SpotifyClient(db, user_ids[0], priority=Priority.P2_BATCH)
                    try:
                        await get_artist_genres_cached(db, client, [artist_id])
                    finally:
                        await client.close()
                if (i + 1) % 10 == 0:
                    logger.info("Genre warmup: %d/%d artisti", i + 1, len(missing))
            except (RateLimitError, ThrottleError):
                logger.info(
                    "Genre warmup: rate limited at %d/%d, stopping",
                    i + 1,
                    len(missing),
                )
                break
            except Exception as exc:
                logger.warning("Genre warmup failed for %s: %s", artist_id, exc)
            await asyncio.sleep(3)

        processed = min(i + 1, len(missing)) if missing else 0
        logger.info(
            "Genre warmup Spotify completato: %d artisti processati",
            processed,
        )

        # Phase 2: MusicBrainz fallback for artists still without genres
        await _warmup_musicbrainz_pass(all_artist_ids)

        # Phase 3: Playlist-inferred genres for remaining genreless artists
        await _warmup_playlist_inferred_genres(user_ids, all_artist_ids)
    except Exception as exc:
        logger.warning("Genre warmup fallito: %s", exc)


def _needs_musicbrainz_lookup(genres_str: str | None) -> bool:
    """Return True if the genres column value has no useful genre data.

    Matches:
    - NULL / empty string / "null" / "None" / "[]"
    - JSON list that is empty after filtering non-genre tags
    """
    if not genres_str:
        return True
    stripped = genres_str.strip()
    if stripped in ("[]", "null", "", "None"):
        return True
    # Check if stored genres contain ONLY non-genre tags (e.g. ["italian"])
    try:
        import json as _json

        from app.services.musicbrainz_client import filter_non_genre_tags

        parsed = _json.loads(stripped)
        if isinstance(parsed, list):
            filtered = filter_non_genre_tags(parsed)
            return len(filtered) == 0
    except Exception:
        return True
    return False


async def _warmup_musicbrainz_pass(all_artist_ids: set[str]) -> None:
    """MusicBrainz fallback: enrich artists with empty or bad-tag-only genres.

    Runs after Spotify genre warmup. Fetches ALL artist_genres rows for the
    given artist IDs, then filters in Python for those that need a lookup
    (empty genres, or genres consisting only of non-genre tags like "italian").
    Queries MusicBrainz one-by-one at 1 req/s rate. Updates DB only when
    MusicBrainz returns valid genre results.
    """
    import json
    from datetime import datetime, timezone

    from sqlalchemy import select
    from sqlalchemy.dialects.postgresql import insert as pg_insert

    from app.models.track import ArtistGenre
    from app.services.musicbrainz_client import search_artist_genres

    try:
        # Fetch ALL rows for these artist IDs and filter in Python
        async with async_session() as db:
            result = await db.execute(
                select(
                    ArtistGenre.artist_spotify_id,
                    ArtistGenre.artist_name,
                    ArtistGenre.genres,
                ).where(
                    ArtistGenre.artist_spotify_id.in_(list(all_artist_ids)),
                )
            )
            all_rows = result.fetchall()

        # Filter for artists that need MusicBrainz lookup
        empty_genre_artists = [
            (row[0], row[1])
            for row in all_rows
            if row[1] and _needs_musicbrainz_lookup(row[2])
        ]

        if not empty_genre_artists:
            logger.info(
                "Genre warmup MusicBrainz: tutti gli artisti hanno gia' generi validi"
            )
            return

        logger.info(
            "Genre warmup MusicBrainz: %d artisti senza generi validi (su %d totali)",
            len(empty_genre_artists),
            len(all_rows),
        )

        mb_found = 0
        for i, (aid, name) in enumerate(empty_genre_artists):
            try:
                mb_genres = await search_artist_genres(name)
                if mb_genres:
                    mb_found += 1
                    async with async_session() as db:
                        now = datetime.now(timezone.utc)
                        stmt = (
                            pg_insert(ArtistGenre)
                            .values(
                                artist_spotify_id=aid,
                                artist_name=name,
                                genres=json.dumps(mb_genres),
                                cached_at=now,
                            )
                            .on_conflict_do_update(
                                index_elements=["artist_spotify_id"],
                                set_={
                                    "genres": json.dumps(mb_genres),
                                    "cached_at": now,
                                },
                            )
                        )
                        await db.execute(stmt)
                        await db.commit()
            except Exception as exc:
                logger.warning("MusicBrainz warmup failed for %s: %s", name, exc)

            if (i + 1) % 10 == 0:
                logger.info(
                    "Genre warmup MusicBrainz: %d/%d artisti (%d trovati)",
                    i + 1,
                    len(empty_genre_artists),
                    mb_found,
                )

        logger.info(
            "Genre warmup MusicBrainz completato: %d/%d artisti arricchiti",
            mb_found,
            len(empty_genre_artists),
        )
    except Exception as exc:
        logger.warning("Genre warmup MusicBrainz fallito: %s", exc)


# --- Phase 3: Playlist-inferred genres ---

_GENRE_PLAYLIST_KEYWORDS: set[str] = {
    "phonk",
    "drill",
    "tek",
    "techno",
    "house",
    "cassa dritta",
    "funk",
    "trap",
    "hip hop",
    "rap",
    "rock",
    "pop",
    "r&b",
    "reggaeton",
    "afrobeat",
    "afrobeats",
    "afro house",
    "dance",
    "edm",
    "dubstep",
    "dnb",
    "drum and bass",
    "chill",
    "lo-fi",
    "lofi",
    "jazz",
    "soul",
    "gospel",
    "metal",
    "punk",
    "indie",
    "alternative",
    "classical",
    "electronic",
    "ambient",
    "trance",
    "psytrance",
    "minimal",
    "deep house",
    "tech house",
    "bass",
    "grime",
    "garage",
    "uk garage",
    "reggae",
    "dancehall",
    "latin",
    "salsa",
    "bachata",
    "cumbia",
    "disco",
    "synthwave",
    "new wave",
    "post-punk",
    "shoegaze",
    "grunge",
    "emo",
    "hardcore",
    "breakbeat",
    "jungle",
    "dub",
    "ska",
    "blues",
    "country",
    "folk",
    "neomelodico",
    "cantautorato",
    "peak time",
    "peaktime",
    # Italian / niche
    "hi tech",
    "drip",
}

# Map slang/Italian playlist names to canonical genre strings.
# Checked FIRST (exact match on lowered name) before keyword substring matching.
_PLAYLIST_GENRE_MAP: dict[str, str] = {
    # Italian genre names
    "afrodisiaco": "reggaeton",
    "bebecita": "reggaeton",
    "perreo": "reggaeton",
    "neomelodico": "neomelodico",
    "cantautorato": "cantautorato italiano",
    "trap italiana": "italian trap",
    "rap italiano": "italian hip hop",
    "musica italiana": "italian pop",
    # Slang/mood-based that imply genres
    "drip": "trap",
    "hi tech": "techno",
    "cassa dritta": "techno",
    "tek": "techno",
    "banger": "edm",
    "peaktime": "peak time techno",
    "afro": "afrobeats",
    "afrohouse": "afro house",
    "chill house": "chill house",
    "backup gold": "hip hop",
}


def _playlist_name_to_genre(name: str) -> str | None:
    """Return genre string if playlist name looks like a genre, else None.

    Checks ``_PLAYLIST_GENRE_MAP`` first (exact match on lowered name) so that
    slang/Italian playlist names map to canonical genre strings.  Falls back to
    ``_GENRE_PLAYLIST_KEYWORDS`` for exact and substring matching.
    """
    lower = name.lower().strip()
    # 1. Exact map lookup → canonical genre (not the playlist name)
    mapped = _PLAYLIST_GENRE_MAP.get(lower)
    if mapped is not None:
        return mapped
    # 2. Exact keyword match
    if lower in _GENRE_PLAYLIST_KEYWORDS:
        return lower
    # 3. Partial match: "Chill house" -> "chill house" (short name = likely a genre)
    for keyword in _GENRE_PLAYLIST_KEYWORDS:
        if keyword in lower and len(lower) < 30:
            return lower
    return None


async def _warmup_playlist_inferred_genres(
    user_ids: list[int], all_artist_ids: set[str]
) -> None:
    """Phase 3: Infer genres from playlist names for remaining genreless artists.

    For each user, fetches their playlists (1 API call, cached). For playlists
    whose name matches a known genre keyword, fetches items (1 call each, cached).
    Builds artist -> {playlist_genres} mapping, then upserts only for artists
    that still have empty genres after Spotify + MusicBrainz passes.

    Uses retry-with-wait on throttle (max 3 attempts per playlist) and a total
    time budget of 5 minutes to prevent infinite warmup.
    """
    import json
    import time
    from datetime import datetime, timezone

    from sqlalchemy import select
    from sqlalchemy.dialects.postgresql import insert as pg_insert

    from app.models.track import ArtistGenre
    from app.services.api_budget import Priority
    from app.utils.rate_limiter import retry_with_backoff

    _PHASE3_TIME_BUDGET = 5 * 60  # 5 minutes
    _MAX_RETRY_PER_PLAYLIST = 3
    _MAX_WAIT_SECS = 35

    phase3_start = time.monotonic()

    def _time_budget_exceeded() -> bool:
        return (time.monotonic() - phase3_start) >= _PHASE3_TIME_BUDGET

    try:
        total_playlists = 0
        completed_playlists = 0
        total_updated = 0

        for uid in user_ids:
            if _time_budget_exceeded():
                logger.info(
                    "Playlist inference: tempo esaurito (5min budget), "
                    "completate %d/%d playlist, %d artisti arricchiti",
                    completed_playlists,
                    total_playlists,
                    total_updated,
                )
                break

            async with async_session() as db:
                client = SpotifyClient(db, uid, priority=Priority.P2_BATCH)
                try:
                    # Get playlists (cached in Redis, 1 API call)
                    playlists_data = await retry_with_backoff(
                        client.get_playlists, limit=50
                    )
                    playlists = playlists_data.get("items", [])

                    # Map genre-like playlists
                    genre_playlists: list[tuple[str, str]] = []
                    for p in playlists:
                        genre = _playlist_name_to_genre(p.get("name", ""))
                        if genre:
                            genre_playlists.append((p["id"], genre))

                    if not genre_playlists:
                        continue

                    total_playlists += len(genre_playlists)

                    logger.info(
                        "Playlist genre inference: %d playlist-genere per user_id=%d",
                        len(genre_playlists),
                        uid,
                    )

                    # For each genre playlist, get items (cached) with retry
                    artist_genres_map: dict[str, set[str]] = {}
                    artist_names: dict[str, str] = {}

                    for pid, genre in genre_playlists:
                        if _time_budget_exceeded():
                            break

                        fetched = False
                        for attempt in range(_MAX_RETRY_PER_PLAYLIST):
                            try:
                                items_data = await retry_with_backoff(
                                    client.get_playlist_items,
                                    pid,
                                    limit=50,
                                    offset=0,
                                )
                                for item in items_data.get("items", []):
                                    track = item.get("item") or item.get(
                                        "track"
                                    )
                                    if not track:
                                        continue
                                    for artist in track.get("artists", []):
                                        aid = artist.get("id")
                                        if aid:
                                            artist_genres_map.setdefault(
                                                aid, set()
                                            ).add(genre)
                                            if aid not in artist_names:
                                                artist_names[aid] = artist.get(
                                                    "name", ""
                                                )
                                fetched = True
                                completed_playlists += 1
                                break  # success, exit retry loop
                            except (RateLimitError, ThrottleError) as exc:
                                wait = min(
                                    getattr(exc, "retry_after", 10) or 10,
                                    _MAX_WAIT_SECS,
                                )
                                logger.info(
                                    "Playlist inference: throttled on playlist %s "
                                    "(tentativo %d/%d), attendo %ds",
                                    pid,
                                    attempt + 1,
                                    _MAX_RETRY_PER_PLAYLIST,
                                    wait,
                                )
                                await asyncio.sleep(wait)
                                # Check time budget after sleeping
                                if _time_budget_exceeded():
                                    break
                            except Exception as exc:
                                logger.debug(
                                    "Playlist items fetch failed for %s: %s",
                                    pid,
                                    exc,
                                )
                                break  # non-retryable error, skip playlist

                        if not fetched:
                            logger.debug(
                                "Playlist inference: skipped playlist %s after retries",
                                pid,
                            )

                        await asyncio.sleep(2)

                    if not artist_genres_map:
                        continue

                    # Only update artists that are in our warmup set AND have empty genres
                    relevant_ids = set(artist_genres_map.keys()) & all_artist_ids
                    if not relevant_ids:
                        continue

                    result = await db.execute(
                        select(
                            ArtistGenre.artist_spotify_id, ArtistGenre.genres
                        ).where(
                            ArtistGenre.artist_spotify_id.in_(list(relevant_ids))
                        )
                    )
                    existing = {row[0]: row[1] for row in result.fetchall()}

                    updated = 0
                    for aid in relevant_ids:
                        current = existing.get(aid)
                        # Only update if current genres are empty/missing
                        if not _needs_musicbrainz_lookup(current):
                            continue

                        inferred_genres = artist_genres_map[aid]
                        genres_list = sorted(inferred_genres)
                        now = datetime.now(timezone.utc)
                        stmt = (
                            pg_insert(ArtistGenre)
                            .values(
                                artist_spotify_id=aid,
                                artist_name=artist_names.get(aid, ""),
                                genres=json.dumps(genres_list),
                                cached_at=now,
                            )
                            .on_conflict_do_update(
                                index_elements=["artist_spotify_id"],
                                set_={
                                    "genres": json.dumps(genres_list),
                                    "cached_at": now,
                                },
                            )
                        )
                        await db.execute(stmt)
                        updated += 1

                    if updated:
                        await db.commit()
                        total_updated += updated
                        logger.info(
                            "Playlist inference: %d/%d playlist, "
                            "%d artisti arricchiti per user_id=%d",
                            completed_playlists,
                            total_playlists,
                            updated,
                            uid,
                        )
                finally:
                    await client.close()

        elapsed = time.monotonic() - phase3_start
        logger.info(
            "Playlist inference completato in %.0fs: %d/%d playlist, "
            "%d artisti arricchiti",
            elapsed,
            completed_playlists,
            total_playlists,
            total_updated,
        )
    except Exception as exc:
        logger.warning("Playlist genre inference fallito: %s", exc)


async def _startup_sync_recent_plays():
    """Sync ascolti recenti per tutti gli utenti all'avvio del backend.

    In dev mode il backend non gira 24/7 — al boot pagina all'indietro
    finche' non raggiunge l'ultimo ascolto gia' nel DB (max 20 pagine = 1000 brani
    come safety cap per evitare loop infiniti, anche se Spotify non ne ha cosi' tanti).
    """
    from sqlalchemy import select

    from app.models.user import User
    from app.services.api_budget import Priority

    await asyncio.sleep(5)  # Lascia che il backend si stabilizzi
    try:
        async with async_session() as db:
            result = await db.execute(select(User.id))
            user_ids = [row[0] for row in result.fetchall()]

        if not user_ids:
            return

        logger.info(
            "Startup sync: recupero ascolti recenti per %d utenti (fino a overlap con DB)",
            len(user_ids),
        )

        for uid in user_ids:
            synced = False
            for attempt in range(3):
                try:
                    async with async_session() as db:
                        client = SpotifyClient(
                            db, uid, priority=Priority.P0_INTERACTIVE
                        )
                        try:
                            await _sync_user_recent_plays(
                                db,
                                uid,
                                client,
                                max_pages=20,
                                raise_on_throttle=True,
                            )
                            synced = True
                        finally:
                            await client.close()
                    break
                except (RateLimitError, ThrottleError) as exc:
                    wait = min(getattr(exc, "retry_after", 10) or 10, 35)
                    logger.info(
                        "Startup sync user_id=%d throttled (tentativo %d/3), "
                        "attendo %ds",
                        uid,
                        attempt + 1,
                        wait,
                    )
                    await asyncio.sleep(wait)
                except Exception as exc:
                    logger.warning("Startup sync user_id=%d fallito: %s", uid, exc)
                    break
            await asyncio.sleep(5)  # Stagger tra utenti

        logger.info("Startup sync completato")
    except Exception as exc:
        logger.warning("Startup sync fallito: %s", exc)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Backend avviato — database gestito da Alembic")
    if not settings.cookie_secure and not settings.frontend_url.startswith(
        "http://127"
    ):
        logger.warning(
            "SECURITY: cookie_secure=False su ambiente non-localhost. Impostare COOKIE_SECURE=true in produzione."
        )

    # APScheduler: sync ascolti recenti ogni 30 minuti
    # jitter=60 adds random 0-60s delay to prevent thundering herd on restart
    scheduler.add_job(
        sync_recent_plays,
        trigger=IntervalTrigger(minutes=30),
        id="sync_recent_plays",
        name="Sync ascolti recenti ogni 30 minuti",
        replace_existing=True,
        jitter=60,
    )
    # jitter=300 adds random 0-300s delay to the 02:00 job
    scheduler.add_job(
        compute_daily_aggregates,
        trigger=CronTrigger(hour=2, minute=0),
        id="compute_daily_aggregates",
        name="Calcolo aggregati giornalieri alle 02:00",
        replace_existing=True,
        jitter=300,
    )
    # Monthly cleanup of expired data (1st of month, 03:00)
    scheduler.add_job(
        cleanup_expired_data,
        trigger=CronTrigger(day=1, hour=3, minute=0),
        id="cleanup_expired_data",
        name="Pulizia dati scaduti mensile (1\u00b0 del mese, 03:00)",
        replace_existing=True,
        jitter=600,
    )
    scheduler.start()
    logger.info(
        "APScheduler avviato — sync_recent_plays ogni 30 minuti (jitter=60s), "
        "compute_daily_aggregates alle 02:00 (jitter=300s), "
        "cleanup_expired_data il 1\u00b0 del mese alle 03:00 (jitter=600s)"
    )

    # Startup sync: recupera ascolti recenti per tutti gli utenti (max 3 pagine = 150 brani)
    # Non-blocking: lancia come task asincrono, il backend è già pronto per le request
    asyncio.create_task(_startup_sync_recent_plays())

    # Genre cache warmup: fill artist_genres for known artists (runs after startup sync)
    asyncio.create_task(_warmup_genre_cache())

    yield

    scheduler.shutdown(wait=False)
    logger.info("APScheduler arrestato")
    await close_redis()
    logger.info("Redis chiuso")


class RateLimitHeaderMiddleware(BaseHTTPMiddleware):
    """Inject X-RateLimit-Usage and X-RateLimit-Reset headers into every /api/ response.

    Reads current usage from Redis via SpotifyClient.get_window_usage().
    Uses get_effective_budget() to show the per-user P0 budget instead of the
    raw Spotify throttle limit (25).
    Caches result for 2s to avoid Redis round-trip on every response.
    """

    _cached_usage: tuple[int, float, int] = (0, 0.0, 25)
    _cached_at: float = 0.0
    _CACHE_TTL: float = 2.0

    async def dispatch(self, request, call_next):
        response = await call_next(request)
        if request.url.path.startswith("/api/"):
            import time as _time

            now = _time.monotonic()
            if now - self._cached_at > self._CACHE_TTL:
                current, reset = await SpotifyClient.get_window_usage()
                effective = await SpotifyClient.get_effective_budget()
                RateLimitHeaderMiddleware._cached_usage = (current, reset, effective)
                RateLimitHeaderMiddleware._cached_at = now
            else:
                current, reset, effective = self._cached_usage
            response.headers["X-RateLimit-Usage"] = f"{current}/{effective}"
            response.headers["X-RateLimit-Reset"] = str(reset)
        return response


app = FastAPI(
    title="Wrap",
    description="Dashboard di analisi musicale personale",
    version="1.0.0",
    lifespan=lifespan,
)


@app.exception_handler(SpotifyAuthError)
async def spotify_auth_exception_handler(request, exc: SpotifyAuthError):
    """Token scaduto/corrotto → 401, il frontend redirige al login."""
    logger.warning("SpotifyAuthError: %s", exc)
    return JSONResponse(
        status_code=401,
        content={"detail": "Sessione scaduta"},
    )


@app.exception_handler(RateLimitError)
async def rate_limit_exception_handler(request, exc: RateLimitError):
    """Propaga i 429 di Spotify al frontend con il corretto Retry-After."""
    retry_after = round(exc.retry_after or 5, 1)
    is_throttle = isinstance(exc, ThrottleError)
    logger.warning(
        "Rate limit propagato al frontend: Retry-After=%.0fs, throttled=%s",
        retry_after,
        is_throttle,
    )
    return JSONResponse(
        status_code=429,
        content={
            "detail": {
                "message": f"Troppe richieste. Riprova tra {int(retry_after)} secondi.",
                "throttled": is_throttle,
                "retry_after": retry_after,
            }
        },
        headers={"Retry-After": str(int(retry_after))},
    )


@app.exception_handler(SpotifyServerError)
async def spotify_server_exception_handler(request, exc: SpotifyServerError):
    """Errore transitorio lato Spotify → 502."""
    logger.warning("SpotifyServerError: %s", exc)
    return JSONResponse(
        status_code=502,
        content={"detail": "Spotify non disponibile al momento"},
    )


# Proxy support: trust X-Forwarded-For when behind a reverse proxy
if os.getenv("BEHIND_PROXY", "").lower() == "true":
    from uvicorn.middleware.proxy_headers import ProxyHeadersMiddleware

    app.add_middleware(ProxyHeadersMiddleware, trusted_hosts=["*"])

# Rate Limiter (prima di CORS per intercettare richieste eccessive)
app.add_middleware(APIRateLimiter, requests_per_minute=120)

# CORS (restrict methods and headers to what the app actually uses)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_url],
    allow_credentials=True,
    allow_methods=["GET", "POST", "DELETE"],
    allow_headers=["Content-Type"],
    expose_headers=["X-RateLimit-Usage", "X-RateLimit-Reset"],
)

# Rate limit usage header (runs inside CORS — added after CORSMiddleware)
app.add_middleware(RateLimitHeaderMiddleware)

# Request context (request_id + user_id in logs — runs early, after rate limit headers)
app.add_middleware(RequestContextMiddleware)

# Per-user quota (runs after request context so user_id is available from cookie)
app.add_middleware(UserQuotaMiddleware)

# Routers
app.include_router(auth.router)
app.include_router(analysis.router)
app.include_router(library.router)
app.include_router(playlists.router)
app.include_router(analytics.router)
app.include_router(export.router)
app.include_router(taste_evolution.router)
app.include_router(temporal.router)
app.include_router(artist_network.router)
app.include_router(playlist_analytics.router)
app.include_router(historical.router)
app.include_router(wrapped.router)
app.include_router(profile.router)
app.include_router(social.router)
app.include_router(privacy.router)
app.include_router(admin.router)


@app.get("/health")
async def health():
    """Health check con verifica database e Redis."""
    checks = {"database": "ok", "redis": "ok"}
    try:
        from sqlalchemy import text

        async with async_session() as session:
            await session.execute(text("SELECT 1"))
    except Exception as e:
        checks["database"] = "error"
        logger.error(f"Health check database failed: {e}")

    if not await redis_ping():
        checks["redis"] = "error"

    status = "ok" if all(v == "ok" for v in checks.values()) else "degraded"
    status_code = 200 if status == "ok" else 503
    return JSONResponse(
        content={"status": status, "checks": checks}, status_code=status_code
    )


@app.get("/health/detailed")
async def health_detailed(request: Request):
    """Diagnostica dettagliata — solo admin."""
    from datetime import datetime, timedelta, timezone

    from sqlalchemy import func, select, text

    from app.dependencies import get_session_user_id
    from app.models.user import SpotifyToken, User

    user_id = get_session_user_id(request)
    if not user_id:
        return JSONResponse(status_code=403, content={"detail": "Accesso negato"})

    async with async_session() as session:
        user = (
            await session.execute(select(User).where(User.id == user_id))
        ).scalar_one_or_none()
        if not user or not user.is_admin:
            return JSONResponse(status_code=403, content={"detail": "Accesso negato"})

    # DB ping
    checks: dict[str, str] = {"database": "ok", "redis": "ok"}
    try:
        async with async_session() as session:
            await session.execute(text("SELECT 1"))
    except Exception as e:
        checks["database"] = f"error: {e}"

    # Redis ping
    if not await redis_ping():
        checks["redis"] = "error"

    # Active users (token updated in last 24h)
    try:
        async with async_session() as session:
            cutoff = datetime.now(timezone.utc) - timedelta(hours=24)
            result = await session.execute(
                select(func.count())
                .select_from(SpotifyToken)
                .where(SpotifyToken.updated_at > cutoff)
            )
            active_users = result.scalar() or 0

            total_result = await session.execute(select(func.count()).select_from(User))
            total_users = total_result.scalar() or 0
    except Exception:
        active_users = -1
        total_users = -1

    # APScheduler jobs
    jobs_info = []
    for job in scheduler.get_jobs():
        jobs_info.append(
            {
                "id": job.id,
                "name": job.name,
                "next_run": str(job.next_run_time) if job.next_run_time else None,
            }
        )

    # Spotify reachability (lightweight check)
    spotify_reachable = False
    try:
        import httpx

        async with httpx.AsyncClient(timeout=5.0) as client:
            await client.get("https://api.spotify.com/v1/")
            spotify_reachable = True
    except Exception:
        spotify_reachable = False

    # Rate limit window
    current_calls, window_reset = await SpotifyClient.get_window_usage()
    max_calls = SpotifyClient._MAX_CALLS_PER_WINDOW

    status = "ok" if all(v == "ok" for v in checks.values()) else "degraded"
    return {
        "status": status,
        "checks": checks,
        "users": {"total": total_users, "active_24h": active_users},
        "scheduler": {"jobs": jobs_info},
        "spotify": {"reachable": spotify_reachable},
        "rate_limit": {
            "calls_in_window": current_calls,
            "max_calls": max_calls,
            "window_reset_seconds": window_reset,
        },
    }


@app.middleware("http")
async def api_version_redirect(request, call_next):
    """Redirect vecchi path /api/* a /api/v1/* per backward compatibility (308)."""
    path = request.url.path
    # Only redirect /api/ paths that aren't already /api/v1/
    if path.startswith("/api/") and not path.startswith("/api/v1/"):
        new_path = "/api/v1" + path[4:]  # /api/foo → /api/v1/foo
        query = str(request.url.query)
        url = new_path + ("?" + query if query else "")
        return RedirectResponse(url=url, status_code=308)
    return await call_next(request)
