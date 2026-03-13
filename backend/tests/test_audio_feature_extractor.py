"""Test per audio_feature_extractor.py — unit test senza dipendenze esterne."""

from unittest.mock import AsyncMock, MagicMock, patch

import numpy as np
import pytest

from app.services.audio_feature_extractor import (
    _analyze_audio,
    extract_features_from_url,
)


class TestAnalyzeAudio:
    """Test _analyze_audio con audio sintetico."""

    def test_returns_all_expected_keys(self, tmp_path):
        """Verifica che vengano restituite tutte le feature attese."""
        import soundfile as sf

        # Genera audio sintetico: sinusoide 440Hz, 2 secondi
        sr = 22050
        duration = 2.0
        t = np.linspace(0, duration, int(sr * duration), endpoint=False)
        y = 0.3 * np.sin(2 * np.pi * 440 * t).astype(np.float32)

        filepath = str(tmp_path / "test.wav")
        sf.write(filepath, y, sr)

        features = _analyze_audio(filepath)

        expected_keys = [
            "energy",
            "danceability",
            "valence",
            "acousticness",
            "instrumentalness",
            "speechiness",
            "liveness",
            "tempo",
        ]
        for key in expected_keys:
            assert key in features, f"Manca la feature: {key}"

    def test_features_in_valid_range(self, tmp_path):
        """Verifica che le feature 0-1 siano nell'intervallo corretto."""
        import soundfile as sf

        sr = 22050
        duration = 2.0
        t = np.linspace(0, duration, int(sr * duration), endpoint=False)
        y = 0.3 * np.sin(2 * np.pi * 440 * t).astype(np.float32)

        filepath = str(tmp_path / "test.wav")
        sf.write(filepath, y, sr)

        features = _analyze_audio(filepath)

        for key in ["energy", "danceability", "valence", "acousticness",
                     "instrumentalness", "speechiness", "liveness"]:
            assert 0 <= features[key] <= 1, f"{key} fuori range: {features[key]}"

        assert 60 <= features["tempo"] <= 200, f"tempo fuori range: {features['tempo']}"

    def test_empty_audio_returns_empty(self, tmp_path):
        """Audio vuoto deve restituire dict vuoto."""
        import soundfile as sf

        filepath = str(tmp_path / "empty.wav")
        sf.write(filepath, np.array([], dtype=np.float32), 22050)

        features = _analyze_audio(filepath)
        assert features == {}


class TestExtractFeaturesFromUrl:
    """Test extract_features_from_url con mock HTTP."""

    @pytest.mark.asyncio
    async def test_returns_none_on_empty_url(self):
        result = await extract_features_from_url("")
        assert result is None

    @pytest.mark.asyncio
    async def test_returns_none_on_http_error(self):
        mock_response = MagicMock()
        mock_response.status_code = 404

        with patch("app.services.audio_feature_extractor.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_client_cls.return_value = mock_client

            result = await extract_features_from_url("https://example.com/preview.mp3")
            assert result is None

    @pytest.mark.asyncio
    async def test_returns_none_on_exception(self):
        with patch("app.services.audio_feature_extractor.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client.get = AsyncMock(side_effect=Exception("Connection error"))
            mock_client_cls.return_value = mock_client

            result = await extract_features_from_url("https://example.com/preview.mp3")
            assert result is None
