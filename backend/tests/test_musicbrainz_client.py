"""Tests for musicbrainz_client.py — unit tests mocking httpx.

Covers:
- Successful search with tags in search result
- Successful MBID lookup fallback when search has no tags
- Score threshold filtering (< 90 rejected)
- Empty/missing artist name handling
- 503 rate limit response handling
- HTTP error handling
- Network error handling
- Genre deduplication and cap at 10
"""

from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest


# Reset module-level state between tests
@pytest.fixture(autouse=True)
def _reset_rate_limit():
    """Reset the module-level _last_call_time before each test."""
    import app.services.musicbrainz_client as mb

    mb._last_call_time = 0
    yield


class TestSearchArtistGenres:
    """Tests for search_artist_genres function."""

    @pytest.mark.asyncio
    async def test_returns_tags_from_search_result(self):
        """When search result has tags with score >= 90, return them directly."""
        search_response = MagicMock()
        search_response.status_code = 200
        search_response.raise_for_status = MagicMock()
        search_response.json.return_value = {
            "artists": [
                {
                    "id": "mbid-123",
                    "score": 95,
                    "tags": [
                        {"name": "electronic", "count": 5},
                        {"name": "ambient", "count": 3},
                    ],
                }
            ]
        }

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=search_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("app.services.musicbrainz_client.httpx.AsyncClient", return_value=mock_client):
            from app.services.musicbrainz_client import search_artist_genres

            result = await search_artist_genres("Burial")

        assert result == ["electronic", "ambient"]
        # Should only make 1 request (search), not the MBID lookup
        assert mock_client.get.call_count == 1

    @pytest.mark.asyncio
    async def test_falls_back_to_mbid_lookup_when_no_tags(self):
        """When search has no tags, lookup by MBID for genres + tags."""
        search_response = MagicMock()
        search_response.status_code = 200
        search_response.raise_for_status = MagicMock()
        search_response.json.return_value = {
            "artists": [
                {
                    "id": "mbid-456",
                    "score": 100,
                    "tags": [],
                }
            ]
        }

        lookup_response = MagicMock()
        lookup_response.status_code = 200
        lookup_response.raise_for_status = MagicMock()
        lookup_response.json.return_value = {
            "genres": [{"name": "Hip Hop"}],
            "tags": [
                {"name": "trap", "count": 3},
                {"name": "rap", "count": 1},
                {"name": "ignored", "count": 0},  # count=0, should be excluded
            ],
        }

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(side_effect=[search_response, lookup_response])
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("app.services.musicbrainz_client.httpx.AsyncClient", return_value=mock_client):
            from app.services.musicbrainz_client import search_artist_genres

            result = await search_artist_genres("Travis Scott")

        assert result == ["hip hop", "trap", "rap"]
        assert mock_client.get.call_count == 2

    @pytest.mark.asyncio
    async def test_rejects_low_score_artists(self):
        """Artists with score < 90 should not be matched."""
        search_response = MagicMock()
        search_response.status_code = 200
        search_response.raise_for_status = MagicMock()
        search_response.json.return_value = {
            "artists": [
                {"id": "mbid-789", "score": 60, "tags": [{"name": "rock"}]},
                {"id": "mbid-abc", "score": 45, "tags": [{"name": "pop"}]},
            ]
        }

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=search_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("app.services.musicbrainz_client.httpx.AsyncClient", return_value=mock_client):
            from app.services.musicbrainz_client import search_artist_genres

            result = await search_artist_genres("Obscure Artist 12345")

        assert result == []

    @pytest.mark.asyncio
    async def test_empty_artist_name_returns_empty(self):
        """Empty or whitespace-only artist names return empty list immediately."""
        from app.services.musicbrainz_client import search_artist_genres

        assert await search_artist_genres("") == []
        assert await search_artist_genres("   ") == []
        assert await search_artist_genres(None) == []

    @pytest.mark.asyncio
    async def test_no_artists_in_response(self):
        """When MusicBrainz returns no artists, return empty list."""
        search_response = MagicMock()
        search_response.status_code = 200
        search_response.raise_for_status = MagicMock()
        search_response.json.return_value = {"artists": []}

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=search_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("app.services.musicbrainz_client.httpx.AsyncClient", return_value=mock_client):
            from app.services.musicbrainz_client import search_artist_genres

            result = await search_artist_genres("Non Existent Artist")

        assert result == []

    @pytest.mark.asyncio
    async def test_503_rate_limit_returns_empty(self):
        """MusicBrainz 503 (rate limited) returns empty list gracefully."""
        search_response = MagicMock()
        search_response.status_code = 503

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=search_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("app.services.musicbrainz_client.httpx.AsyncClient", return_value=mock_client):
            from app.services.musicbrainz_client import search_artist_genres

            result = await search_artist_genres("Any Artist")

        assert result == []

    @pytest.mark.asyncio
    async def test_503_on_mbid_lookup_returns_empty(self):
        """If search succeeds but MBID lookup gets 503, return empty."""
        search_response = MagicMock()
        search_response.status_code = 200
        search_response.raise_for_status = MagicMock()
        search_response.json.return_value = {
            "artists": [{"id": "mbid-x", "score": 95, "tags": []}]
        }

        lookup_response = MagicMock()
        lookup_response.status_code = 503

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(side_effect=[search_response, lookup_response])
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("app.services.musicbrainz_client.httpx.AsyncClient", return_value=mock_client):
            from app.services.musicbrainz_client import search_artist_genres

            result = await search_artist_genres("Some Artist")

        assert result == []

    @pytest.mark.asyncio
    async def test_http_error_returns_empty(self):
        """Non-503 HTTP errors return empty list gracefully."""
        search_response = MagicMock()
        search_response.status_code = 500
        search_response.reason_phrase = "Internal Server Error"
        search_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "Server Error",
            request=MagicMock(),
            response=search_response,
        )

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=search_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("app.services.musicbrainz_client.httpx.AsyncClient", return_value=mock_client):
            from app.services.musicbrainz_client import search_artist_genres

            result = await search_artist_genres("Some Artist")

        assert result == []

    @pytest.mark.asyncio
    async def test_network_error_returns_empty(self):
        """Network-level errors return empty list gracefully."""
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(side_effect=httpx.ConnectError("DNS failed"))
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("app.services.musicbrainz_client.httpx.AsyncClient", return_value=mock_client):
            from app.services.musicbrainz_client import search_artist_genres

            result = await search_artist_genres("Some Artist")

        assert result == []

    @pytest.mark.asyncio
    async def test_genres_capped_at_10(self):
        """Result should be capped at 10 genres/tags."""
        search_response = MagicMock()
        search_response.status_code = 200
        search_response.raise_for_status = MagicMock()
        search_response.json.return_value = {
            "artists": [
                {
                    "id": "mbid-many",
                    "score": 100,
                    "tags": [
                        {"name": f"genre-{i}", "count": 1}
                        for i in range(15)
                    ],
                }
            ]
        }

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=search_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("app.services.musicbrainz_client.httpx.AsyncClient", return_value=mock_client):
            from app.services.musicbrainz_client import search_artist_genres

            result = await search_artist_genres("Prolific Artist")

        assert len(result) == 10

    @pytest.mark.asyncio
    async def test_genres_deduplicated(self):
        """Duplicate genre names should be removed."""
        search_response = MagicMock()
        search_response.status_code = 200
        search_response.raise_for_status = MagicMock()
        search_response.json.return_value = {
            "artists": [
                {
                    "id": "mbid-dup",
                    "score": 92,
                    "tags": [
                        {"name": "rock", "count": 5},
                        {"name": "Rock", "count": 3},
                        {"name": "ROCK", "count": 1},
                        {"name": "pop", "count": 2},
                    ],
                }
            ]
        }

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=search_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("app.services.musicbrainz_client.httpx.AsyncClient", return_value=mock_client):
            from app.services.musicbrainz_client import search_artist_genres

            result = await search_artist_genres("Dedup Artist")

        assert result == ["rock", "pop"]

    @pytest.mark.asyncio
    async def test_no_mbid_returns_empty_when_no_tags(self):
        """If search result has no tags and no MBID, return empty."""
        search_response = MagicMock()
        search_response.status_code = 200
        search_response.raise_for_status = MagicMock()
        search_response.json.return_value = {
            "artists": [
                {
                    "score": 95,
                    "tags": [],
                    # no "id" field
                }
            ]
        }

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=search_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("app.services.musicbrainz_client.httpx.AsyncClient", return_value=mock_client):
            from app.services.musicbrainz_client import search_artist_genres

            result = await search_artist_genres("No MBID Artist")

        assert result == []


class TestNonGenreTagFiltering:
    """Tests for _NON_GENRE_TAGS blocklist filtering."""

    @pytest.mark.asyncio
    async def test_filters_nationality_tags_from_search(self):
        """Tags like 'italian', 'english' should be stripped from search results."""
        search_response = MagicMock()
        search_response.status_code = 200
        search_response.raise_for_status = MagicMock()
        search_response.json.return_value = {
            "artists": [
                {
                    "id": "mbid-einaudi",
                    "score": 100,
                    "tags": [
                        {"name": "classical", "count": 10},
                        {"name": "italian", "count": 8},
                        {"name": "piano", "count": 6},
                        {"name": "composer", "count": 4},
                        {"name": "modern classical", "count": 3},
                    ],
                }
            ]
        }

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=search_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("app.services.musicbrainz_client.httpx.AsyncClient", return_value=mock_client):
            from app.services.musicbrainz_client import search_artist_genres

            result = await search_artist_genres("Ludovico Einaudi")

        # "italian" and "composer" should be filtered out
        assert "italian" not in result
        assert "composer" not in result
        assert "classical" in result
        assert "piano" in result
        assert "modern classical" in result

    @pytest.mark.asyncio
    async def test_filters_nationality_tags_from_mbid_lookup(self):
        """Non-genre tags should be filtered from MBID lookup results too."""
        search_response = MagicMock()
        search_response.status_code = 200
        search_response.raise_for_status = MagicMock()
        search_response.json.return_value = {
            "artists": [{"id": "mbid-sfera", "score": 98, "tags": []}]
        }

        lookup_response = MagicMock()
        lookup_response.status_code = 200
        lookup_response.raise_for_status = MagicMock()
        lookup_response.json.return_value = {
            "genres": [{"name": "Trap"}, {"name": "Italian"}],
            "tags": [
                {"name": "rap", "count": 5},
                {"name": "italian", "count": 3},
                {"name": "hip hop", "count": 2},
                {"name": "seen live", "count": 1},
            ],
        }

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(side_effect=[search_response, lookup_response])
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("app.services.musicbrainz_client.httpx.AsyncClient", return_value=mock_client):
            from app.services.musicbrainz_client import search_artist_genres

            result = await search_artist_genres("Sfera Ebbasta")

        assert "italian" not in result
        assert "seen live" not in result
        assert "trap" in result
        assert "rap" in result
        assert "hip hop" in result

    @pytest.mark.asyncio
    async def test_returns_empty_when_all_tags_are_non_genre(self):
        """If ALL tags are non-genre, falls through to MBID lookup."""
        search_response = MagicMock()
        search_response.status_code = 200
        search_response.raise_for_status = MagicMock()
        search_response.json.return_value = {
            "artists": [
                {
                    "id": "mbid-only-bad",
                    "score": 95,
                    "tags": [
                        {"name": "italian", "count": 5},
                        {"name": "seen live", "count": 2},
                    ],
                }
            ]
        }

        # MBID lookup also returns only non-genre tags
        lookup_response = MagicMock()
        lookup_response.status_code = 200
        lookup_response.raise_for_status = MagicMock()
        lookup_response.json.return_value = {
            "genres": [{"name": "Italian"}],
            "tags": [{"name": "composer", "count": 1}],
        }

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(side_effect=[search_response, lookup_response])
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("app.services.musicbrainz_client.httpx.AsyncClient", return_value=mock_client):
            from app.services.musicbrainz_client import search_artist_genres

            result = await search_artist_genres("Only Bad Tags Artist")

        assert result == []

    @pytest.mark.asyncio
    async def test_filters_decade_and_junk_tags(self):
        """Decade labels and junk tags are filtered."""
        search_response = MagicMock()
        search_response.status_code = 200
        search_response.raise_for_status = MagicMock()
        search_response.json.return_value = {
            "artists": [
                {
                    "id": "mbid-mixed",
                    "score": 95,
                    "tags": [
                        {"name": "electronic", "count": 8},
                        {"name": "2010s", "count": 5},
                        {"name": "ambient", "count": 3},
                        {"name": "fixme", "count": 1},
                        {"name": "female", "count": 2},
                    ],
                }
            ]
        }

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=search_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("app.services.musicbrainz_client.httpx.AsyncClient", return_value=mock_client):
            from app.services.musicbrainz_client import search_artist_genres

            result = await search_artist_genres("Mixed Tags Artist")

        assert result == ["electronic", "ambient"]
        assert "2010s" not in result
        assert "fixme" not in result
        assert "female" not in result


class TestPickBestMatch:
    """Tests for _pick_best_match disambiguation logic."""

    def test_returns_none_for_empty_candidates(self):
        from app.services.musicbrainz_client import _pick_best_match

        assert _pick_best_match([], "MEDUZA") is None

    def test_returns_none_when_all_below_threshold(self):
        from app.services.musicbrainz_client import _pick_best_match

        candidates = [
            {"name": "Some Artist", "score": 50},
            {"name": "Other Artist", "score": 70},
        ]
        assert _pick_best_match(candidates, "MEDUZA") is None

    def test_single_viable_candidate_returned(self):
        from app.services.musicbrainz_client import _pick_best_match

        candidates = [
            {"name": "MEDUZA", "score": 91},
            {"name": "Someone Else", "score": 40},
        ]
        result = _pick_best_match(candidates, "MEDUZA")
        assert result is not None
        assert result["name"] == "MEDUZA"

    def test_exact_name_preferred_over_higher_score_within_threshold(self):
        """The MEDUZA case: 'Eddie Meduza' score=100, 'MEDUZA' score=91.
        Since 91 >= 100-10, the exact name match wins."""
        from app.services.musicbrainz_client import _pick_best_match

        candidates = [
            {"name": "Eddie Meduza", "score": 100},
            {"name": "MEDUZA", "score": 91},
        ]
        result = _pick_best_match(candidates, "MEDUZA")
        assert result is not None
        assert result["name"] == "MEDUZA"

    def test_exact_name_wins_even_with_12_point_gap(self):
        """Exact name bonus (+15) overcomes a 12-point score gap."""
        from app.services.musicbrainz_client import _pick_best_match

        candidates = [
            {"name": "Eddie Meduza", "score": 100},
            {"name": "MEDUZA", "score": 88},  # 100-88=12, but +15 exact bonus → 103 vs 100
        ]
        result = _pick_best_match(candidates, "MEDUZA")
        assert result is not None
        assert result["name"] == "MEDUZA"

    def test_exact_name_not_preferred_when_score_gap_too_large(self):
        """When score gap exceeds exact bonus (15), higher score wins."""
        from app.services.musicbrainz_client import _pick_best_match

        candidates = [
            {"name": "Eddie Meduza", "score": 100, "tags": [
                {"name": "rock"}, {"name": "rockabilly"}, {"name": "pop"},
                {"name": "punk"}, {"name": "blues"},
            ]},
            {"name": "MEDUZA", "score": 85},  # 100+10 vs 85+15=100 → Eddie wins
        ]
        result = _pick_best_match(candidates, "MEDUZA")
        assert result is not None
        assert result["name"] == "Eddie Meduza"

    def test_highest_score_wins_when_no_exact_match_and_equal_signals(self):
        """When no candidate has an exact name match and signals are equal,
        highest base score wins."""
        from app.services.musicbrainz_client import _pick_best_match

        candidates = [
            {"name": "Maz (Quebec folk)", "score": 95},
            {"name": "MAZ DJ", "score": 90},
        ]
        result = _pick_best_match(candidates, "Maz")
        assert result is not None
        assert result["name"] == "Maz (Quebec folk)"

    def test_case_insensitive_name_matching(self):
        """Name comparison should be case-insensitive."""
        from app.services.musicbrainz_client import _pick_best_match

        candidates = [
            {"name": "Other Artist", "score": 98},
            {"name": "meduza", "score": 91},
        ]
        result = _pick_best_match(candidates, "MEDUZA")
        assert result is not None
        assert result["name"] == "meduza"

    def test_strips_whitespace_in_names(self):
        from app.services.musicbrainz_client import _pick_best_match

        candidates = [
            {"name": "Other", "score": 97},
            {"name": " MEDUZA ", "score": 90},
        ]
        result = _pick_best_match(candidates, "MEDUZA")
        assert result is not None
        assert result["name"] == " MEDUZA "

    @pytest.mark.asyncio
    async def test_disambiguation_in_full_search(self):
        """End-to-end: search_artist_genres picks the correct MEDUZA."""
        search_response = MagicMock()
        search_response.status_code = 200
        search_response.raise_for_status = MagicMock()
        search_response.json.return_value = {
            "artists": [
                {
                    "id": "mbid-eddie",
                    "name": "Eddie Meduza",
                    "score": 100,
                    "tags": [
                        {"name": "rock", "count": 5},
                        {"name": "rockabilly", "count": 3},
                    ],
                },
                {
                    "id": "mbid-meduza",
                    "name": "MEDUZA",
                    "score": 91,
                    "tags": [
                        {"name": "dance", "count": 4},
                        {"name": "house", "count": 3},
                        {"name": "edm", "count": 2},
                    ],
                },
            ]
        }

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=search_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch(
            "app.services.musicbrainz_client.httpx.AsyncClient",
            return_value=mock_client,
        ):
            from app.services.musicbrainz_client import search_artist_genres

            result = await search_artist_genres("MEDUZA")

        # Should pick MEDUZA (exact match), not Eddie Meduza
        assert "dance" in result
        assert "house" in result
        assert "rockabilly" not in result


class TestPickBestMatchCompositeScoring:
    """Tests for the composite scoring signals in _pick_best_match."""

    def test_tag_count_bonus_breaks_tie(self):
        """Among equal-score candidates, more genre tags wins."""
        from app.services.musicbrainz_client import _pick_best_match

        candidates = [
            {
                "name": "Artist A",
                "score": 95,
                "tags": [{"name": "folk"}],
            },
            {
                "name": "Artist B",
                "score": 95,
                "tags": [
                    {"name": "house"},
                    {"name": "dance"},
                    {"name": "electronic"},
                    {"name": "edm"},
                ],
            },
        ]
        result = _pick_best_match(candidates, "Artist X")
        assert result is not None
        assert result["name"] == "Artist B"

    def test_tag_count_bonus_capped_at_10(self):
        """Tag bonus caps at +10 (5 tags * 2 each)."""
        from app.services.musicbrainz_client import _pick_best_match

        candidates = [
            {
                "name": "Many Tags",
                "score": 90,
                "tags": [{"name": f"genre-{i}"} for i in range(10)],
            },
            {
                "name": "Few Tags",
                "score": 100,
                "tags": [],
            },
        ]
        # Many Tags: 90 + 10 (tag cap) = 100. Few Tags: 100 + 0 = 100. Tie → stable sort → Many Tags first
        # Actually both are 100, but Many Tags was sorted first due to stable sort
        result = _pick_best_match(candidates, "Unrelated")
        assert result is not None
        # Both score 100 composite, stable sort preserves order (Many Tags sorted first)
        assert result["name"] == "Many Tags"

    def test_non_genre_tags_dont_count(self):
        """Tags in _NON_GENRE_TAGS blocklist don't contribute to tag bonus."""
        from app.services.musicbrainz_client import _pick_best_match

        candidates = [
            {
                "name": "Bloated Tags",
                "score": 95,
                "tags": [
                    {"name": "italian"},
                    {"name": "seen live"},
                    {"name": "2010s"},
                    {"name": "composer"},
                ],  # all blocked → 0 filtered
            },
            {
                "name": "Good Tags",
                "score": 95,
                "tags": [{"name": "rock"}, {"name": "pop"}],  # 2 valid → +4
            },
        ]
        result = _pick_best_match(candidates, "Unrelated")
        assert result is not None
        assert result["name"] == "Good Tags"

    def test_disambiguation_bonus_with_genre_words(self):
        """Disambiguation containing genre words gives a bonus."""
        from app.services.musicbrainz_client import _pick_best_match

        candidates = [
            {
                "name": "MEDUZA",
                "score": 90,
                "tags": [],
                "disambiguation": "Italian house music trio",
            },
            {
                "name": "MEDUZA",
                "score": 90,
                "tags": [],
                "disambiguation": "",
            },
        ]
        result = _pick_best_match(candidates, "MEDUZA")
        assert result is not None
        # First candidate: "house" + "music" + "trio" = 3 words → +9
        assert result["disambiguation"] == "Italian house music trio"

    def test_disambiguation_bonus_capped_at_9(self):
        """Disambig bonus caps at +9 (3 words * 3 each)."""
        from app.services.musicbrainz_client import _pick_best_match

        candidates = [
            {
                "name": "A",
                "score": 90,
                "tags": [],
                "disambiguation": "rock pop jazz funk soul blues house techno",
            },
            {
                "name": "B",
                "score": 99,
                "tags": [],
                "disambiguation": "",
            },
        ]
        # A: 90 + 9 (cap) = 99. B: 99 + 0 = 99. Tie → stable sort → A first
        result = _pick_best_match(candidates, "Unrelated")
        assert result is not None
        assert result["name"] == "A"

    def test_meduza_full_disambiguation(self):
        """Real-world MEDUZA case: exact name + tags + disambig vs higher score."""
        from app.services.musicbrainz_client import _pick_best_match

        candidates = [
            {
                "name": "Eddie Meduza",
                "score": 100,
                "tags": [{"name": "rock"}, {"name": "rockabilly"}],
                "disambiguation": "Swedish rock singer",
            },
            {
                "name": "MEDUZA",
                "score": 91,
                "tags": [
                    {"name": "dance"},
                    {"name": "house"},
                    {"name": "edm"},
                ],
                "disambiguation": "Italian house music trio",
            },
        ]
        result = _pick_best_match(candidates, "MEDUZA")
        assert result is not None
        assert result["name"] == "MEDUZA"
        # MEDUZA: 91 + 15 (exact) + 6 (3 tags * 2) + 9 (house+music+trio) = 121
        # Eddie:  100 + 0 + 4 (2 tags * 2) + 6 (rock+singer) = 110

    def test_fisher_disambiguation(self):
        """FISHER case: house DJ should win over vocal trance homonym."""
        from app.services.musicbrainz_client import _pick_best_match

        candidates = [
            {
                "name": "Fisher",
                "score": 100,
                "tags": [{"name": "trance"}, {"name": "vocal trance"}],
                "disambiguation": "vocal trance artist",
            },
            {
                "name": "FISHER",
                "score": 95,
                "tags": [
                    {"name": "house"},
                    {"name": "tech house"},
                    {"name": "dance"},
                    {"name": "electronic"},
                ],
                "disambiguation": "Australian house DJ and producer",
            },
        ]
        result = _pick_best_match(candidates, "FISHER")
        assert result is not None
        assert result["name"] == "FISHER"
        # FISHER: 95 + 15 (exact) + 8 (4 tags * 2) + 9 (house+dj+producer → cap) = 127
        # Fisher: 100 + 0 + 4 (2 tags * 2) + 3 (trance) = 107

    def test_single_viable_candidate_returned_directly(self):
        """When only one candidate is viable (score >= 85), return it without ranking."""
        from app.services.musicbrainz_client import _pick_best_match

        candidates = [
            {"name": "Good Artist", "score": 90, "tags": []},
            {"name": "Bad Artist", "score": 50, "tags": []},
        ]
        result = _pick_best_match(candidates, "Other Name")
        assert result is not None
        assert result["name"] == "Good Artist"

    def test_all_signals_combine(self):
        """Composite score uses all three signals additively."""
        from app.services.musicbrainz_client import _pick_best_match

        candidates = [
            {
                "name": "Weak Match",
                "score": 100,
                "tags": [],
                "disambiguation": "",
            },
            {
                "name": "Target",
                "score": 86,
                "tags": [
                    {"name": "electronic"},
                    {"name": "house"},
                    {"name": "techno"},
                ],
                "disambiguation": "electronic music producer",
            },
        ]
        result = _pick_best_match(candidates, "Target")
        assert result is not None
        # Target: 86 + 15 (exact) + 6 (3 tags) + 9 (electronic+music+producer) = 116
        # Weak:   100 + 0 + 0 + 0 = 100
        assert result["name"] == "Target"

    def test_missing_tags_and_disambig_fields(self):
        """Candidates without tags or disambiguation fields don't crash."""
        from app.services.musicbrainz_client import _pick_best_match

        candidates = [
            {"name": "Minimal", "score": 95},
            {"name": "Also Minimal", "score": 92},
        ]
        result = _pick_best_match(candidates, "Minimal")
        assert result is not None
        assert result["name"] == "Minimal"  # exact name + higher score

    @pytest.mark.asyncio
    async def test_fisher_end_to_end(self):
        """End-to-end: search_artist_genres picks FISHER over vocal trance homonym."""
        search_response = MagicMock()
        search_response.status_code = 200
        search_response.raise_for_status = MagicMock()
        search_response.json.return_value = {
            "artists": [
                {
                    "id": "mbid-vocal-fisher",
                    "name": "Fisher",
                    "score": 100,
                    "tags": [
                        {"name": "trance", "count": 3},
                        {"name": "vocal trance", "count": 2},
                    ],
                    "disambiguation": "vocal trance artist",
                },
                {
                    "id": "mbid-house-fisher",
                    "name": "FISHER",
                    "score": 95,
                    "tags": [
                        {"name": "house", "count": 5},
                        {"name": "tech house", "count": 4},
                        {"name": "dance", "count": 3},
                        {"name": "electronic", "count": 2},
                    ],
                    "disambiguation": "Australian house DJ and producer",
                },
            ]
        }

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=search_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch(
            "app.services.musicbrainz_client.httpx.AsyncClient",
            return_value=mock_client,
        ):
            from app.services.musicbrainz_client import search_artist_genres

            result = await search_artist_genres("FISHER")

        assert "house" in result
        assert "tech house" in result
        assert "trance" not in result
        assert "vocal trance" not in result


class TestFilterNonGenreTags:
    """Tests for the exported filter_non_genre_tags function."""

    def test_filters_bad_tags(self):
        from app.services.musicbrainz_client import filter_non_genre_tags

        tags = ["rock", "italian", "electronic", "seen live", "2010s"]
        result = filter_non_genre_tags(tags)
        assert result == ["rock", "electronic"]

    def test_empty_input(self):
        from app.services.musicbrainz_client import filter_non_genre_tags

        assert filter_non_genre_tags([]) == []

    def test_all_bad_tags(self):
        from app.services.musicbrainz_client import filter_non_genre_tags

        result = filter_non_genre_tags(["italian", "composer", "2020s"])
        assert result == []

    def test_all_good_tags(self):
        from app.services.musicbrainz_client import filter_non_genre_tags

        tags = ["rock", "pop", "electronic", "hip hop"]
        result = filter_non_genre_tags(tags)
        assert result == tags
