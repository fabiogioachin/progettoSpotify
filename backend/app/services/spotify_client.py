"""Wrapper per Spotify Web API con gestione automatica token refresh e rate limiting."""

import asyncio
import logging
import re
import time
from collections import deque
from datetime import datetime, timedelta, timezone
from typing import Any

import httpx
from cachetools import TTLCache
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.user import SpotifyToken
from cryptography.fernet import InvalidToken

from app.utils.rate_limiter import (
    RateLimitError,
    SpotifyAuthError,
    SpotifyServerError,
    ThrottleError,
)
from app.utils.token_manager import decrypt_token, encrypt_token

logger = logging.getLogger(__name__)

# Module-level TTL caches for read-only Spotify API responses
_cache_5m = TTLCache(maxsize=256, ttl=300)  # 5 min for most methods
_cache_2m = TTLCache(maxsize=64, ttl=120)  # 2 min for recently played


def _cache_key(user_id, method_name, *args, **kwargs):
    """Create a hashable cache key from user_id, method name, and arguments."""
    return (user_id, method_name, args, tuple(sorted(kwargs.items())))


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
    # Global cooldown shared across all instances — ANY 429 activates cooldown
    # so pending requests in the semaphore don't keep hitting Spotify.
    _cooldown_until: float = 0.0  # monotonic timestamp

    # Global semaphore — max 6 concurrent Spotify API requests across all instances
    _global_sem = asyncio.Semaphore(6)

    # Sliding window throttle — preventive rate limiting
    _call_timestamps: deque = deque()
    _WINDOW_SIZE: float = 30.0
    _MAX_CALLS_PER_WINDOW: int = 25
    _window_lock = asyncio.Lock()

    def __init__(self, db: AsyncSession, user_id: int):
        self.db = db
        self.user_id = user_id
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

            # Buffer 5 minuti prima della scadenza (naive UTC per compatibilità SQLite)
            now_utc = datetime.now(timezone.utc).replace(tzinfo=None)
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
        token_record.expires_at = datetime.now(timezone.utc).replace(
            tzinfo=None
        ) + timedelta(seconds=data["expires_in"])
        token_record.updated_at = datetime.now(timezone.utc).replace(tzinfo=None)
        await self.db.commit()

    async def _request(self, method: str, url: str, **kwargs) -> Any:
        """Esegue una richiesta autenticata alla Spotify API con retry su 401."""
        async with SpotifyClient._global_sem:
            # Global cooldown check — don't hit Spotify if we're in cooldown
            now = time.monotonic()
            if SpotifyClient._cooldown_until > now:
                remaining = SpotifyClient._cooldown_until - now
                logger.warning(
                    "Global cooldown active (%.0fs remaining) — skipping request to %s",
                    remaining,
                    url,
                )
                raise RateLimitError(remaining)

            # Sliding window throttle — preventive rate limiting
            wait_time = 0.0
            async with SpotifyClient._window_lock:
                now_w = time.monotonic()
                while (
                    SpotifyClient._call_timestamps
                    and SpotifyClient._call_timestamps[0]
                    < now_w - SpotifyClient._WINDOW_SIZE
                ):
                    SpotifyClient._call_timestamps.popleft()

                if (
                    len(SpotifyClient._call_timestamps)
                    >= SpotifyClient._MAX_CALLS_PER_WINDOW
                ):
                    oldest = SpotifyClient._call_timestamps[0]
                    wait_time = oldest + SpotifyClient._WINDOW_SIZE - now_w

            if wait_time > 0:
                logger.info(
                    "Throttle preventivo: attesa %.1fs (budget %d/%d in 30s)",
                    wait_time,
                    SpotifyClient._MAX_CALLS_PER_WINDOW,
                    SpotifyClient._MAX_CALLS_PER_WINDOW,
                )
                raise ThrottleError(wait_time)

            # Registra la chiamata nel window
            async with SpotifyClient._window_lock:
                SpotifyClient._call_timestamps.append(time.monotonic())

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
                SpotifyClient._cooldown_until = now + retry_after
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
        key = _cache_key(self.user_id, "me")
        cached = _cache_5m.get(key)
        if cached is not None:
            return cached
        result = await self.get("/me")
        _cache_5m[key] = result
        return result

    async def get_top_tracks(
        self, time_range: str = "medium_term", limit: int = 50
    ) -> dict:
        key = _cache_key(self.user_id, "top_tracks", time_range, limit)
        cached = _cache_5m.get(key)
        if cached is not None:
            return cached
        result = await self.get("/me/top/tracks", time_range=time_range, limit=limit)
        _cache_5m[key] = result
        return result

    async def get_top_artists(
        self, time_range: str = "medium_term", limit: int = 50
    ) -> dict:
        key = _cache_key(self.user_id, "top_artists", time_range, limit)
        cached = _cache_5m.get(key)
        if cached is not None:
            return cached
        result = await self.get("/me/top/artists", time_range=time_range, limit=limit)
        _cache_5m[key] = result
        return result

    async def get_recently_played(self, limit: int = 50) -> dict:
        key = _cache_key(self.user_id, "recently_played", limit)
        cached = _cache_2m.get(key)
        if cached is not None:
            return cached
        result = await self.get("/me/player/recently-played", limit=limit)
        _cache_2m[key] = result
        return result

    async def get_saved_tracks(self, limit: int = 50, offset: int = 0) -> dict:
        return await self.get("/me/tracks", limit=limit, offset=offset)

    async def get_playlists(self, limit: int = 50, offset: int = 0) -> dict:
        key = _cache_key(self.user_id, "playlists", limit, offset)
        cached = _cache_5m.get(key)
        if cached is not None:
            return cached
        result = await self.get("/me/playlists", limit=limit, offset=offset)
        _cache_5m[key] = result
        return result

    async def get_artist(self, artist_id: str) -> dict:
        _validate_spotify_id(artist_id)
        key = _cache_key(self.user_id, "artist", artist_id)
        cached = _cache_5m.get(key)
        if cached is not None:
            return cached
        result = await self.get(f"/artists/{artist_id}")
        _cache_5m[key] = result
        return result
