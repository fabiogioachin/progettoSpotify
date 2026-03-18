"""Router per pattern temporali di ascolto."""

import logging

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import require_auth
from app.services.spotify_client import SpotifyClient
from app.services.temporal_patterns import compute_temporal_patterns
from app.utils.rate_limiter import RateLimitError, SpotifyAuthError, SpotifyServerError

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/temporal", tags=["temporal"])


@router.get("")
async def get_temporal_patterns(
    request: Request,
    user_id: int = Depends(require_auth),
    db: AsyncSession = Depends(get_db),
):
    """Pattern temporali di ascolto dell'utente."""
    client = SpotifyClient(db, user_id)
    try:
        result = await compute_temporal_patterns(client, db=db, user_id=user_id)
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
