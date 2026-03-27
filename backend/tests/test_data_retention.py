"""Tests for data retention cleanup job."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


class TestCleanupExpiredData:
    """Tests for cleanup_expired_data service."""

    @pytest.mark.asyncio
    async def test_cleanup_deletes_expired_records(self):
        """Verify cleanup issues DELETE for all three tables."""
        mock_result = MagicMock()
        mock_result.rowcount = 10

        mock_session = AsyncMock()
        mock_session.execute = AsyncMock(return_value=mock_result)
        mock_session.commit = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)

        with patch(
            "app.services.data_retention.async_session", return_value=mock_session
        ):
            from app.services.data_retention import cleanup_expired_data

            await cleanup_expired_data()

        # 2 DELETE statements (user_snapshots, track_popularity)
        assert mock_session.execute.call_count == 2
        mock_session.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_cleanup_logs_counts(self):
        """Verify cleanup logs deleted row counts."""
        mock_result = MagicMock()
        mock_result.rowcount = 0

        mock_session = AsyncMock()
        mock_session.execute = AsyncMock(return_value=mock_result)
        mock_session.commit = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)

        with (
            patch(
                "app.services.data_retention.async_session", return_value=mock_session
            ),
            patch("app.services.data_retention.logger") as mock_logger,
        ):
            from app.services.data_retention import cleanup_expired_data

            await cleanup_expired_data()

        mock_logger.info.assert_called_once()
        log_msg = mock_logger.info.call_args[0][0]
        assert "Pulizia dati scaduti completata" in log_msg
