"""Dependency injection condivise per i router FastAPI."""

from fastapi import HTTPException, Request

from app.config import settings


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


async def require_admin(request: Request) -> int:
    """Dependency che richiede admin. Solleva 403 se non admin."""
    user_id = require_auth(request)

    from sqlalchemy import select

    from app.database import async_session
    from app.models.user import User

    async with async_session() as session:
        user = (
            await session.execute(select(User).where(User.id == user_id))
        ).scalar_one_or_none()
        if not user or not user.is_admin:
            raise HTTPException(
                status_code=403, detail="Accesso riservato agli amministratori"
            )
    return user_id
