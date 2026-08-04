"""Test del recupero copertine in sottofondo.

Le copertine si prendono un brano alla volta: quello che puo' andare storto e'
che un brano rotto fermi tutta la coda, o che il limite di chiamate venga
ignorato e la finestra si saturi mentre l'utente sta guardando un'altra pagina.
"""

from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services import track_metadata
from app.utils.rate_limiter import ThrottleError


def _spotify_track(image: str | None = "https://img.example.com/a.jpg") -> dict:
    return {
        "album": {
            "name": "Album",
            "images": [{"url": image}] if image else [],
        },
        "preview_url": None,
    }


@asynccontextmanager
async def _fake_session(db):
    yield db


async def _passthrough(fn, *args, **kwargs):
    return await fn(*args, **kwargs)


def _patches(client, db, upserted):
    async def _record(_db, track_id, item):
        upserted.append((track_id, item))

    return (
        patch(
            "app.services.track_metadata.async_session",
            lambda: _fake_session(db),
        ),
        patch("app.services.track_metadata.SpotifyClient", return_value=client),
        patch("app.services.track_metadata.retry_with_backoff", _passthrough),
        patch("app.services.track_metadata._upsert", _record),
        patch("app.services.track_metadata.asyncio.sleep", AsyncMock()),
    )


def _client() -> MagicMock:
    client = MagicMock()
    client.close = AsyncMock()
    return client


class TestFetchMissingImages:
    @pytest.mark.asyncio
    async def test_a_broken_track_does_not_stop_the_queue(self):
        client = _client()
        client.get_track = AsyncMock(
            side_effect=[
                _spotify_track(),
                ValueError("brano sparito"),
                _spotify_track(),
            ]
        )
        upserted: list = []

        p1, p2, p3, p4, p5 = _patches(client, AsyncMock(), upserted)
        with p1, p2, p3, p4, p5:
            await track_metadata.fetch_missing_images(1, ["a", "b", "c"])

        assert [t for t, _ in upserted] == ["a", "c"]

    @pytest.mark.asyncio
    async def test_throttle_stops_the_run(self):
        """Finestra piena: si smette, non si insiste — si riprende alla visita dopo."""
        client = _client()
        client.get_track = AsyncMock(
            side_effect=[
                _spotify_track(),
                ThrottleError("finestra piena"),
                _spotify_track(),
            ]
        )
        upserted: list = []

        p1, p2, p3, p4, p5 = _patches(client, AsyncMock(), upserted)
        with p1, p2, p3, p4, p5:
            await track_metadata.fetch_missing_images(1, ["a", "b", "c"])

        assert [t for t, _ in upserted] == ["a"]
        assert client.get_track.await_count == 2

    @pytest.mark.asyncio
    async def test_a_second_run_for_the_same_user_is_skipped(self):
        """La pagina richiede la lista ogni 15s: non deve moltiplicare le code."""
        client = _client()
        client.get_track = AsyncMock(return_value=_spotify_track())
        upserted: list = []

        p1, p2, p3, p4, p5 = _patches(client, AsyncMock(), upserted)
        with p1, p2, p3, p4, p5:
            track_metadata._running.add(7)
            try:
                await track_metadata.fetch_missing_images(7, ["a", "b"])
            finally:
                track_metadata._running.discard(7)

        client.get_track.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_the_flag_is_cleared_when_the_run_ends(self):
        client = _client()
        client.get_track = AsyncMock(return_value=_spotify_track())

        p1, p2, p3, p4, p5 = _patches(client, AsyncMock(), [])
        with p1, p2, p3, p4, p5:
            await track_metadata.fetch_missing_images(7, ["a"])

        assert 7 not in track_metadata._running

    @pytest.mark.asyncio
    async def test_no_ids_means_no_client(self):
        client = _client()
        client.get_track = AsyncMock()

        p1, p2, p3, p4, p5 = _patches(client, AsyncMock(), [])
        with p1, p2, p3, p4, p5:
            await track_metadata.fetch_missing_images(1, [])

        client.get_track.assert_not_awaited()


class TestReadTrackImages:
    @pytest.mark.asyncio
    async def test_empty_list_skips_the_query(self):
        db = AsyncMock()
        assert await track_metadata.read_track_images(db, []) == {}
        db.execute.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_returns_cached_rows_by_id(self):
        row = MagicMock(
            track_spotify_id="a",
            album_name="Album",
            album_image="https://img.example.com/a.jpg",
            preview_url=None,
        )
        result = MagicMock()
        result.scalars.return_value.all.return_value = [row]
        db = AsyncMock()
        db.execute = AsyncMock(return_value=result)

        got = await track_metadata.read_track_images(db, ["a", "b"])

        assert got["a"]["album_image"] == "https://img.example.com/a.jpg"
        assert "b" not in got
