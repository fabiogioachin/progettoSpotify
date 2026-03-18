"""Router per ecosistema artisti e network graph."""

import logging

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import require_auth
from app.services.artist_network import build_artist_network
from app.services.spotify_client import SpotifyClient
from app.utils.json_utils import sanitize_nans
from app.utils.rate_limiter import RateLimitError, SpotifyAuthError, SpotifyServerError

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/artist-network", tags=["artist-network"])


@router.get("")
async def get_artist_network(
    request: Request,
    user_id: int = Depends(require_auth),
    db: AsyncSession = Depends(get_db),
):
    """Grafo di artisti correlati con cluster e bridge artists."""
    client = SpotifyClient(db, user_id)
    try:
        result = await build_artist_network(client)
    except (SpotifyAuthError, RateLimitError, SpotifyServerError):
        raise  # Handled by global exception handlers in main.py
    except Exception as exc:
        logger.error("Errore artist_network: %s", exc)
        raise HTTPException(status_code=500, detail="Errore nel grafo artisti")
    finally:
        await client.close()
    return sanitize_nans(result)
