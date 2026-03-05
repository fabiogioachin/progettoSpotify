"""Wrapper per Spotify Web API con gestione automatica token refresh e rate limiting."""

import asyncio
from datetime import datetime, timedelta, timezone
from typing import Any

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.user import SpotifyToken
from cryptography.fernet import InvalidToken

from app.utils.rate_limiter import RateLimitError, SpotifyAuthError, SpotifyServerError
from app.utils.token_manager import decrypt_token, encrypt_token

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
        token_record.expires_at = datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(seconds=data["expires_in"])
        token_record.updated_at = datetime.now(timezone.utc).replace(tzinfo=None)
        await self.db.commit()

    async def _request(self, method: str, url: str, **kwargs) -> Any:
        """Esegue una richiesta autenticata alla Spotify API con retry su 401."""
        access_token = await self._get_valid_token()
        headers = {"Authorization": f"Bearer {access_token}"}

        resp = await self._client.request(method, url, headers=headers, **kwargs)

        # Su 401, tenta un refresh forzato e riprova una volta
        if resp.status_code == 401:
            access_token = await self._force_refresh()
            headers = {"Authorization": f"Bearer {access_token}"}
            resp = await self._client.request(method, url, headers=headers, **kwargs)
            if resp.status_code == 401:
                raise SpotifyAuthError("Token non valido dopo refresh")

        if resp.status_code == 429:
            retry_after = float(resp.headers.get("Retry-After", "1"))
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
        return await self.get("/me")

    async def get_top_tracks(self, time_range: str = "medium_term", limit: int = 50) -> dict:
        return await self.get("/me/top/tracks", time_range=time_range, limit=limit)

    async def get_top_artists(self, time_range: str = "medium_term", limit: int = 50) -> dict:
        return await self.get("/me/top/artists", time_range=time_range, limit=limit)

    async def get_recently_played(self, limit: int = 50) -> dict:
        return await self.get("/me/player/recently-played", limit=limit)

    async def get_saved_tracks(self, limit: int = 50, offset: int = 0) -> dict:
        return await self.get("/me/tracks", limit=limit, offset=offset)

    async def get_audio_features(self, track_ids: list[str]) -> dict:
        ids = ",".join(track_ids)
        return await self.get("/audio-features", ids=ids)

    async def get_playlists(self, limit: int = 50, offset: int = 0) -> dict:
        return await self.get("/me/playlists", limit=limit, offset=offset)

    async def get_playlist_tracks(self, playlist_id: str, limit: int = 100, offset: int = 0) -> dict:
        return await self.get(f"/playlists/{playlist_id}/tracks", limit=limit, offset=offset)

    async def get_recommendations(self, seed_tracks: list[str], limit: int = 20, **kwargs) -> dict:
        return await self.get(
            "/recommendations",
            seed_tracks=",".join(seed_tracks[:5]),
            limit=limit,
            **kwargs,
        )

    async def get_artist(self, artist_id: str) -> dict:
        return await self.get(f"/artists/{artist_id}")

    async def get_artists(self, artist_ids: list[str]) -> dict:
        ids = ",".join(artist_ids[:50])
        return await self.get("/artists", ids=ids)

    async def get_related_artists(self, artist_id: str) -> dict:
        return await self.get(f"/artists/{artist_id}/related-artists")

    async def get_artist_top_tracks(self, artist_id: str, market: str = "IT") -> dict:
        return await self.get(f"/artists/{artist_id}/top-tracks", market=market)
