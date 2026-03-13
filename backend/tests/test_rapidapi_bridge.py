"""Test per rapidapi_bridge.py."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.rapidapi_bridge import fetch_features_rapidapi


class TestFetchFeaturesRapidapi:
    """Test fetch_features_rapidapi."""

    @pytest.mark.asyncio
    async def test_returns_none_when_no_key(self):
        """Se rapidapi_key e' vuoto, deve restituire None immediatamente."""
        with patch("app.services.rapidapi_bridge.settings") as mock_settings:
            mock_settings.rapidapi_key = ""
            result = await fetch_features_rapidapi("track123", "Test Song", "Test Artist")
            assert result is None

    @pytest.mark.asyncio
    async def test_returns_none_on_http_error(self):
        """Su errore HTTP, deve restituire None."""
        mock_response = MagicMock()
        mock_response.status_code = 500

        with patch("app.services.rapidapi_bridge.settings") as mock_settings, \
             patch("app.services.rapidapi_bridge.httpx.AsyncClient") as mock_client_cls:
            mock_settings.rapidapi_key = "test-key"

            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_client_cls.return_value = mock_client

            result = await fetch_features_rapidapi("track123", "Test Song", "Test Artist")
            assert result is None

    @pytest.mark.asyncio
    async def test_returns_none_on_insufficient_features(self):
        """Se il response ha meno di 3 features, deve restituire None."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"energy": 0.5}

        with patch("app.services.rapidapi_bridge.settings") as mock_settings, \
             patch("app.services.rapidapi_bridge.httpx.AsyncClient") as mock_client_cls:
            mock_settings.rapidapi_key = "test-key"

            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_client_cls.return_value = mock_client

            result = await fetch_features_rapidapi("track123", "Test Song", "Test Artist")
            assert result is None

    @pytest.mark.asyncio
    async def test_returns_features_on_success(self):
        """Su response valido con 3+ features, restituisce dict."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "energy": 0.8,
            "danceability": 0.6,
            "valence": 0.7,
            "tempo": 120.0,
        }

        with patch("app.services.rapidapi_bridge.settings") as mock_settings, \
             patch("app.services.rapidapi_bridge.httpx.AsyncClient") as mock_client_cls:
            mock_settings.rapidapi_key = "test-key"

            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_client_cls.return_value = mock_client

            result = await fetch_features_rapidapi("track123", "Test Song", "Test Artist")
            assert result is not None
            assert result["energy"] == 0.8
            assert result["danceability"] == 0.6
            assert result["valence"] == 0.7
            assert result["tempo"] == 120.0

    @pytest.mark.asyncio
    async def test_returns_none_on_exception(self):
        """Su eccezione, deve restituire None."""
        with patch("app.services.rapidapi_bridge.settings") as mock_settings, \
             patch("app.services.rapidapi_bridge.httpx.AsyncClient") as mock_client_cls:
            mock_settings.rapidapi_key = "test-key"

            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client.get = AsyncMock(side_effect=Exception("Network error"))
            mock_client_cls.return_value = mock_client

            result = await fetch_features_rapidapi("track123", "Test Song", "Test Artist")
            assert result is None
