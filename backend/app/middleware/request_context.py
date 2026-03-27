"""Request context middleware — injects request_id and user_id into log records."""

import contextvars
import logging
import uuid

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

from app.config import settings

request_id_var: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "request_id", default=None
)
user_id_var: contextvars.ContextVar[int | None] = contextvars.ContextVar(
    "user_id", default=None
)


class RequestContextFilter(logging.Filter):
    """Logging filter that adds request_id and user_id from contextvars to log records."""

    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = request_id_var.get()
        record.user_id = user_id_var.get()
        return True


def _extract_user_id(request: Request) -> int | None:
    """Best-effort extraction of user_id from session cookie."""
    try:
        from itsdangerous import URLSafeSerializer

        cookie = request.cookies.get("session")
        if not cookie:
            return None
        s = URLSafeSerializer(settings.session_secret)
        data = s.loads(cookie)
        return data.get("user_id")
    except Exception:
        return None


class RequestContextMiddleware(BaseHTTPMiddleware):
    """Generates a UUID4 request_id per request and extracts user_id from session cookie.

    Both values are stored in contextvars so all loggers in the call chain pick them up
    via RequestContextFilter.
    """

    async def dispatch(self, request: Request, call_next):
        rid = str(uuid.uuid4())
        uid = _extract_user_id(request)

        request_id_var.set(rid)
        user_id_var.set(uid)

        response = await call_next(request)
        response.headers["X-Request-ID"] = rid
        return response
