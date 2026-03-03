"""Dependency injection condivise per i router FastAPI."""

from typing import Literal

from fastapi import Depends, HTTPException, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.constants import TIME_RANGES
from app.database import get_db
from app.services.spotify_client import SpotifyClient


def get_session_user_id(request: Request) -> int | None:
    """Legge l'ID utente dalla sessione firmata nel cookie."""
    from itsdangerous import BadSignature, URLSafeSerializer

    cookie = request.cookies.get("session")
    if not cookie:
        return None
    s = URLSafeSerializer(settings.session_secret)
    try:
        data = s.loads(cookie)
        return data.get("user_id")
    except BadSignature:
        return None


def require_auth(request: Request) -> int:
    """Dependency che richiede autenticazione. Solleva 401 se non autenticato."""
    user_id = get_session_user_id(request)
    if not user_id:
        raise HTTPException(status_code=401, detail="Non autenticato")
    return user_id
