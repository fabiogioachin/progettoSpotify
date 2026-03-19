"""Router per pattern temporali di ascolto."""

import logging
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import require_auth
from app.services.spotify_client import SpotifyClient
from app.services.temporal_patterns import compute_temporal_patterns
from app.utils.rate_limiter import RateLimitError, SpotifyAuthError, SpotifyServerError

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/temporal", tags=["temporal"])

_DAYS_MAP = {"7d": 7, "30d": 30, "90d": 90, "all": 365}


@router.get("")
async def get_temporal_patterns(
    request: Request,
    range: Literal["7d", "30d", "90d", "all"] = Query(default="30d"),
    user_id: int = Depends(require_auth),
    db: AsyncSession = Depends(get_db),
):
    """Pattern temporali di ascolto dell'utente."""
    days = _DAYS_MAP[range]
    client = SpotifyClient(db, user_id)
    try:
        result = await compute_temporal_patterns(
            client, db=db, user_id=user_id, days=days
        )
    except (SpotifyAuthError, RateLimitError, SpotifyServerError):
        raise  # Handled by global exception handlers in main.py
    except Exception as exc:
        logger.error("Errore temporal_patterns: %s", exc)
        raise HTTPException(
            status_code=500, detail="Errore nell'analisi pattern temporali"
        )
    finally:
        await client.close()
    return result
