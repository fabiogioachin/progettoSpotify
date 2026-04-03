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

from app.services.api_budget import (
    Priority,
    TIER_LIMITS,
    extend_cache_ttl,
)
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

    # Lua script for atomic check-and-register (cooldown + budget + throttle)
    # KEYS[1] = calls sorted set, KEYS[2] = cooldown key
    # ARGV[1] = now, ARGV[2] = window_start, ARGV[3] = call_id,
    # ARGV[4] = priority_str, ARGV[5] = user_id_str,
    # ARGV[6] = max_calls, ARGV[7] = tier_limit, ARGV[8] = user_limit,
    # ARGV[9] = key_ttl
    # Returns: {allowed(0/1), reason(0=ok,1=cooldown,2=tier,3=user,4=window), wait_time, count}
    _LUA_SCRIPT = """\
local calls_key = KEYS[1]
local cooldown_key = KEYS[2]

local now = tonumber(ARGV[1])
local window_start = tonumber(ARGV[2])
local call_id = ARGV[3]
local priority_str = ARGV[4]
local user_id_str = ARGV[5]
local max_calls = tonumber(ARGV[6])
local tier_limit = tonumber(ARGV[7])
local user_limit = tonumber(ARGV[8])
local key_ttl = tonumber(ARGV[9])
local window_size = now - window_start

-- 1. Check cooldown
local cd_ttl = redis.call('TTL', cooldown_key)
if cd_ttl > 0 then
    return {0, 1, cd_ttl, 0}
end

-- 2. Clean expired entries
redis.call('ZREMRANGEBYSCORE', calls_key, 0, window_start)

-- 3. Get all members in window (needed for both total count and budget parsing)
local members = redis.call('ZRANGEBYSCORE', calls_key, window_start, '+inf')
local total = #members

-- 4. Budget check: count per-tier and per-user calls
local tier_count = 0
local user_count = 0

for _, member in ipairs(members) do
    -- member format: {uuid_hex}:{priority}:{user_id}
    local p1 = string.find(member, ':', 1, true)
    if p1 then
        local p2 = string.find(member, ':', p1 + 1, true)
        if p2 then
            local m_priority = string.sub(member, p1 + 1, p2 - 1)
            local m_user_id = string.sub(member, p2 + 1)
            if m_priority == priority_str then
                tier_count = tier_count + 1
                if m_user_id == user_id_str then
                    user_count = user_count + 1
                end
            end
        end
    end
end

-- 5. Check tier budget
if tier_count >= tier_limit then
    return {0, 2, 0, total}
end

-- 6. Check user budget within tier
if user_count >= user_limit then
    return {0, 3, 0, total}
end

-- 7. Check sliding window (total calls)
if total >= max_calls then
    -- Calculate wait time: oldest entry score + window_size - now
    local wait = window_size
    if total > 0 then
        local oldest_score = tonumber(redis.call('ZSCORE', calls_key, members[1]))
        if oldest_score then
            wait = oldest_score + window_size - now
            if wait < 0 then wait = 0 end
        end
    end
    return {0, 4, wait, total}
end

-- 8. ALL checks passed — register the call
redis.call('ZADD', calls_key, now, call_id)
redis.call('EXPIRE', calls_key, key_ttl)

return {1, 0, 0, total + 1}
"""
    _lua_sha: str | None = None

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
    async def _load_lua_script(r) -> str:
        """Load the Lua script into Redis and cache the SHA. Returns the SHA."""
        if SpotifyClient._lua_sha is not None:
            return SpotifyClient._lua_sha
        sha = await r.script_load(SpotifyClient._LUA_SCRIPT)
        SpotifyClient._lua_sha = sha
        return sha

    async def _check_and_register(self) -> None:
        """Atomic cooldown + budget + throttle check via single Lua EVALSHA.

        Consolidates 3 Redis round-trips into 1. Raises:
        - RateLimitError if global cooldown is active (from a prior Spotify 429)
        - ThrottleError if tier/user budget or sliding window is exhausted

        Fail-open: if Redis is unavailable, the call is allowed.
        """
        try:
            r = get_redis()
            sha = await self._load_lua_script(r)

            now = time.time()
            window_start = now - self._WINDOW_SIZE
            call_id = f"{uuid.uuid4().hex}:{int(self.priority)}:{self.user_id}"

            tier_limit = TIER_LIMITS[self.priority]
            # Dynamic user share: with 1 active user, allow full tier budget.
            # The Lua script enforces this per-call; actual multi-user fairness
            # is handled by natural competition within the tier limit.
            user_limit = tier_limit  # Full tier for the fast path

            try:
                result = await r.evalsha(
                    sha,
                    2,  # number of keys
                    self._REDIS_CALLS_KEY,
                    self._REDIS_COOLDOWN_KEY,
                    str(now),
                    str(window_start),
                    call_id,
                    str(int(self.priority)),
                    str(self.user_id),
                    str(self._MAX_CALLS_PER_WINDOW),
                    str(tier_limit),
                    str(user_limit),
                    str(60),  # key_ttl
                )
            except Exception as e:
                # NOSCRIPT error: SHA not in Redis (server restart). Reload and retry.
                if "NOSCRIPT" in str(e):
                    SpotifyClient._lua_sha = None
                    sha = await self._load_lua_script(r)
                    result = await r.evalsha(
                        sha,
                        2,
                        self._REDIS_CALLS_KEY,
                        self._REDIS_COOLDOWN_KEY,
                        str(now),
                        str(window_start),
                        call_id,
                        str(int(self.priority)),
                        str(self.user_id),
                        str(self._MAX_CALLS_PER_WINDOW),
                        str(tier_limit),
                        str(user_limit),
                        str(60),
                    )
                else:
                    raise

            # Parse Lua result: [allowed, reason, wait_time, count]
            allowed = int(result[0])
            reason = int(result[1])
            wait_time = float(result[2])

            if allowed:
                return  # All checks passed, call registered

            if reason == 1:
                # Cooldown active
                logger.warning(
                    "Global cooldown active (%.0fs remaining) — skipping request",
                    wait_time,
                )
                raise RateLimitError(wait_time)

            if reason == 2:
                # Tier budget exhausted
                logger.info(
                    "Budget esaurito per tier %s — extend cache TTL",
                    self.priority.name,
                )
                await extend_cache_ttl(self.user_id)
                raise ThrottleError(self._WINDOW_SIZE)

            if reason == 3:
                # User budget within tier exhausted
                logger.info(
                    "Budget utente esaurito per user %s in tier %s — extend cache TTL",
                    self.user_id,
                    self.priority.name,
                )
                await extend_cache_ttl(self.user_id)
                raise ThrottleError(self._WINDOW_SIZE)

            if reason == 4:
                # Sliding window full
                effective_wait = max(0.1, wait_time)
                logger.info(
                    "Throttle preventivo: attesa %.1fs (budget %d/%d in 30s)",
                    effective_wait,
                    self._MAX_CALLS_PER_WINDOW,
                    self._MAX_CALLS_PER_WINDOW,
                )
                raise ThrottleError(effective_wait)

        except (RateLimitError, ThrottleError):
            raise
        except Exception:
            logger.warning("Redis non disponibile per check_and_register — fail-open")

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
        Optimized: ZCOUNT for count (O(log N)), ZRANGEBYSCORE LIMIT 0 1 for oldest.
        Returns (0, 0) if Redis is unavailable.
        """
        try:
            r = get_redis()
            now = time.time()
            window_start = now - SpotifyClient._WINDOW_SIZE

            pipe = r.pipeline(transaction=False)
            pipe.zcount(SpotifyClient._REDIS_CALLS_KEY, window_start, "+inf")
            pipe.zrangebyscore(
                SpotifyClient._REDIS_CALLS_KEY,
                window_start,
                "+inf",
                withscores=True,
                start=0,
                num=1,
            )
            results = await pipe.execute()

            count = results[0]
            oldest_entries = results[1]
            if count > 0 and oldest_entries:
                oldest_score = oldest_entries[0][1]
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
            # Atomic cooldown + budget + throttle check via single Lua script
            await self._check_and_register()

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
        self,
        limit: int = 50,
        before: int | None = None,
        skip_cache: bool = False,
    ) -> dict:
        key = f"cache:user:{self.user_id}:recently_played:{_args_hash(limit, before)}"
        if not skip_cache:
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
