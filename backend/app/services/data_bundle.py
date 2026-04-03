"""Request-scoped data bundle for Spotify API call deduplication.

Created once per request in the router, passed to all services.
Each get_* method calls the Spotify API only on first access,
then serves from in-memory cache for the rest of the request.
"""

import asyncio
import logging

from app.services.spotify_client import SpotifyClient
from app.utils.rate_limiter import retry_with_backoff

logger = logging.getLogger(__name__)


class RequestDataBundle:
    def __init__(self, client: SpotifyClient):
        self.client = client
        self._top_tracks: dict[str, dict] = {}
        self._top_artists: dict[str, dict] = {}
        self._recently_played: dict | None = None
        self._me: dict | None = None

    async def get_top_tracks(
        self, time_range: str = "medium_term", limit: int = 50
    ) -> dict:
        key = f"{time_range}:{limit}"
        if key not in self._top_tracks:
            self._top_tracks[key] = await retry_with_backoff(
                self.client.get_top_tracks, time_range=time_range, limit=limit
            )
        return self._top_tracks[key]

    async def get_top_artists(
        self, time_range: str = "medium_term", limit: int = 50
    ) -> dict:
        key = f"{time_range}:{limit}"
        if key not in self._top_artists:
            self._top_artists[key] = await retry_with_backoff(
                self.client.get_top_artists, time_range=time_range, limit=limit
            )
        return self._top_artists[key]

    async def get_recently_played(self, limit: int = 50) -> dict:
        if self._recently_played is None:
            self._recently_played = await retry_with_backoff(
                self.client.get_recently_played, limit=limit
            )
        return self._recently_played

    async def get_me(self) -> dict:
        if self._me is None:
            self._me = await retry_with_backoff(self.client.get_me)
        return self._me

    async def prefetch(
        self,
        artists: bool = True,
        tracks: bool = True,
        recent: bool = False,
        me: bool = False,
    ):
        """Pre-fetch commonly needed data in parallel.

        Fetches all 3 time_ranges for artists and/or tracks simultaneously,
        reducing total latency vs sequential calls.
        """
        tasks = []
        ranges = ["short_term", "medium_term", "long_term"]

        if artists:
            for tr in ranges:
                tasks.append(self.get_top_artists(time_range=tr))
        if tracks:
            for tr in ranges:
                tasks.append(self.get_top_tracks(time_range=tr))
        if recent:
            tasks.append(self.get_recently_played())
        if me:
            tasks.append(self.get_me())

        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
