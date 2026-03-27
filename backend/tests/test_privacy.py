"""Tests for privacy / GDPR endpoints."""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

from fastapi.testclient import TestClient
from itsdangerous import URLSafeSerializer

from app.config import settings
from app.database import get_db
from app.main import app


def _make_session_cookie(user_id: int) -> str:
    """Create a signed session cookie for the given user_id."""
    s = URLSafeSerializer(settings.session_secret)
    return s.dumps({"user_id": user_id})


def _mock_db_override(mock_db):
    """Create an async generator that yields mock_db, suitable for dependency override."""

    async def _override():
        yield mock_db

    return _override


class TestDeleteAccount:
    """Tests for DELETE /api/v1/me/data."""

    def test_delete_account_requires_auth(self):
        """Unauthenticated request returns 401."""
        with TestClient(app) as client:
            resp = client.delete("/api/v1/me/data")
            assert resp.status_code == 401

    def test_delete_account_authenticated(self):
        """Authenticated request returns 200 with correct message."""
        cookie = _make_session_cookie(1)

        mock_result = AsyncMock()
        mock_result.rowcount = 5

        mock_db = AsyncMock()
        mock_db.execute = AsyncMock(return_value=mock_result)
        mock_db.commit = AsyncMock()

        app.dependency_overrides[get_db] = _mock_db_override(mock_db)
        try:
            with TestClient(app) as client:
                client.cookies.set("session", cookie)
                resp = client.delete("/api/v1/me/data")
                assert resp.status_code == 200
                data = resp.json()
                assert data["detail"] == "Account eliminato con successo"
        finally:
            app.dependency_overrides.clear()

    def test_delete_calls_correct_number_of_deletes(self):
        """Delete endpoint issues 5 DELETE statements (4 tables + User)."""
        cookie = _make_session_cookie(1)

        mock_result = AsyncMock()
        mock_result.rowcount = 3

        mock_db = AsyncMock()
        mock_db.execute = AsyncMock(return_value=mock_result)
        mock_db.commit = AsyncMock()

        app.dependency_overrides[get_db] = _mock_db_override(mock_db)
        try:
            with TestClient(app) as client:
                client.cookies.set("session", cookie)
                resp = client.delete("/api/v1/me/data")
                assert resp.status_code == 200
                # 4 user-data tables + 1 User delete = 5 calls
                assert mock_db.execute.call_count == 5
                mock_db.commit.assert_called_once()
        finally:
            app.dependency_overrides.clear()


class TestExportData:
    """Tests for GET /api/v1/me/data/export."""

    def test_export_requires_auth(self):
        """Unauthenticated request returns 401."""
        with TestClient(app) as client:
            resp = client.get("/api/v1/me/data/export")
            assert resp.status_code == 401

    def test_export_returns_attachment_header(self):
        """Authenticated export has Content-Disposition attachment."""
        cookie = _make_session_cookie(1)

        mock_scalars = MagicMock()
        mock_scalars.all.return_value = []

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_result.scalars.return_value = mock_scalars

        mock_db = AsyncMock()
        mock_db.execute = AsyncMock(return_value=mock_result)

        app.dependency_overrides[get_db] = _mock_db_override(mock_db)
        try:
            with TestClient(app) as client:
                client.cookies.set("session", cookie)
                resp = client.get("/api/v1/me/data/export")
                assert resp.status_code == 200
                assert "attachment" in resp.headers.get("content-disposition", "")
                assert "wrap-export.json" in resp.headers.get(
                    "content-disposition", ""
                )

                body = resp.json()
                assert "exported_at" in body
                assert "user" in body
                assert "recent_plays" in body
                assert "snapshots" in body
                assert "daily_stats" in body
                assert "profile_metrics" in body
        finally:
            app.dependency_overrides.clear()


class TestSerializeRow:
    """Tests for _serialize_row helper."""

    def test_serialize_datetime(self):
        from app.models.user import User
        from app.routers.privacy import _serialize_row

        user = User(
            id=1,
            spotify_id="test123",
            display_name="Test",
            email="test@test.com",
            created_at=datetime(2024, 1, 1, tzinfo=timezone.utc),
        )
        result = _serialize_row(user)
        assert result["spotify_id"] == "test123"
        assert result["display_name"] == "Test"
        assert isinstance(result["created_at"], str)
        assert "2024-01-01" in result["created_at"]

    def test_serialize_none_values(self):
        from app.models.user import User
        from app.routers.privacy import _serialize_row

        user = User(
            id=2,
            spotify_id="test456",
            display_name=None,
            email=None,
            avatar_url=None,
        )
        result = _serialize_row(user)
        assert result["display_name"] is None
        assert result["email"] is None
