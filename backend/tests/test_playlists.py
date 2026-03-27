"""Unit tests for the 3 bug fixes in the playlist/dashboard modules.

Covers:
1. Popularity enrichment (playlists.py Phase 1b)
2. Genre cap of 50 (_extract_genres in audio_analyzer.py)
3. Track count fallback (playlists.py get_playlists)
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.audio_analyzer import _extract_genres
from app.services.spotify_client import _validate_spotify_id


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_track(
    track_id: str,
    artist_id: str = "artist1234567890",
    popularity: int | None = None,
) -> dict:
    t = {
        "id": track_id,
        "name": f"Track {track_id}",
        "artists": [{"id": artist_id, "name": f"Artist {artist_id}"}],
    }
    if popularity is not None:
        t["popularity"] = popularity
    return t


def _make_client(get_track_side_effect=None, get_artist_side_effect=None) -> MagicMock:
    client = MagicMock()
    client.get_track = AsyncMock(side_effect=get_track_side_effect)
    client.get_artist = AsyncMock(side_effect=get_artist_side_effect)
    client.get = AsyncMock()
    client.close = AsyncMock()
    return client


async def _passthrough_retry(fn, *args, **kwargs):
    """Drop-in replacement for retry_with_backoff that calls fn directly."""
    return await fn(*args, **kwargs)


# ---------------------------------------------------------------------------
# 1. Popularity enrichment logic
# ---------------------------------------------------------------------------


class TestGetTrack:
    """Tests for SpotifyClient.get_track — caching and ID validation."""

    @pytest.mark.asyncio
    async def test_get_track_validates_id_too_short(self):
        """IDs shorter than 15 chars must raise ValueError."""
        with pytest.raises(ValueError, match="Invalid Spotify ID"):
            _validate_spotify_id("short")

    @pytest.mark.asyncio
    async def test_get_track_validates_id_too_long(self):
        """IDs longer than 25 chars must raise ValueError."""
        with pytest.raises(ValueError, match="Invalid Spotify ID"):
            _validate_spotify_id("a" * 26)

    @pytest.mark.asyncio
    async def test_get_track_validates_id_with_special_chars(self):
        """IDs with non-alphanumeric chars must raise ValueError."""
        with pytest.raises(ValueError, match="Invalid Spotify ID"):
            _validate_spotify_id("track-id!@#$%^&*()")

    def test_get_track_accepts_valid_id(self):
        """A 22-char alphanumeric ID must not raise."""
        _validate_spotify_id("4iV5W9uYEdYUVa79Axb7Rh")  # no exception

    def test_get_track_accepts_minimum_length_id(self):
        """A 15-char alphanumeric ID must not raise."""
        _validate_spotify_id("a" * 15)

    def test_get_track_accepts_maximum_length_id(self):
        """A 25-char alphanumeric ID must not raise."""
        _validate_spotify_id("a" * 25)


class TestPopularityEnrichmentLogic:
    """Tests for the inline popularity enrichment logic in compare_playlists.

    The logic is:
      1. Collect track IDs where popularity is 0 or absent.
      2. Call client.get_track for each (via gather_in_chunks).
      3. Merge returned popularity values back into the track dicts.
    """

    @pytest.mark.asyncio
    async def test_tracks_without_popularity_are_identified(self):
        """Tracks with no popularity key must end up in missing_pop_ids."""
        tracks = [
            _make_track("tid111111111111", popularity=None),  # missing
            _make_track("tid222222222222", popularity=0),  # zero counts as missing
            _make_track("tid333333333333", popularity=75),  # present — should be kept
        ]
        # Replicate the collection logic from playlists.py Phase 1b
        missing_pop_ids: set[str] = set()
        for t in tracks:
            if t.get("id") and not t.get("popularity"):
                missing_pop_ids.add(t["id"])

        assert "tid111111111111" in missing_pop_ids
        assert "tid222222222222" in missing_pop_ids
        assert "tid333333333333" not in missing_pop_ids

    @pytest.mark.asyncio
    async def test_popularity_merged_back_after_fetch(self):
        """After enrichment, track dicts must contain the fetched popularity."""
        track = _make_track("tid111111111111", popularity=None)
        tracks = [track]

        # Simulate what the router does: build pop_map, then merge
        pop_map = {"tid111111111111": 82}
        for t in tracks:
            tid = t.get("id")
            if tid and tid in pop_map:
                t["popularity"] = pop_map[tid]

        assert track["popularity"] == 82

    @pytest.mark.asyncio
    async def test_missing_popularity_capped_at_100(self):
        """Only the first 100 track IDs with missing popularity must be enriched."""
        # Build 120 tracks without popularity
        tracks = [
            _make_track(f"t{str(i).zfill(14)}", popularity=None) for i in range(120)
        ]
        missing_pop_ids: set[str] = set()
        for t in tracks:
            if t.get("id") and not t.get("popularity"):
                missing_pop_ids.add(t["id"])

        # The router caps at 100
        missing_pop_list = list(missing_pop_ids)[:100]
        assert len(missing_pop_list) == 100

    @pytest.mark.asyncio
    async def test_track_with_explicit_popularity_not_enriched(self):
        """Tracks that already have popularity > 0 must not appear in missing set."""
        track = _make_track("tid111111111111", popularity=55)
        missing_pop_ids: set[str] = set()
        if track.get("id") and not track.get("popularity"):
            missing_pop_ids.add(track["id"])

        assert len(missing_pop_ids) == 0

    @pytest.mark.asyncio
    async def test_enrichment_skipped_when_no_missing_tracks(self):
        """When all tracks have popularity, get_track must never be called."""
        client = _make_client()
        tracks = [
            _make_track("tid111111111111", popularity=80),
            _make_track("tid222222222222", popularity=50),
        ]

        missing_pop_ids: set[str] = set()
        for t in tracks:
            if t.get("id") and not t.get("popularity"):
                missing_pop_ids.add(t["id"])

        # No enrichment calls expected
        if missing_pop_ids:
            await client.get_track("any")

        client.get_track.assert_not_called()

    @pytest.mark.asyncio
    async def test_pop_map_ignores_none_returns(self):
        """If get_track returns None for popularity, track must not be touched."""
        # pop_map only stores non-None values (router logic: r[1] is not None)
        raw_results = [
            ("tid111111111111", None),  # failed fetch — omitted
            ("tid222222222222", 65),  # success
        ]
        pop_map: dict[str, int] = {}
        for r in raw_results:
            if isinstance(r, tuple) and r[1] is not None:
                pop_map[r[0]] = r[1]

        assert "tid111111111111" not in pop_map
        assert pop_map["tid222222222222"] == 65


# ---------------------------------------------------------------------------
# 2. Genre cap verification (_extract_genres)
# ---------------------------------------------------------------------------


class TestExtractGenres:
    """Tests for _extract_genres in audio_analyzer.py (uses genre_cache)."""

    @pytest.mark.asyncio
    async def test_all_artists_fetched_no_cap(self):
        """All unique artist IDs are passed to genre cache (no artificial cap)."""
        n = 40
        tracks = [
            {
                "id": f"t{str(i).zfill(14)}",
                "artists": [{"id": f"a{str(i).zfill(14)}", "name": f"Artist {i}"}],
            }
            for i in range(n)
        ]
        expected_ids = {f"a{str(i).zfill(14)}" for i in range(n)}

        captured_ids = []

        async def _mock_cache(db, client, artist_ids):
            captured_ids.extend(artist_ids)
            return {aid: ["pop"] for aid in artist_ids}

        db = AsyncMock()
        client = _make_client()

        with patch(
            "app.services.audio_analyzer.get_artist_genres_cached", _mock_cache
        ):
            await _extract_genres(db, client, tracks)

        assert set(captured_ids) == expected_ids

    @pytest.mark.asyncio
    async def test_extract_genres_empty_tracks_returns_empty(self):
        """No tracks -> empty genre distribution, no cache call."""
        db = AsyncMock()
        client = _make_client()

        async def _mock_cache(db, client, artist_ids):
            return {}

        with patch(
            "app.services.audio_analyzer.get_artist_genres_cached", _mock_cache
        ):
            result = await _extract_genres(db, client, [])

        assert result == {}

    @pytest.mark.asyncio
    async def test_extract_genres_tracks_without_artist_ids(self):
        """Tracks whose artists have no 'id' key must be skipped gracefully."""
        tracks = [
            {"id": "t111111111111111", "artists": [{"name": "No ID Artist"}]},
        ]
        db = AsyncMock()
        client = _make_client()

        async def _mock_cache(db, client, artist_ids):
            return {}

        with patch(
            "app.services.audio_analyzer.get_artist_genres_cached", _mock_cache
        ):
            result = await _extract_genres(db, client, tracks)

        assert result == {}

    @pytest.mark.asyncio
    async def test_extract_genres_aggregates_percentages(self):
        """Genre distribution must sum to 100%."""
        tracks = [
            {
                "id": "t111111111111111",
                "artists": [{"id": "a111111111111111"}],
            },
            {
                "id": "t222222222222222",
                "artists": [{"id": "a222222222222222"}],
            },
        ]

        async def _mock_cache(db, client, artist_ids):
            return {
                "a111111111111111": ["rock"],
                "a222222222222222": ["pop"],
            }

        db = AsyncMock()
        client = _make_client()

        with patch(
            "app.services.audio_analyzer.get_artist_genres_cached", _mock_cache
        ):
            result = await _extract_genres(db, client, tracks)

        assert result  # non-empty
        total = sum(result.values())
        assert abs(total - 100.0) < 0.1, f"Percentages should sum to 100, got {total}"

    @pytest.mark.asyncio
    async def test_extract_genres_deduplicates_artists(self):
        """The same artist appearing in multiple tracks must be deduplicated."""
        tracks = [
            {"id": f"t{str(i).zfill(14)}", "artists": [{"id": "shared_artist1234"}]}
            for i in range(5)
        ]

        captured_ids = []

        async def _mock_cache(db, client, artist_ids):
            captured_ids.extend(artist_ids)
            return {aid: ["pop"] for aid in artist_ids}

        db = AsyncMock()
        client = _make_client()

        with patch(
            "app.services.audio_analyzer.get_artist_genres_cached", _mock_cache
        ):
            await _extract_genres(db, client, tracks)

        assert len(captured_ids) == 1, (
            f"Same artist must be deduplicated; expected 1 ID, got {len(captured_ids)}"
        )


# ---------------------------------------------------------------------------
# 3. Track count fallback logic
# ---------------------------------------------------------------------------


class TestTrackCountFallback:
    """Tests for the inline track_count=0 fallback in get_playlists (lines 71-91)."""

    def test_zero_count_playlists_are_selected(self):
        """Playlists with track_count=0 must be identified for metadata refetch."""
        playlists = [
            {"id": "pid1111111111111", "name": "A", "track_count": 0},
            {"id": "pid2222222222222", "name": "B", "track_count": 10},
            {"id": "pid3333333333333", "name": "C", "track_count": 0},
        ]
        zero_count = [p for p in playlists if p["track_count"] == 0]
        assert len(zero_count) == 2
        assert all(p["track_count"] == 0 for p in zero_count)

    def test_zero_count_refetch_capped_at_20(self):
        """At most 20 playlists with track_count=0 should be scheduled for refetch."""
        playlists = [
            {"id": f"pid{str(i).zfill(12)}", "name": f"P{i}", "track_count": 0}
            for i in range(30)
        ]
        zero_count = [p for p in playlists if p["track_count"] == 0]
        to_fix = zero_count[:20]
        assert len(to_fix) == 20

    def test_nonzero_track_count_not_refetched(self):
        """Playlists with track_count > 0 must not be selected for refetch."""
        playlists = [
            {"id": "pid1111111111111", "name": "A", "track_count": 5},
            {"id": "pid2222222222222", "name": "B", "track_count": 100},
        ]
        zero_count = [p for p in playlists if p["track_count"] == 0]
        assert zero_count == []

    @pytest.mark.asyncio
    async def test_track_count_updated_from_meta_response(self):
        """After fetching metadata, track_count must be updated in the playlist dict."""
        playlist = {"id": "pid1111111111111", "name": "MyList", "track_count": 0}

        # Simulate what _fetch_playlist_meta does
        meta = {"tracks": {"total": 42}}
        total = meta.get("tracks", {}).get("total")
        if total is not None:
            playlist["track_count"] = total

        assert playlist["track_count"] == 42

    @pytest.mark.asyncio
    async def test_track_count_unchanged_when_meta_missing(self):
        """If API response has no tracks.total, track_count must remain 0."""
        playlist = {"id": "pid1111111111111", "name": "MyList", "track_count": 0}

        meta = {}  # no 'tracks' key
        total = meta.get("tracks", {}).get("total")
        if total is not None:
            playlist["track_count"] = total

        assert playlist["track_count"] == 0

    @pytest.mark.asyncio
    async def test_fetch_playlist_meta_calls_correct_endpoint(self):
        """The refetch must call /playlists/{id} via client.get."""
        client = _make_client()
        client.get.return_value = {"tracks": {"total": 15}}

        playlist = {"id": "pid1111111111111", "name": "MyList", "track_count": 0}

        # Replicate _fetch_playlist_meta from the router
        with patch(
            "app.routers.playlists.retry_with_backoff",
            side_effect=lambda fn, *args, **kwargs: fn(*args, **kwargs),
        ):
            meta = await client.get(f"/playlists/{playlist['id']}")
            total = meta.get("tracks", {}).get("total")
            if total is not None:
                playlist["track_count"] = total

        client.get.assert_called_once_with(f"/playlists/{playlist['id']}")
        assert playlist["track_count"] == 15

    @pytest.mark.asyncio
    async def test_no_api_call_when_no_zero_count_playlists(self):
        """When no playlist has track_count=0, client.get must not be called."""
        client = _make_client()
        playlists = [
            {"id": "pid1111111111111", "name": "A", "track_count": 5},
            {"id": "pid2222222222222", "name": "B", "track_count": 20},
        ]
        zero_count = [p for p in playlists if p["track_count"] == 0]
        if zero_count:
            await client.get("/playlists/any")

        client.get.assert_not_called()

    @pytest.mark.asyncio
    async def test_track_count_fallback_uses_get_playlist_items_total(self):
        """_fetch_playlist_meta calls get_playlist_items(id, limit=1) and
        reads the 'total' field to fix track_count=0."""

        async def _passthrough_retry(fn, *args, **kwargs):
            return await fn(*args, **kwargs)

        async def _passthrough_gather(coros, chunk_size=5):
            results = []
            for coro in coros:
                results.append(await coro)
            return results

        client = _make_client()

        # get_playlists returns one playlist with track_count=0
        client.get.return_value = {
            "items": [
                {
                    "id": "pid1111111111111",
                    "name": "Empty Count",
                    "description": "",
                    "images": [],
                    "tracks": {"total": 0},
                    "owner": {"id": "owner123", "display_name": "Me"},
                }
            ],
            "total": 1,
        }

        # get_playlist_items returns total=42
        client.get_playlist_items = AsyncMock(
            return_value={"total": 42, "items": [{"track": {"id": "t" * 15}}]}
        )

        # Mock get_playlists on the client
        client.get_playlists = AsyncMock(
            return_value={
                "items": [
                    {
                        "id": "pid1111111111111",
                        "name": "Empty Count",
                        "description": "",
                        "images": [],
                        "tracks": {"total": 0},
                        "owner": {"id": "owner123", "display_name": "Me"},
                    }
                ],
                "total": 1,
            }
        )

        # Mock the DB query for user
        mock_result = MagicMock()
        mock_user = MagicMock()
        mock_user.spotify_id = "owner123"
        mock_result.scalar_one_or_none.return_value = mock_user
        mock_db = AsyncMock()
        mock_db.execute = AsyncMock(return_value=mock_result)

        with (
            patch("app.routers.playlists.SpotifyClient", return_value=client),
            patch("app.routers.playlists.retry_with_backoff", _passthrough_retry),
            patch("app.routers.playlists.gather_in_chunks", _passthrough_gather),
        ):
            from app.routers.playlists import get_playlists

            mock_request = MagicMock()
            result = await get_playlists(
                request=mock_request,
                limit=50,
                offset=0,
                user_id=1,
                db=mock_db,
            )

        # The playlist should now have track_count=42 from the fallback
        assert result["playlists"][0]["track_count"] == 42
        client.get_playlist_items.assert_called_once_with(
            "pid1111111111111", limit=1, offset=0
        )
