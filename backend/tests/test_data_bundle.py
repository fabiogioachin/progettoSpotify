"""Test per data_bundle.py — deduplication delle chiamate Spotify API per request."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.data_bundle import RequestDataBundle


@pytest.fixture
def mock_client():
    client = MagicMock()
    client.get_top_tracks = AsyncMock(return_value={"items": [{"id": "t1"}]})
    client.get_top_artists = AsyncMock(return_value={"items": [{"id": "a1"}]})
    client.get_recently_played = AsyncMock(return_value={"items": [{"id": "r1"}]})
    client.get_me = AsyncMock(return_value={"id": "user1", "display_name": "Test"})
    client.close = AsyncMock()
    return client


@pytest.fixture
def bundle(mock_client):
    return RequestDataBundle(mock_client)


class TestGetTopTracksDedup:
    @pytest.mark.asyncio
    async def test_same_params_calls_client_once(self, bundle, mock_client):
        """get_top_tracks con stessi parametri chiama il client una sola volta."""
        result1 = await bundle.get_top_tracks(time_range="short_term", limit=50)
        result2 = await bundle.get_top_tracks(time_range="short_term", limit=50)

        assert result1 is result2
        assert mock_client.get_top_tracks.await_count == 1

    @pytest.mark.asyncio
    async def test_different_time_ranges_call_client_separately(
        self, bundle, mock_client
    ):
        """get_top_tracks con time_range diversi chiama il client per ciascuno."""
        await bundle.get_top_tracks(time_range="short_term")
        await bundle.get_top_tracks(time_range="medium_term")

        assert mock_client.get_top_tracks.await_count == 2

    @pytest.mark.asyncio
    async def test_different_limits_call_client_separately(self, bundle, mock_client):
        """get_top_tracks con limit diversi chiama il client per ciascuno."""
        await bundle.get_top_tracks(time_range="short_term", limit=10)
        await bundle.get_top_tracks(time_range="short_term", limit=50)

        assert mock_client.get_top_tracks.await_count == 2


class TestGetTopArtistsDedup:
    @pytest.mark.asyncio
    async def test_same_params_calls_client_once(self, bundle, mock_client):
        """get_top_artists con stessi parametri chiama il client una sola volta."""
        result1 = await bundle.get_top_artists(time_range="long_term")
        result2 = await bundle.get_top_artists(time_range="long_term")

        assert result1 is result2
        assert mock_client.get_top_artists.await_count == 1

    @pytest.mark.asyncio
    async def test_different_time_ranges_call_client_separately(
        self, bundle, mock_client
    ):
        """get_top_artists con time_range diversi chiama il client per ciascuno."""
        await bundle.get_top_artists(time_range="short_term")
        await bundle.get_top_artists(time_range="long_term")

        assert mock_client.get_top_artists.await_count == 2


class TestGetRecentlyPlayedDedup:
    @pytest.mark.asyncio
    async def test_calls_client_once(self, bundle, mock_client):
        """get_recently_played chiamato due volte chiama il client una sola volta."""
        result1 = await bundle.get_recently_played()
        result2 = await bundle.get_recently_played()

        assert result1 is result2
        assert mock_client.get_recently_played.await_count == 1


class TestGetMeDedup:
    @pytest.mark.asyncio
    async def test_calls_client_once(self, bundle, mock_client):
        """get_me chiamato due volte chiama il client una sola volta."""
        result1 = await bundle.get_me()
        result2 = await bundle.get_me()

        assert result1 is result2
        assert mock_client.get_me.await_count == 1


class TestPrefetch:
    @pytest.mark.asyncio
    async def test_prefetch_artists_and_tracks(self, bundle, mock_client):
        """prefetch carica tutti e 3 i time_range per artists e tracks."""
        await bundle.prefetch(artists=True, tracks=True, recent=False, me=False)

        # 3 time_ranges each
        assert mock_client.get_top_artists.await_count == 3
        assert mock_client.get_top_tracks.await_count == 3

    @pytest.mark.asyncio
    async def test_prefetch_populates_cache(self, bundle, mock_client):
        """Dopo prefetch, le singole get_* non richiamano il client."""
        await bundle.prefetch(artists=True, tracks=True, recent=True, me=True)

        # Reset call counts to check no further calls
        mock_client.get_top_artists.reset_mock()
        mock_client.get_top_tracks.reset_mock()
        mock_client.get_recently_played.reset_mock()
        mock_client.get_me.reset_mock()

        await bundle.get_top_artists(time_range="short_term")
        await bundle.get_top_artists(time_range="medium_term")
        await bundle.get_top_artists(time_range="long_term")
        await bundle.get_top_tracks(time_range="short_term")
        await bundle.get_top_tracks(time_range="medium_term")
        await bundle.get_top_tracks(time_range="long_term")
        await bundle.get_recently_played()
        await bundle.get_me()

        mock_client.get_top_artists.assert_not_awaited()
        mock_client.get_top_tracks.assert_not_awaited()
        mock_client.get_recently_played.assert_not_awaited()
        mock_client.get_me.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_prefetch_error_does_not_crash_others(self, bundle, mock_client):
        """Se una task in prefetch fallisce, le altre completano (return_exceptions)."""
        mock_client.get_top_artists.side_effect = [
            RuntimeError("API down"),  # short_term fails
            {"items": [{"id": "a2"}]},  # medium_term ok
            {"items": [{"id": "a3"}]},  # long_term ok
        ]

        await bundle.prefetch(artists=True, tracks=True)

        # tracks should all succeed despite artists error
        assert mock_client.get_top_tracks.await_count == 3

        # medium_term and long_term artists should be cached
        result = await bundle.get_top_artists(time_range="medium_term")
        assert result == {"items": [{"id": "a2"}]}

    @pytest.mark.asyncio
    async def test_prefetch_only_recent_and_me(self, bundle, mock_client):
        """prefetch con solo recent e me non chiama artists/tracks."""
        await bundle.prefetch(artists=False, tracks=False, recent=True, me=True)

        mock_client.get_top_artists.assert_not_awaited()
        mock_client.get_top_tracks.assert_not_awaited()
        assert mock_client.get_recently_played.await_count == 1
        assert mock_client.get_me.await_count == 1

    @pytest.mark.asyncio
    async def test_prefetch_nothing(self, bundle, mock_client):
        """prefetch con tutto False non chiama nulla."""
        await bundle.prefetch(artists=False, tracks=False, recent=False, me=False)

        mock_client.get_top_artists.assert_not_awaited()
        mock_client.get_top_tracks.assert_not_awaited()
        mock_client.get_recently_played.assert_not_awaited()
        mock_client.get_me.assert_not_awaited()


class TestRetryWithBackoff:
    @pytest.mark.asyncio
    async def test_uses_retry_with_backoff(self, mock_client):
        """Verifica che il bundle usa retry_with_backoff, non chiamate dirette."""
        with patch(
            "app.services.data_bundle.retry_with_backoff", new_callable=AsyncMock
        ) as mock_retry:
            mock_retry.return_value = {"items": []}
            bundle = RequestDataBundle(mock_client)

            await bundle.get_top_tracks(time_range="short_term")

            mock_retry.assert_awaited_once_with(
                mock_client.get_top_tracks,
                time_range="short_term",
                limit=50,
            )


class TestClientNotClosed:
    @pytest.mark.asyncio
    async def test_bundle_does_not_close_client(self, bundle, mock_client):
        """Il bundle non chiude il client — responsabilita' del router."""
        await bundle.get_top_tracks()
        await bundle.get_top_artists()
        await bundle.get_recently_played()
        await bundle.get_me()

        mock_client.close.assert_not_awaited()
