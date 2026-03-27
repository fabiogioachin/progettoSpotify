"""Wrapper per Spotify Web API con gestione automatica token refresh e rate limiting."""

import asyncio
import hashlib
import json
import logging
import re
import time
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.user import SpotifyToken
from app.services.redis_client import get_redis
from cryptography.fernet import InvalidToken

from app.services.api_budget import Priority, check_budget, extend_cache_ttl
from app.utils.rate_limiter import (
    RateLimitError,
    SpotifyAuthError,
    SpotifyServerError,
    ThrottleError,
)
from app.utils.token_manager import decrypt_token, encrypt_token

logger = logging.getLogger(__name__)


def _args_hash(*args, **kwargs) -> str:
    """Deterministic hash of method arguments for cache key construction."""
    raw = json.dumps(
        {"args": list(args), "kwargs": dict(sorted(kwargs.items()))}, default=str
    )
    return hashlib.md5(raw.encode()).hexdigest()[:12]


async def _cache_get(key: str) -> dict | None:
    """Get from Redis, return None on miss or Redis error."""
    try:
        r = get_redis()
        raw = await r.get(key)
        return json.loads(raw) if raw else None
    except Exception:
        return None  # graceful degradation


async def _cache_set(key: str, value: dict, ttl: int):
    """Set in Redis with TTL. Fail silently."""
    try:
        r = get_redis()
        await r.set(key, json.dumps(value, default=str), ex=ttl)
    except Exception:
        logger.debug("Cache write failed for %s", key, exc_info=True)


SPOTIFY_ID_RE = re.compile(r"^[a-zA-Z0-9]{15,25}$")


def _validate_spotify_id(spotify_id: str) -> None:
    if not SPOTIFY_ID_RE.match(spotify_id):
        raise ValueError(f"Invalid Spotify ID: {spotify_id!r}")


SPOTIFY_API = "https://api.spotify.com/v1"
SPOTIFY_TOKEN_URL = "https://accounts.spotify.com/api/token"
SPOTIFY_AUTH_URL = "https://accounts.spotify.com/authorize"

SCOPES = [
    "user-read-recently-played",
    "user-top-read",
    "user-library-read",
    "playlist-read-private",
    "playlist-read-collaborative",
    "user-read-private",
    "user-read-email",
]


class SpotifyClient:
    # Redis keys for distributed rate limiting
    _REDIS_CALLS_KEY = "ratelimit:spotify:calls"
    _REDIS_COOLDOWN_KEY = "ratelimit:spotify:cooldown"

    # Global semaphore — max 3 concurrent Spotify API requests across all instances
    # (dev mode punishes bursts with extreme retry_after values)
    _global_sem = asyncio.Semaphore(3)

    # Sliding window constants
    _WINDOW_SIZE: float = 30.0
    _MAX_CALLS_PER_WINDOW: int = 25

    def __init__(
        self,
        db: AsyncSession,
        user_id: int,
        priority: Priority = Priority.P0_INTERACTIVE,
    ):
        self.db = db
        self.user_id = user_id
        self.priority = priority
        self._client = httpx.AsyncClient(timeout=30.0)
        self._refresh_lock = asyncio.Lock()

    async def close(self):
        await self._client.aclose()

    async def _get_valid_token(self) -> str:
        """Restituisce un access_token valido, facendo refresh se necessario."""
        async with self._refresh_lock:
            result = await self.db.execute(
                select(SpotifyToken).where(SpotifyToken.user_id == self.user_id)
            )
            token_record = result.scalar_one_or_none()
            if not token_record:
                raise SpotifyAuthError("Nessun token trovato per l'utente")

            # Buffer 5 minuti prima della scadenza
            now_utc = datetime.now(timezone.utc)
            if token_record.expires_at <= now_utc + timedelta(minutes=5):
                await self._refresh_token(token_record)

            try:
                return decrypt_token(token_record.access_token_encrypted)
            except InvalidToken:
                raise SpotifyAuthError("Token corrotto — è necessario riautenticarsi")

    async def _refresh_token(self, token_record: SpotifyToken):
        """Rinnova l'access_token usando il refresh_token."""
        try:
            refresh_token = decrypt_token(token_record.refresh_token_encrypted)
        except InvalidToken:
            raise SpotifyAuthError("Token corrotto — è necessario riautenticarsi")

        resp = await self._client.post(
            SPOTIFY_TOKEN_URL,
            data={
                "grant_type": "refresh_token",
                "refresh_token": refresh_token,
                "client_id": settings.spotify_client_id,
                "client_secret": settings.spotify_client_secret,
            },
        )

        if resp.status_code != 200:
            raise SpotifyAuthError(f"Token refresh fallito: {resp.status_code}")

        data = resp.json()
        token_record.access_token_encrypted = encrypt_token(data["access_token"])
        if "refresh_token" in data:
            token_record.refresh_token_encrypted = encrypt_token(data["refresh_token"])
        token_record.expires_at = datetime.now(timezone.utc) + timedelta(
            seconds=data["expires_in"]
        )
        token_record.updated_at = datetime.now(timezone.utc)
        await self.db.commit()

    @staticmethod
    async def _check_cooldown() -> float | None:
        """Check Redis for active cooldown. Returns remaining seconds or None.

        Fail-open: if Redis is down, assume not in cooldown.
        """
        try:
            r = get_redis()
            ttl = await r.ttl(SpotifyClient._REDIS_COOLDOWN_KEY)
            if ttl > 0:
                return float(ttl)
        except Exception:
            logger.warning("Redis non disponibile per cooldown check — fail-open")
        return None

    @staticmethod
    async def _set_cooldown(seconds: float) -> None:
        """Set global cooldown in Redis with TTL."""
        try:
            r = get_redis()
            await r.set(SpotifyClient._REDIS_COOLDOWN_KEY, "1", ex=max(1, int(seconds)))
        except Exception:
            logger.warning("Redis non disponibile per set cooldown — ignorato")

    @staticmethod
    async def _throttle_check_and_register(
        priority: Priority = Priority.P0_INTERACTIVE,
        user_id: int = 0,
    ) -> None:
        """Sliding window check + register via Redis sorted set.

        Member format: {uuid}:{priority}:{user_id} — enables per-tier budget analysis.

        Raises ThrottleError if budget exhausted.
        Fail-open: if Redis is down, allow the call (Spotify's own 429 is the safety net).
        """
        try:
            r = get_redis()
            now = time.time()
            window_start = now - SpotifyClient._WINDOW_SIZE
            call_id = f"{uuid.uuid4().hex}:{int(priority)}:{user_id}"

            pipe = r.pipeline(transaction=True)
            # Remove expired entries
            pipe.zremrangebyscore(SpotifyClient._REDIS_CALLS_KEY, 0, window_start)
            # Count current calls in window
            pipe.zrangebyscore(SpotifyClient._REDIS_CALLS_KEY, window_start, "+inf")
            # Add this call
            pipe.zadd(SpotifyClient._REDIS_CALLS_KEY, {call_id: now})
            # Safety TTL on the key
            pipe.expire(SpotifyClient._REDIS_CALLS_KEY, 60)
            results = await pipe.execute()

            # results[1] is the list of members in window (before adding current call)
            calls_in_window = results[1]
            if len(calls_in_window) >= SpotifyClient._MAX_CALLS_PER_WINDOW:
                # Remove the call we just added — we're over budget
                try:
                    await r.zrem(SpotifyClient._REDIS_CALLS_KEY, call_id)
                except Exception:
                    pass
                # Calculate wait time from oldest call in window
                oldest_score = await r.zscore(
                    SpotifyClient._REDIS_CALLS_KEY, calls_in_window[0]
                )
                if oldest_score:
                    wait_time = oldest_score + SpotifyClient._WINDOW_SIZE - now
                else:
                    wait_time = SpotifyClient._WINDOW_SIZE
                logger.info(
                    "Throttle preventivo: attesa %.1fs (budget %d/%d in 30s)",
                    wait_time,
                    SpotifyClient._MAX_CALLS_PER_WINDOW,
                    SpotifyClient._MAX_CALLS_PER_WINDOW,
                )
                raise ThrottleError(max(0.1, wait_time))
        except ThrottleError:
            raise
        except Exception:
            logger.warning("Redis non disponibile per throttle check — fail-open")

    @staticmethod
    async def get_window_usage() -> tuple[int, float]:
        """Return (current_call_count, window_reset_seconds) from Redis.

        Used by RateLimitHeaderMiddleware and rate-limit-status endpoint.
        Returns (0, 0) if Redis is unavailable.
        """
        try:
            r = get_redis()
            now = time.time()
            window_start = now - SpotifyClient._WINDOW_SIZE
            members = await r.zrangebyscore(
                SpotifyClient._REDIS_CALLS_KEY,
                window_start,
                "+inf",
                withscores=True,
            )
            count = len(members)
            if count > 0 and members:
                oldest_score = members[0][1]
                reset = max(
                    0, round(oldest_score + SpotifyClient._WINDOW_SIZE - now, 1)
                )
            else:
                reset = 0
            return count, reset
        except Exception:
            return 0, 0

    @staticmethod
    async def get_cooldown_remaining() -> float:
        """Return seconds remaining in cooldown, or 0. Redis-safe."""
        remaining = await SpotifyClient._check_cooldown()
        return remaining if remaining else 0

    async def _request(self, method: str, url: str, **kwargs) -> Any:
        """Esegue una richiesta autenticata alla Spotify API con retry su 401."""
        async with SpotifyClient._global_sem:
            # Global cooldown check via Redis
            cooldown_remaining = await self._check_cooldown()
            if cooldown_remaining is not None:
                logger.warning(
                    "Global cooldown active (%.0fs remaining) — skipping request to %s",
                    cooldown_remaining,
                    url,
                )
                raise RateLimitError(cooldown_remaining)

            # Priority budget check — before consuming a slot in the sliding window
            budget_ok = await check_budget(self.user_id, self.priority)
            if not budget_ok:
                # Extend cache TTLs to reduce future pressure
                await extend_cache_ttl(self.user_id)
                # P0: ThrottleError propagates to frontend (shows throttle banner)
                # P1/P2: caller (background jobs) catches ThrottleError and skips
                raise ThrottleError(self._WINDOW_SIZE)

            # Sliding window throttle via Redis sorted set
            await self._throttle_check_and_register(
                priority=self.priority, user_id=self.user_id
            )

            access_token = await self._get_valid_token()
            headers = {"Authorization": f"Bearer {access_token}"}

            resp = await self._client.request(method, url, headers=headers, **kwargs)

            # Su 401, tenta un refresh forzato e riprova una volta
            if resp.status_code == 401:
                access_token = await self._force_refresh()
                headers = {"Authorization": f"Bearer {access_token}"}
                resp = await self._client.request(
                    method, url, headers=headers, **kwargs
                )
                if resp.status_code == 401:
                    raise SpotifyAuthError("Token non valido dopo refresh")

            if resp.status_code == 429:
                retry_after = float(resp.headers.get("Retry-After", "1"))
                await self._set_cooldown(retry_after)
                if retry_after > 60:
                    logger.warning(
                        "Spotify rate limit con retry_after=%.0fs — cooldown globale per %.0f min",
                        retry_after,
                        retry_after / 60,
                    )
                else:
                    logger.info(
                        "Spotify rate limit con retry_after=%.0fs — cooldown breve",
                        retry_after,
                    )
                raise RateLimitError(retry_after)
            if resp.status_code >= 500:
                raise SpotifyServerError(f"Spotify server error: {resp.status_code}")

            resp.raise_for_status()
            return resp.json()

    async def _force_refresh(self) -> str:
        """Forza il refresh del token ignorando la scadenza. Restituisce il nuovo access_token."""
        async with self._refresh_lock:
            result = await self.db.execute(
                select(SpotifyToken).where(SpotifyToken.user_id == self.user_id)
            )
            token_record = result.scalar_one_or_none()
            if not token_record:
                raise SpotifyAuthError("Nessun token trovato per l'utente")
            await self._refresh_token(token_record)
            try:
                return decrypt_token(token_record.access_token_encrypted)
            except InvalidToken:
                raise SpotifyAuthError("Token corrotto dopo refresh")

    async def get(self, endpoint: str, **params) -> Any:
        url = f"{SPOTIFY_API}{endpoint}"
        return await self._request("GET", url, params=params)

    # ---- Endpoints specifici ----

    async def get_me(self) -> dict:
        key = f"cache:user:{self.user_id}:me:{_args_hash()}"
        cached = await _cache_get(key)
        if cached is not None:
            return cached
        result = await self.get("/me")
        await _cache_set(key, result, 300)
        return result

    async def get_top_tracks(
        self, time_range: str = "medium_term", limit: int = 50
    ) -> dict:
        key = f"cache:user:{self.user_id}:top_tracks:{_args_hash(time_range, limit)}"
        cached = await _cache_get(key)
        if cached is not None:
            return cached
        result = await self.get("/me/top/tracks", time_range=time_range, limit=limit)
        await _cache_set(key, result, 300)
        return result

    async def get_top_artists(
        self, time_range: str = "medium_term", limit: int = 50
    ) -> dict:
        key = f"cache:user:{self.user_id}:top_artists:{_args_hash(time_range, limit)}"
        cached = await _cache_get(key)
        if cached is not None:
            return cached
        result = await self.get("/me/top/artists", time_range=time_range, limit=limit)
        await _cache_set(key, result, 300)
        return result

    async def get_recently_played(
        self, limit: int = 50, before: int | None = None
    ) -> dict:
        key = f"cache:user:{self.user_id}:recently_played:{_args_hash(limit, before)}"
        cached = await _cache_get(key)
        if cached is not None:
            return cached
        params: dict = {"limit": limit}
        if before is not None:
            params["before"] = before
        result = await self.get("/me/player/recently-played", **params)
        await _cache_set(key, result, 120)
        return result

    async def get_saved_tracks(self, limit: int = 50, offset: int = 0) -> dict:
        key = f"cache:user:{self.user_id}:saved_tracks:{_args_hash(limit, offset)}"
        cached = await _cache_get(key)
        if cached is not None:
            return cached
        result = await self.get("/me/tracks", limit=limit, offset=offset)
        await _cache_set(key, result, 300)
        return result

    async def get_playlists(self, limit: int = 50, offset: int = 0) -> dict:
        key = f"cache:user:{self.user_id}:playlists:{_args_hash(limit, offset)}"
        cached = await _cache_get(key)
        if cached is not None:
            return cached
        result = await self.get("/me/playlists", limit=limit, offset=offset)
        await _cache_set(key, result, 300)
        return result

    async def get_playlist_items(
        self, playlist_id: str, limit: int = 50, offset: int = 0
    ) -> dict:
        _validate_spotify_id(playlist_id)
        key = f"cache:user:{self.user_id}:playlist_items:{_args_hash(playlist_id, limit, offset)}"
        cached = await _cache_get(key)
        if cached is not None:
            return cached
        result = await self.get(
            f"/playlists/{playlist_id}/items", limit=limit, offset=offset
        )
        await _cache_set(key, result, 300)
        return result

    async def get_track(self, track_id: str) -> dict:
        _validate_spotify_id(track_id)
        key = f"cache:track:{track_id}"
        cached = await _cache_get(key)
        if cached is not None:
            return cached
        result = await self.get(f"/tracks/{track_id}")
        await _cache_set(key, result, 300)
        return result

    async def get_artist(self, artist_id: str) -> dict:
        _validate_spotify_id(artist_id)
        key = f"cache:artist:{artist_id}"
        cached = await _cache_get(key)
        if cached is not None:
            return cached
        result = await self.get(f"/artists/{artist_id}")
        await _cache_set(key, result, 3600)
        return result
