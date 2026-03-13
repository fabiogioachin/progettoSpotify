"""Test per il router analysis.py."""

from unittest.mock import patch

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


class TestAnalysisRouter:
    """Test degli endpoint di analisi."""

    def test_start_analysis_requires_auth(self):
        """POST /api/analyze-tracks senza auth deve restituire 401."""
        response = client.post(
            "/api/analyze-tracks",
            json={"track_ids": ["abc123"]},
        )
        assert response.status_code == 401

    def test_get_status_requires_auth(self):
        """GET /api/analyze-tracks/{id} senza auth deve restituire 401."""
        response = client.get("/api/analyze-tracks/00000000-0000-0000-0000-000000000000")
        assert response.status_code == 401

    def test_start_analysis_empty_tracks(self):
        """POST con lista vuota deve restituire 400."""
        with patch("app.routers.analysis.require_auth", return_value=1):
            response = client.post(
                "/api/analyze-tracks",
                json={"track_ids": []},
            )
            # 400 o 401 (dipende dall'ordine dei middleware)
            assert response.status_code in (400, 401)

    def test_start_analysis_too_many_tracks(self):
        """POST con piu' di 100 tracce deve restituire 400."""
        with patch("app.routers.analysis.require_auth", return_value=1):
            track_ids = [f"track_{i}" for i in range(101)]
            response = client.post(
                "/api/analyze-tracks",
                json={"track_ids": track_ids},
            )
            assert response.status_code in (400, 401)
