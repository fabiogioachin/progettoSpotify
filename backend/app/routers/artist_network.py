"""Router per ecosistema artisti e network graph."""

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import require_auth
from app.services.artist_network import build_artist_network
from app.services.spotify_client import SpotifyClient
from app.utils.rate_limiter import SpotifyAuthError

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
    except SpotifyAuthError:
        raise HTTPException(status_code=401, detail="Sessione scaduta")
    finally:
        await client.close()
    return result
