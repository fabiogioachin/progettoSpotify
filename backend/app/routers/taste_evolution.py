"""Router per analisi evoluzione del gusto musicale."""

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import require_auth
from app.services.spotify_client import SpotifyClient
from app.services.taste_evolution import compute_taste_evolution
from app.utils.rate_limiter import SpotifyAuthError

router = APIRouter(prefix="/api/taste-evolution", tags=["taste-evolution"])


@router.get("")
async def get_taste_evolution(
    request: Request,
    user_id: int = Depends(require_auth),
    db: AsyncSession = Depends(get_db),
):
    """Analisi dell'evoluzione del gusto attraverso i periodi."""
    client = SpotifyClient(db, user_id)
    try:
        result = await compute_taste_evolution(client)
    except SpotifyAuthError:
        raise HTTPException(status_code=401, detail="Sessione scaduta")
    finally:
        await client.close()
    return result
