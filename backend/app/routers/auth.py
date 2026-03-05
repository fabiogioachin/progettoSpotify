"""Router autenticazione OAuth Spotify."""

import asyncio
import hmac
import logging
import secrets
from datetime import datetime, timedelta, timezone

import httpx
from fastapi import APIRouter, Depends, Request, Response
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.dependencies import get_session_user_id
from app.models.user import SpotifyToken, User
from app.services.background_tasks import save_daily_snapshot
from app.services.spotify_client import SCOPES, SPOTIFY_AUTH_URL, SPOTIFY_TOKEN_URL
from app.utils.token_manager import encrypt_token

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["auth"])


def set_session_cookie(response: Response, user_id: int):
    """Imposta il cookie di sessione firmato."""
    from itsdangerous import URLSafeSerializer

    s = URLSafeSerializer(settings.session_secret)
    cookie_value = s.dumps({"user_id": user_id})
    response.set_cookie(
        key="session",
        value=cookie_value,
        httponly=True,
        samesite="lax",
        secure=settings.cookie_secure,
        max_age=60 * 60 * 24 * 30,  # 30 giorni
        path="/",
    )


@router.get("/spotify/login")
async def spotify_login(request: Request):
    """Redirect a Spotify per autorizzazione OAuth."""
    state = secrets.token_urlsafe(32)

    # Salva state nel cookie temporaneo
    params = {
        "client_id": settings.spotify_client_id,
        "response_type": "code",
        "redirect_uri": settings.spotify_redirect_uri,
        "scope": " ".join(SCOPES),
        "state": state,
        "show_dialog": "false",
    }
    auth_url = f"{SPOTIFY_AUTH_URL}?{'&'.join(f'{k}={v}' for k, v in params.items())}"

    response = RedirectResponse(url=auth_url)
    response.set_cookie(
        key="oauth_state",
        value=state,
        httponly=True,
        samesite="lax",
        max_age=600,
        path="/",
    )
    return response


@router.get("/spotify/callback")
async def spotify_callback(
    request: Request,
    code: str | None = None,
    state: str | None = None,
    error: str | None = None,
    db: AsyncSession = Depends(get_db),
):
    """Callback OAuth Spotify — scambia code per token e crea sessione."""
    if error:
        return RedirectResponse(url=f"{settings.frontend_url}?error={error}")

    # Verifica state (timing-safe comparison)
    stored_state = request.cookies.get("oauth_state")
    if not state or not stored_state or not hmac.compare_digest(state, stored_state):
        return RedirectResponse(url=f"{settings.frontend_url}?error=state_mismatch")

    # Scambia code per token
    async with httpx.AsyncClient() as client:
        token_resp = await client.post(
            SPOTIFY_TOKEN_URL,
            data={
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": settings.spotify_redirect_uri,
                "client_id": settings.spotify_client_id,
                "client_secret": settings.spotify_client_secret,
            },
        )

    if token_resp.status_code != 200:
        return RedirectResponse(url=f"{settings.frontend_url}?error=token_exchange_failed")

    token_data = token_resp.json()
    access_token = token_data["access_token"]
    refresh_token = token_data["refresh_token"]
    expires_in = token_data["expires_in"]

    # Ottieni profilo utente (retry su 429 con Retry-After)
    profile_resp = None
    async with httpx.AsyncClient() as client:
        for attempt in range(3):
            profile_resp = await client.get(
                "https://api.spotify.com/v1/me",
                headers={"Authorization": f"Bearer {access_token}"},
            )
            if profile_resp.status_code == 429:
                retry_after = int(profile_resp.headers.get("Retry-After", 2))
                await asyncio.sleep(min(retry_after, 5))
                continue
            break

    if profile_resp is None or profile_resp.status_code != 200:
        return RedirectResponse(url=f"{settings.frontend_url}?error=profile_fetch_failed")

    profile = profile_resp.json()
    spotify_id = profile["id"]

    # Crea o aggiorna utente
    result = await db.execute(select(User).where(User.spotify_id == spotify_id))
    user = result.scalar_one_or_none()

    if not user:
        user = User(
            spotify_id=spotify_id,
            display_name=profile.get("display_name"),
            email=profile.get("email"),
            avatar_url=(profile.get("images", [{}])[0].get("url") if profile.get("images") else None),
            country=profile.get("country"),
        )
        db.add(user)
        await db.flush()
    else:
        user.display_name = profile.get("display_name")
        user.email = profile.get("email")
        user.avatar_url = (profile.get("images", [{}])[0].get("url") if profile.get("images") else None)
        user.updated_at = datetime.now(timezone.utc)

    # Salva/aggiorna token
    result = await db.execute(select(SpotifyToken).where(SpotifyToken.user_id == user.id))
    token_record = result.scalar_one_or_none()

    expires_at = datetime.now(timezone.utc) + timedelta(seconds=expires_in)

    if not token_record:
        token_record = SpotifyToken(
            user_id=user.id,
            access_token_encrypted=encrypt_token(access_token),
            refresh_token_encrypted=encrypt_token(refresh_token),
            expires_at=expires_at,
            scope=" ".join(SCOPES),
        )
        db.add(token_record)
    else:
        token_record.access_token_encrypted = encrypt_token(access_token)
        token_record.refresh_token_encrypted = encrypt_token(refresh_token)
        token_record.expires_at = expires_at
        token_record.updated_at = datetime.now(timezone.utc)

    await db.commit()

    # Imposta cookie di sessione e redirect al frontend
    response = RedirectResponse(url=settings.frontend_url)
    set_session_cookie(response, user.id)
    response.delete_cookie("oauth_state", path="/")
    return response


@router.get("/me")
async def get_current_user(request: Request, db: AsyncSession = Depends(get_db)):
    """Ritorna il profilo dell'utente corrente dalla sessione."""
    user_id = get_session_user_id(request)
    if not user_id:
        return {"authenticated": False}

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()

    if not user:
        return {"authenticated": False}

    # Snapshot giornaliero (non-blocking, best-effort)
    asyncio.create_task(_try_daily_snapshot(user.id))

    return {
        "authenticated": True,
        "user": {
            "id": user.id,
            "spotify_id": user.spotify_id,
            "display_name": user.display_name,
            "email": user.email,
            "avatar_url": user.avatar_url,
            "country": user.country,
        },
    }


async def _try_daily_snapshot(user_id: int):
    """Wrapper non-blocking per save_daily_snapshot."""
    try:
        await save_daily_snapshot(user_id)
    except Exception as exc:
        logger.warning("Daily snapshot fallito per user_id=%d: %s", user_id, exc)


@router.post("/logout")
async def logout(response: Response):
    """Cancella il cookie di sessione."""
    response = RedirectResponse(url=settings.frontend_url, status_code=302)
    response.delete_cookie("session", path="/")
    return response
