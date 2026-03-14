"""Router per analisi evoluzione del gusto musicale."""

import logging

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import require_auth
from app.services.spotify_client import SpotifyClient
from app.services.taste_evolution import compute_taste_evolution
from app.utils.rate_limiter import RateLimitError, SpotifyAuthError, SpotifyServerError

logger = logging.getLogger(__name__)
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
    except RateLimitError as e:
        from app.utils.rate_limiter import ThrottleError

        is_throttle = isinstance(e, ThrottleError)
        raise HTTPException(
            status_code=429,
            detail={
                "message": "Carico API elevato — dati in arrivo tra poco"
                if is_throttle
                else "Troppe richieste a Spotify, riprova tra poco",
                "throttled": is_throttle,
                "retry_after": round(e.retry_after or 5, 1),
            },
            headers={"Retry-After": str(int(e.retry_after or 5))},
        )
    except SpotifyServerError:
        raise HTTPException(status_code=502, detail="Spotify non disponibile")
    except Exception as exc:
        logger.error("Errore taste_evolution: %s", exc)
        raise HTTPException(
            status_code=500, detail="Errore nell'analisi evoluzione gusto"
        )
    finally:
        await client.close()
    return result
