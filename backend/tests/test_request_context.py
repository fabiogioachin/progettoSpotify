"""Tests for request context middleware and logging filter."""

import logging


from app.middleware.request_context import (
    RequestContextFilter,
    request_id_var,
    user_id_var,
)


class TestRequestContextFilter:
    """Tests for the logging filter that injects request_id and user_id."""

    def test_filter_adds_request_id(self):
        """Filter adds request_id from contextvar to log record."""
        filt = RequestContextFilter()
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="",
            lineno=0,
            msg="test",
            args=(),
            exc_info=None,
        )

        token = request_id_var.set("abc-123")
        try:
            result = filt.filter(record)
            assert result is True
            assert record.request_id == "abc-123"
        finally:
            request_id_var.reset(token)

    def test_filter_adds_user_id(self):
        """Filter adds user_id from contextvar to log record."""
        filt = RequestContextFilter()
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="",
            lineno=0,
            msg="test",
            args=(),
            exc_info=None,
        )

        token = user_id_var.set(42)
        try:
            result = filt.filter(record)
            assert result is True
            assert record.user_id == 42
        finally:
            user_id_var.reset(token)

    def test_filter_defaults_to_none(self):
        """Without contextvar set, request_id and user_id are None."""
        filt = RequestContextFilter()
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="",
            lineno=0,
            msg="test",
            args=(),
            exc_info=None,
        )

        rid_token = request_id_var.set(None)
        uid_token = user_id_var.set(None)
        try:
            filt.filter(record)
            assert record.request_id is None
            assert record.user_id is None
        finally:
            request_id_var.reset(rid_token)
            user_id_var.reset(uid_token)


class TestExtractUserId:
    """Tests for _extract_user_id helper."""

    def test_no_cookie_returns_none(self):
        from unittest.mock import MagicMock
        from app.middleware.request_context import _extract_user_id

        request = MagicMock()
        request.cookies = {}
        assert _extract_user_id(request) is None

    def test_invalid_cookie_returns_none(self):
        from unittest.mock import MagicMock
        from app.middleware.request_context import _extract_user_id

        request = MagicMock()
        request.cookies = {"session": "garbage.value"}
        assert _extract_user_id(request) is None

    def test_valid_cookie_returns_user_id(self):
        from unittest.mock import MagicMock
        from itsdangerous import URLSafeSerializer
        from app.config import settings
        from app.middleware.request_context import _extract_user_id

        s = URLSafeSerializer(settings.session_secret)
        cookie = s.dumps({"user_id": 7})

        request = MagicMock()
        request.cookies = {"session": cookie}
        assert _extract_user_id(request) == 7
