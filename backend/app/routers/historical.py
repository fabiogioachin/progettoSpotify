"""Router per dati storici annuali."""

import logging

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import require_auth
from app.services.historical_tops import get_historical_top_songs
from app.services.spotify_client import SpotifyClient
from app.utils.rate_limiter import SpotifyAuthError

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["historical"])


@router.get("/historical-tops")
async def historical_tops(
    request: Request,
    user_id: int = Depends(require_auth),
    db: AsyncSession = Depends(get_db),
):
    """Recupera storico annuale dalle playlist 'Your Top Songs'."""
    client = SpotifyClient(db, user_id)
    try:
        result = await get_historical_top_songs(client)
    except SpotifyAuthError:
        raise HTTPException(status_code=401, detail="Sessione scaduta")
    except Exception as exc:
        logger.error("Errore historical_tops: %s", exc)
        raise HTTPException(status_code=500, detail="Errore nel caricamento storico")
    finally:
        await client.close()
    return result
