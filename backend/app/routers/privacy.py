"""Router privacy / GDPR — eliminazione account e export dati."""

import json
import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Response
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import require_auth
from app.models.listening_history import (
    DailyListeningStats,
    RecentPlay,
    UserProfileMetrics,
    UserSnapshot,
)
from app.models.user import User

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/me", tags=["privacy"])


@router.delete("/data")
async def delete_account(
    response: Response,
    user_id: int = Depends(require_auth),
    db: AsyncSession = Depends(get_db),
):
    """Elimina tutti i dati dell'utente e l'account (GDPR Art. 17 — diritto alla cancellazione)."""
    # Delete all user data in a single transaction (order: dependent tables first)
    tables_with_user_id = [
        RecentPlay,
        UserSnapshot,
        DailyListeningStats,
        UserProfileMetrics,
    ]

    deleted_counts: dict[str, int] = {}
    for model in tables_with_user_id:
        result = await db.execute(delete(model).where(model.user_id == user_id))
        deleted_counts[model.__tablename__] = result.rowcount

    # Delete the user (SpotifyToken cascades via FK ondelete=CASCADE)
    await db.execute(delete(User).where(User.id == user_id))
    deleted_counts["users"] = 1

    await db.commit()

    logger.info(
        "Account eliminato: user_id=%d, righe eliminate=%s",
        user_id,
        deleted_counts,
    )

    # Clear session cookie
    response.delete_cookie("session", path="/")

    return {"detail": "Account eliminato con successo"}


def _serialize_row(row) -> dict:
    """Convert a SQLAlchemy row to a JSON-serializable dict."""
    d = {}
    for col in row.__table__.columns:
        val = getattr(row, col.name)
        if isinstance(val, (datetime,)):
            val = val.isoformat()
        elif hasattr(val, "isoformat"):
            val = val.isoformat()
        d[col.name] = val
    return d


@router.get("/data/export")
async def export_data(
    user_id: int = Depends(require_auth),
    db: AsyncSession = Depends(get_db),
):
    """Esporta tutti i dati dell'utente come JSON (GDPR Art. 20 — portabilita dei dati)."""
    # User profile
    user_result = await db.execute(select(User).where(User.id == user_id))
    user = user_result.scalar_one_or_none()
    user_data = _serialize_row(user) if user else {}

    # Recent plays
    plays_result = await db.execute(
        select(RecentPlay)
        .where(RecentPlay.user_id == user_id)
        .order_by(RecentPlay.played_at.desc())
    )
    recent_plays = [_serialize_row(r) for r in plays_result.scalars().all()]

    # User snapshots
    snapshots_result = await db.execute(
        select(UserSnapshot)
        .where(UserSnapshot.user_id == user_id)
        .order_by(UserSnapshot.captured_at.desc())
    )
    snapshots = [_serialize_row(r) for r in snapshots_result.scalars().all()]

    # Daily listening stats
    stats_result = await db.execute(
        select(DailyListeningStats)
        .where(DailyListeningStats.user_id == user_id)
        .order_by(DailyListeningStats.date.desc())
    )
    daily_stats = [_serialize_row(r) for r in stats_result.scalars().all()]

    # Profile metrics
    metrics_result = await db.execute(
        select(UserProfileMetrics).where(UserProfileMetrics.user_id == user_id)
    )
    profile_metrics = [_serialize_row(r) for r in metrics_result.scalars().all()]

    export = {
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "user": user_data,
        "recent_plays": recent_plays,
        "snapshots": snapshots,
        "daily_stats": daily_stats,
        "profile_metrics": profile_metrics,
    }

    content = json.dumps(export, ensure_ascii=False, indent=2)

    return Response(
        content=content,
        media_type="application/json",
        headers={
            "Content-Disposition": 'attachment; filename="wrap-export.json"',
        },
    )
