"""Router per analisi approfondita delle playlist."""

import logging

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import require_auth
from app.services.playlist_analytics import analyze_playlists
from app.services.spotify_client import SpotifyClient
from app.utils.rate_limiter import SpotifyAuthError

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/playlist-analytics", tags=["playlist-analytics"])


@router.get("")
async def get_playlist_analytics(
    request: Request,
    user_id: int = Depends(require_auth),
    db: AsyncSession = Depends(get_db),
):
    """Analisi approfondita delle playlist dell'utente."""
    client = SpotifyClient(db, user_id)
    try:
        result = await analyze_playlists(client)
    except SpotifyAuthError:
        raise HTTPException(status_code=401, detail="Sessione scaduta")
    except Exception as exc:
        logger.error("Errore playlist_analytics: %s", exc)
        raise HTTPException(status_code=500, detail="Errore nell'analisi playlist")
    finally:
        await client.close()
    return result
