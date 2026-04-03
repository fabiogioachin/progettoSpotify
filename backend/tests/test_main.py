"""Tests for rate limit status endpoint, RateLimitHeaderMiddleware, and warmup helpers in main.py.

Covers:
- /api/v1/rate-limit-status includes window_reset_seconds field
- RateLimitHeaderMiddleware injects X-RateLimit-Reset header on /api/ responses
- _needs_musicbrainz_lookup correctly identifies artists needing MusicBrainz data

All rate limit state is now backed by Redis — tests mock SpotifyClient static methods.
"""

from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient


@pytest.fixture
def patched_app():
    """Import app with Redis-backed rate limit methods safely mocked."""
    with (
        patch(
            "app.services.spotify_client.SpotifyClient.get_window_usage",
            new_callable=AsyncMock,
            return_value=(0, 0),
        ),
        patch(
            "app.services.spotify_client.SpotifyClient.get_cooldown_remaining",
            new_callable=AsyncMock,
            return_value=0,
        ),
    ):
        from app.main import app

        yield app


class TestRateLimitHeaderMiddleware:
    """Tests for X-RateLimit-Reset header injection."""

    @pytest.mark.asyncio
    async def test_api_response_includes_ratelimit_reset_header(self, patched_app):
        """Every /api/ response must include X-RateLimit-Reset header."""
        transport = ASGITransport(app=patched_app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            response = await ac.get("/api/v1/rate-limit-status")

        assert "x-ratelimit-reset" in response.headers, (
            "Response must include X-RateLimit-Reset header"
        )
        # Value should be a parseable float
        reset_val = float(response.headers["x-ratelimit-reset"])
        assert reset_val >= 0

    @pytest.mark.asyncio
    async def test_api_response_includes_ratelimit_usage_header(self, patched_app):
        """Every /api/ response must include X-RateLimit-Usage header."""
        transport = ASGITransport(app=patched_app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            response = await ac.get("/api/v1/rate-limit-status")

        assert "x-ratelimit-usage" in response.headers, (
            "Response must include X-RateLimit-Usage header"
        )

    @pytest.mark.asyncio
    async def test_health_endpoint_no_ratelimit_headers(self, patched_app):
        """/health is not under /api/ so should not get rate limit headers."""
        transport = ASGITransport(app=patched_app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            response = await ac.get("/health")

        # /health is not an /api/ path, so no X-RateLimit-Reset
        assert "x-ratelimit-reset" not in response.headers


class TestNeedsMusicbrainzLookup:
    """Tests for _needs_musicbrainz_lookup helper in main.py."""

    def test_none_needs_lookup(self):
        from app.main import _needs_musicbrainz_lookup

        assert _needs_musicbrainz_lookup(None) is True

    def test_empty_string_needs_lookup(self):
        from app.main import _needs_musicbrainz_lookup

        assert _needs_musicbrainz_lookup("") is True

    def test_empty_json_list_needs_lookup(self):
        from app.main import _needs_musicbrainz_lookup

        assert _needs_musicbrainz_lookup("[]") is True

    def test_null_string_needs_lookup(self):
        from app.main import _needs_musicbrainz_lookup

        assert _needs_musicbrainz_lookup("null") is True

    def test_none_string_needs_lookup(self):
        from app.main import _needs_musicbrainz_lookup

        assert _needs_musicbrainz_lookup("None") is True

    def test_only_non_genre_tags_needs_lookup(self):
        """Genres like ['italian'] that are all in the blocklist need re-lookup."""
        from app.main import _needs_musicbrainz_lookup

        assert _needs_musicbrainz_lookup('["italian"]') is True
        assert _needs_musicbrainz_lookup('["italian", "composer"]') is True
        assert _needs_musicbrainz_lookup('["2010s", "seen live"]') is True

    def test_valid_genres_do_not_need_lookup(self):
        from app.main import _needs_musicbrainz_lookup

        assert _needs_musicbrainz_lookup('["rock", "pop"]') is False
        assert _needs_musicbrainz_lookup('["classical", "piano"]') is False

    def test_mixed_valid_and_bad_tags_do_not_need_lookup(self):
        """If at least one valid genre remains after filtering, no re-lookup needed."""
        from app.main import _needs_musicbrainz_lookup

        assert _needs_musicbrainz_lookup('["rock", "italian"]') is False
        assert _needs_musicbrainz_lookup('["trap", "2020s", "seen live"]') is False

    def test_malformed_json_needs_lookup(self):
        from app.main import _needs_musicbrainz_lookup

        assert _needs_musicbrainz_lookup("not json") is True
        assert _needs_musicbrainz_lookup("{bad}") is True


class TestPlaylistNameToGenre:
    """Tests for _playlist_name_to_genre helper in main.py."""

    def test_exact_match(self):
        from app.main import _playlist_name_to_genre

        assert _playlist_name_to_genre("phonk") == "phonk"
        assert _playlist_name_to_genre("Phonk") == "phonk"
        assert _playlist_name_to_genre("DRILL") == "drill"
        assert _playlist_name_to_genre("techno") == "techno"

    def test_partial_match_short_name(self):
        from app.main import _playlist_name_to_genre

        # "Chill house" contains "chill" and "house", both keywords, and len < 30
        result = _playlist_name_to_genre("Chill house")
        assert result == "chill house"

    def test_non_genre_returns_none(self):
        from app.main import _playlist_name_to_genre

        assert _playlist_name_to_genre("GOLD TIMES") is None
        assert _playlist_name_to_genre("USA") is None
        assert _playlist_name_to_genre("My Favorites 2025") is None

    def test_long_name_no_partial_match(self):
        from app.main import _playlist_name_to_genre

        # Name > 30 chars should not match even if it contains a keyword
        long_name = "My very long playlist name with some chill vibes"
        assert _playlist_name_to_genre(long_name) is None

    def test_whitespace_handling(self):
        from app.main import _playlist_name_to_genre

        assert _playlist_name_to_genre("  phonk  ") == "phonk"
        assert _playlist_name_to_genre("  Trap  ") == "trap"

    def test_italian_specific_keywords(self):
        """Mapped keywords return canonical genres, not raw playlist names."""
        from app.main import _playlist_name_to_genre

        # These are in _PLAYLIST_GENRE_MAP — return canonical genre
        assert _playlist_name_to_genre("cassa dritta") == "techno"
        assert _playlist_name_to_genre("Hi Tech") == "techno"
        assert _playlist_name_to_genre("DRIP") == "trap"

    def test_empty_string_returns_none(self):
        from app.main import _playlist_name_to_genre

        assert _playlist_name_to_genre("") is None

    def test_playlist_genre_map_exact_match(self):
        """_PLAYLIST_GENRE_MAP entries are matched exactly (case-insensitive)."""
        from app.main import _playlist_name_to_genre

        assert _playlist_name_to_genre("afrodisiaco") == "reggaeton"
        assert _playlist_name_to_genre("Bebecita") == "reggaeton"
        assert _playlist_name_to_genre("PERREO") == "reggaeton"
        assert _playlist_name_to_genre("neomelodico") == "neomelodico"
        assert _playlist_name_to_genre("cantautorato") == "cantautorato italiano"
        assert _playlist_name_to_genre("trap italiana") == "italian trap"
        assert _playlist_name_to_genre("rap italiano") == "italian hip hop"
        assert _playlist_name_to_genre("musica italiana") == "italian pop"
        assert _playlist_name_to_genre("banger") == "edm"
        assert _playlist_name_to_genre("peaktime") == "peak time techno"
        assert _playlist_name_to_genre("afro") == "afrobeats"
        assert _playlist_name_to_genre("afrohouse") == "afro house"
        assert _playlist_name_to_genre("Chill House") == "chill house"
        assert _playlist_name_to_genre("backup gold") == "hip hop"
        assert _playlist_name_to_genre("tek") == "techno"

    def test_map_takes_priority_over_keywords(self):
        """When a name is in both map and keywords, the map's canonical genre wins."""
        from app.main import _playlist_name_to_genre

        # "drip" is in keywords AND map; map should win → "trap" not "drip"
        assert _playlist_name_to_genre("drip") == "trap"
        # "tek" is in keywords AND map; map should win → "techno" not "tek"
        assert _playlist_name_to_genre("tek") == "techno"

    def test_new_keywords_substring_match(self):
        """Newly added keywords work with substring matching."""
        from app.main import _playlist_name_to_genre

        assert _playlist_name_to_genre("afrobeats") == "afrobeats"
        assert _playlist_name_to_genre("afro house") == "afro house"
        assert _playlist_name_to_genre("neomelodico") == "neomelodico"
        assert _playlist_name_to_genre("peak time") == "peak time"
        assert _playlist_name_to_genre("lofi") == "lofi"
        assert _playlist_name_to_genre("lo-fi") == "lo-fi"
