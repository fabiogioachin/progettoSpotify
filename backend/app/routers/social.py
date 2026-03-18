"""Router per il layer social: amicizie, inviti, confronto gusti, leaderboard."""

import logging
import secrets
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import and_, delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import require_auth
from app.models.listening_history import DailyListeningStats, UserProfileMetrics
from app.models.social import Friendship, FriendInviteLink
from app.models.user import User
from app.services.social import compute_compatibility, compute_leaderboard_rankings
from app.services.spotify_client import SpotifyClient
from app.utils.rate_limiter import (
    RateLimitError,
    SpotifyAuthError,
    SpotifyServerError,
    retry_with_backoff,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/social", tags=["social"])


# ---------------------------------------------------------------------------
# POST /api/social/invite — Genera link di invito
# ---------------------------------------------------------------------------
@router.post("/invite")
async def create_invite(
    request: Request,
    user_id: int = Depends(require_auth),
    db: AsyncSession = Depends(get_db),
):
    """Crea un link di invito amicizia con scadenza 7 giorni."""
    code = secrets.token_urlsafe(16)
    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(days=7)

    invite = FriendInviteLink(
        user_id=user_id,
        code=code,
        created_at=now,
        expires_at=expires_at,
        max_uses=1,
        uses=0,
    )
    db.add(invite)
    try:
        await db.commit()
    except Exception as exc:
        await db.rollback()
        logger.exception("Errore creazione invito: %s", exc)
        raise HTTPException(
            status_code=500, detail="Errore nella creazione dell'invito"
        )

    return {"code": code, "expires_at": expires_at.isoformat()}


# ---------------------------------------------------------------------------
# POST /api/social/accept/{code} — Accetta invito
# ---------------------------------------------------------------------------
@router.post("/accept/{code}")
async def accept_invite(
    code: str,
    request: Request,
    user_id: int = Depends(require_auth),
    db: AsyncSession = Depends(get_db),
):
    """Accetta un invito e crea amicizia bidirezionale."""
    # Trova l'invito
    result = await db.execute(
        select(FriendInviteLink).where(FriendInviteLink.code == code)
    )
    invite = result.scalar_one_or_none()

    if not invite:
        raise HTTPException(status_code=404, detail="Codice invito non trovato")

    now = datetime.now(timezone.utc)
    if invite.expires_at < now:
        raise HTTPException(status_code=410, detail="Invito scaduto")

    if invite.uses >= invite.max_uses:
        raise HTTPException(status_code=410, detail="Invito già utilizzato")

    if invite.user_id == user_id:
        raise HTTPException(status_code=400, detail="Non puoi invitare te stesso")

    # Verifica se già amici
    existing = await db.execute(
        select(Friendship).where(
            and_(
                Friendship.user_id == user_id,
                Friendship.friend_id == invite.user_id,
            )
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Siete già amici")

    # Crea amicizia bidirezionale
    db.add(Friendship(user_id=user_id, friend_id=invite.user_id, created_at=now))
    db.add(Friendship(user_id=invite.user_id, friend_id=user_id, created_at=now))
    invite.uses += 1

    try:
        await db.commit()
    except Exception as exc:
        await db.rollback()
        logger.exception("Errore accettazione invito: %s", exc)
        raise HTTPException(
            status_code=500, detail="Errore nell'accettazione dell'invito"
        )

    # Recupera info amico per la risposta
    friend_result = await db.execute(select(User).where(User.id == invite.user_id))
    friend = friend_result.scalar_one_or_none()

    return {
        "friend": {
            "id": friend.id if friend else invite.user_id,
            "display_name": friend.display_name if friend else None,
            "avatar_url": friend.avatar_url if friend else None,
        }
    }


# ---------------------------------------------------------------------------
# GET /api/social/friends — Lista amici
# ---------------------------------------------------------------------------
@router.get("/friends")
async def list_friends(
    request: Request,
    user_id: int = Depends(require_auth),
    db: AsyncSession = Depends(get_db),
):
    """Restituisce la lista amici dell'utente corrente."""
    result = await db.execute(
        select(Friendship, User)
        .join(User, User.id == Friendship.friend_id)
        .where(Friendship.user_id == user_id)
        .order_by(Friendship.created_at.desc())
    )
    rows = result.all()

    friends = []
    for friendship, user in rows:
        friends.append(
            {
                "id": user.id,
                "display_name": user.display_name,
                "avatar_url": user.avatar_url,
                "since": friendship.created_at.isoformat()
                if friendship.created_at
                else None,
            }
        )

    return {"friends": friends}


# ---------------------------------------------------------------------------
# DELETE /api/social/friends/{friend_id} — Rimuovi amicizia
# ---------------------------------------------------------------------------
@router.delete("/friends/{friend_id}")
async def remove_friend(
    friend_id: int,
    request: Request,
    user_id: int = Depends(require_auth),
    db: AsyncSession = Depends(get_db),
):
    """Rimuove l'amicizia bidirezionale."""
    # Elimina entrambe le righe
    result = await db.execute(
        delete(Friendship).where(
            and_(
                Friendship.user_id == user_id,
                Friendship.friend_id == friend_id,
            )
        )
    )
    if result.rowcount == 0:
        raise HTTPException(status_code=404, detail="Amicizia non trovata")
    await db.execute(
        delete(Friendship).where(
            and_(
                Friendship.user_id == friend_id,
                Friendship.friend_id == user_id,
            )
        )
    )

    try:
        await db.commit()
    except Exception as exc:
        await db.rollback()
        logger.exception("Errore rimozione amicizia: %s", exc)
        raise HTTPException(
            status_code=500, detail="Errore nella rimozione dell'amicizia"
        )

    return {"ok": True}


# ---------------------------------------------------------------------------
# GET /api/social/compare/{friend_id} — Confronto gusti
# ---------------------------------------------------------------------------
@router.get("/compare/{friend_id}")
async def compare_taste(
    friend_id: int,
    request: Request,
    user_id: int = Depends(require_auth),
    db: AsyncSession = Depends(get_db),
):
    """Confronta i gusti musicali con un amico."""
    # Verifica amicizia
    friendship = await db.execute(
        select(Friendship).where(
            and_(
                Friendship.user_id == user_id,
                Friendship.friend_id == friend_id,
            )
        )
    )
    if not friendship.scalar_one_or_none():
        raise HTTPException(status_code=403, detail="Non siete amici")

    my_client = SpotifyClient(db, user_id)
    friend_client = SpotifyClient(db, friend_id)
    friend_data_available = True

    try:
        # Fetch my top artists
        my_artists_data = await retry_with_backoff(
            my_client.get_top_artists, time_range="long_term", limit=50
        )

        # Fetch friend's top artists — handle expired token gracefully
        try:
            friend_artists_data = await retry_with_backoff(
                friend_client.get_top_artists, time_range="long_term", limit=50
            )
        except SpotifyAuthError:
            logger.warning("Token amico %d scaduto, confronto parziale", friend_id)
            friend_artists_data = None
            friend_data_available = False

        if not friend_data_available or not friend_artists_data:
            # Dati amico non disponibili — ritorna risposta parziale
            return {
                "friend_data_available": False,
                "score": None,
                "detail": "Il tuo amico deve riautenticarsi per il confronto",
            }

        # Estrai dati per il servizio di compatibilità
        my_artists = my_artists_data.get("items", [])
        friend_artists = friend_artists_data.get("items", [])

        my_data = _extract_user_data(my_artists)
        friend_data = _extract_user_data(friend_artists)

        compatibility = compute_compatibility(my_data, friend_data)
        compatibility["friend_data_available"] = True

        return compatibility

    except (SpotifyAuthError, RateLimitError, SpotifyServerError):
        raise  # Handled by global exception handlers in main.py
    except Exception as exc:
        logger.exception("Errore confronto gusti: %s", exc)
        raise HTTPException(
            status_code=500, detail="Errore nel confronto dei gusti musicali"
        )
    finally:
        await my_client.close()
        await friend_client.close()


def _extract_user_data(artists: list[dict]) -> dict:
    """Estrae top_artists, top_genres, popularity_distribution da una lista artisti Spotify."""
    genres = []
    popularities = []
    for artist in artists:
        genres.extend(artist.get("genres", []))
        pop = artist.get("popularity")
        if pop is not None:
            popularities.append(pop)

    return {
        "top_artists": artists,
        "top_genres": genres,
        "popularity_distribution": popularities,
    }


# ---------------------------------------------------------------------------
# GET /api/social/leaderboard — Classifica amici
# ---------------------------------------------------------------------------
@router.get("/leaderboard")
async def leaderboard(
    request: Request,
    user_id: int = Depends(require_auth),
    db: AsyncSession = Depends(get_db),
):
    """Classifica tra amici per diverse metriche."""
    # Recupera ID amici
    result = await db.execute(
        select(Friendship.friend_id).where(Friendship.user_id == user_id)
    )
    friend_ids = [row[0] for row in result.all()]

    # Includi l'utente corrente nella classifica
    all_user_ids = [user_id] + friend_ids

    # Recupera metriche profilo per tutti
    metrics_result = await db.execute(
        select(UserProfileMetrics, User)
        .join(User, User.id == UserProfileMetrics.user_id)
        .where(UserProfileMetrics.user_id.in_(all_user_ids))
    )
    metrics_rows = metrics_result.all()

    # Recupera nuovi artisti ultimi 30 giorni
    thirty_days_ago = datetime.now(timezone.utc) - timedelta(days=30)
    new_artists_result = await db.execute(
        select(
            DailyListeningStats.user_id,
            func.sum(DailyListeningStats.new_artists_count).label("new_artists_total"),
        )
        .where(
            and_(
                DailyListeningStats.user_id.in_(all_user_ids),
                DailyListeningStats.date >= thirty_days_ago.date(),
            )
        )
        .group_by(DailyListeningStats.user_id)
    )
    new_artists_map = {
        row.user_id: row.new_artists_total or 0 for row in new_artists_result.all()
    }

    # Costruisci lista per il servizio
    friends_metrics = []
    for profile_metrics, user in metrics_rows:
        friends_metrics.append(
            {
                "user_id": user.id,
                "display_name": user.display_name,
                "avatar_url": user.avatar_url,
                "obscurity_score": profile_metrics.obscurity_score or 0,
                "total_plays": profile_metrics.total_plays_lifetime or 0,
                "listening_consistency": profile_metrics.listening_consistency or 0,
                "new_artists_count": new_artists_map.get(user.id, 0),
            }
        )

    return compute_leaderboard_rankings(friends_metrics)
