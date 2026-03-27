"""Router di amministrazione — solo admin."""

import asyncio
import logging
import secrets
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import async_session, get_db
from app.dependencies import require_admin
from app.models.listening_history import RecentPlay
from app.models.social import InviteCode
from app.models.user import SpotifyToken, User
from app.services.api_budget import Priority
from app.services.background_tasks import _sync_user_recent_plays
from app.services.spotify_client import SpotifyClient

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/admin", tags=["admin"])


@router.get("/users")
async def list_users(
    admin_id: int = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Lista tutti gli utenti con statistiche."""
    # Fetch users with token updated_at and play count via subqueries
    token_sub = select(
        SpotifyToken.user_id, SpotifyToken.updated_at.label("last_active")
    ).subquery()
    plays_sub = (
        select(
            RecentPlay.user_id,
            func.count(RecentPlay.id).label("total_plays"),
        )
        .group_by(RecentPlay.user_id)
        .subquery()
    )

    result = await db.execute(
        select(
            User,
            token_sub.c.last_active,
            plays_sub.c.total_plays,
        )
        .outerjoin(token_sub, User.id == token_sub.c.user_id)
        .outerjoin(plays_sub, User.id == plays_sub.c.user_id)
        .order_by(User.created_at.desc())
    )

    users = []
    for row in result.all():
        user = row[0]
        last_active = row[1]
        total_plays = row[2] or 0
        users.append(
            {
                "id": user.id,
                "spotify_id": user.spotify_id,
                "display_name": user.display_name,
                "email": user.email,
                "is_admin": user.is_admin,
                "tier": user.tier,
                "onboarding_completed": user.onboarding_completed,
                "created_at": user.created_at.isoformat() if user.created_at else None,
                "last_active": last_active.isoformat() if last_active else None,
                "total_plays": total_plays,
            }
        )
    return users


@router.get("/invites")
async def list_invites(
    admin_id: int = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Lista tutti i codici di invito."""
    result = await db.execute(select(InviteCode).order_by(InviteCode.created_at.desc()))
    invites = result.scalars().all()
    return [
        {
            "id": inv.id,
            "code": inv.code,
            "created_by": inv.created_by,
            "uses": inv.uses,
            "max_uses": inv.max_uses,
            "expires_at": inv.expires_at.isoformat() if inv.expires_at else None,
            "created_at": inv.created_at.isoformat() if inv.created_at else None,
        }
        for inv in invites
    ]


@router.post("/invites")
async def create_invite(
    request: Request,
    admin_id: int = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Crea un nuovo codice di invito."""
    body = await request.json()
    max_uses = body.get("max_uses", 1)
    expires_days = body.get("expires_days")

    code = secrets.token_urlsafe(24)
    expires_at = None
    if expires_days is not None:
        expires_at = datetime.now(timezone.utc) + timedelta(days=expires_days)

    invite = InviteCode(
        code=code,
        created_by=admin_id,
        max_uses=max_uses,
        expires_at=expires_at,
    )
    db.add(invite)
    await db.commit()

    return {
        "code": code,
        "max_uses": max_uses,
        "expires_at": expires_at.isoformat() if expires_at else None,
    }


@router.get("/api-usage")
async def api_usage(
    admin_id: int = Depends(require_admin),
):
    """Statistiche utilizzo API da Redis."""
    try:
        from app.services.redis_client import get_redis

        redis = get_redis()
        # Scan for per-user rate limit keys
        usage = {}
        async for key in redis.scan_iter(match="ratelimit:user:*:pages"):
            parts = key.split(":")
            if len(parts) >= 3:
                uid = parts[2]
                count = await redis.zcard(key)
                usage[uid] = count
        return {"per_user": usage}
    except Exception:
        return {"per_user": {}}


@router.get("/jobs")
async def list_jobs(
    admin_id: int = Depends(require_admin),
):
    """Lista job APScheduler attivi."""
    from app.main import scheduler  # lazy import to avoid circular

    jobs = []
    for job in scheduler.get_jobs():
        jobs.append(
            {
                "id": job.id,
                "name": job.name,
                "next_run": str(job.next_run_time) if job.next_run_time else None,
            }
        )
    return jobs


@router.post("/users/{user_id}/suspend")
async def suspend_user(
    user_id: int,
    admin_id: int = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Sospendi utente eliminando il suo token Spotify (forza re-auth)."""
    if user_id == admin_id:
        raise HTTPException(status_code=400, detail="Non puoi sospendere te stesso")

    # Check target user exists and is not admin
    target = (
        await db.execute(select(User).where(User.id == user_id))
    ).scalar_one_or_none()
    if not target:
        raise HTTPException(status_code=404, detail="Utente non trovato")
    if target.is_admin:
        raise HTTPException(
            status_code=400, detail="Non puoi sospendere un altro admin"
        )

    # Delete token
    token = (
        await db.execute(select(SpotifyToken).where(SpotifyToken.user_id == user_id))
    ).scalar_one_or_none()
    if token:
        await db.delete(token)
        await db.commit()
        logger.info("Admin %d ha sospeso user_id=%d", admin_id, user_id)
        return {"detail": "Utente sospeso — token eliminato"}

    return {"detail": "Utente non aveva un token attivo"}


@router.post("/users/{user_id}/force-sync")
async def force_sync(
    user_id: int,
    admin_id: int = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Forza sync ascolti recenti per un utente."""
    # Verify user exists
    target = (
        await db.execute(select(User).where(User.id == user_id))
    ).scalar_one_or_none()
    if not target:
        raise HTTPException(status_code=404, detail="Utente non trovato")

    # Check token exists
    token = (
        await db.execute(select(SpotifyToken).where(SpotifyToken.user_id == user_id))
    ).scalar_one_or_none()
    if not token:
        raise HTTPException(status_code=400, detail="Utente non ha un token attivo")

    async def _run_sync():
        try:
            async with async_session() as session:
                client = SpotifyClient(
                    session, user_id, priority=Priority.P1_BACKGROUND_SYNC
                )
                try:
                    await _sync_user_recent_plays(session, user_id, client)
                finally:
                    await client.close()
        except Exception as exc:
            logger.warning(
                "Force-sync fallito per user_id=%d (richiesto da admin=%d): %s",
                user_id,
                admin_id,
                exc,
            )

    asyncio.create_task(_run_sync())
    logger.info("Admin %d ha avviato force-sync per user_id=%d", admin_id, user_id)
    return {"detail": "Sync avviato in background"}
