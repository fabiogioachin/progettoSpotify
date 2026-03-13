"""Router per export dati ottimizzato per Claude AI."""

import asyncio
import logging
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import require_auth
from app.services.artist_network import build_artist_network
from app.services.audio_analyzer import compute_profile, compute_trends, get_or_fetch_features
from app.services.prompt_builder import build_claude_prompt
from app.services.spotify_client import SpotifyClient
from app.services.taste_evolution import compute_taste_evolution
from app.services.temporal_patterns import compute_temporal_patterns
from app.utils.rate_limiter import SpotifyAuthError, retry_with_backoff

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/export", tags=["export"])


@router.get("/claude-prompt")
async def generate_claude_prompt(
    request: Request,
    time_range: Literal["short_term", "medium_term", "long_term"] = Query(default="medium_term"),
    user_id: int = Depends(require_auth),
    db: AsyncSession = Depends(get_db),
):
    """Genera il prompt strutturato per analisi con Claude."""
    client = SpotifyClient(db, user_id)

    try:
        # Recupera top tracks con features
        top_data = await retry_with_backoff(
            client.get_top_tracks, time_range=time_range, limit=20
        )
        top_items = top_data.get("items", [])

        # Costruisci lista compatta
        track_ids = [t["id"] for t in top_items]
        features_map = await get_or_fetch_features(db, track_ids)

        top_tracks = []
        for item in top_items:
            t = {
                "name": item["name"],
                "artist": item["artists"][0]["name"] if item.get("artists") else "",
                "popularity": item.get("popularity", 0),
            }
            feat = features_map.get(item["id"])
            if feat:
                t["features"] = feat
            top_tracks.append(t)

        # Profilo e trend
        profile = await compute_profile(db, client, time_range)
        trends = await compute_trends(db, client, user_id)
        genres = profile.get("genres", {})

        # Fetch additional data in parallel (graceful degradation)
        async def safe_taste():
            try:
                return await compute_taste_evolution(client)
            except SpotifyAuthError:
                raise
            except Exception:
                return None

        async def safe_network():
            try:
                return await build_artist_network(client)
            except SpotifyAuthError:
                raise
            except Exception:
                return None

        async def safe_temporal():
            try:
                return await compute_temporal_patterns(client)
            except SpotifyAuthError:
                raise
            except Exception:
                return None

        taste_evo, art_net, temp_pat = await asyncio.gather(
            safe_taste(), safe_network(), safe_temporal()
        )

        # Genera export
        export = build_claude_prompt(
            top_tracks=top_tracks,
            features_profile=profile.get("features", {}),
            trends=trends,
            genres=genres,
            taste_evolution=taste_evo,
            artist_network=art_net,
            temporal_patterns=temp_pat,
        )

    except SpotifyAuthError:
        raise HTTPException(status_code=401, detail="Sessione scaduta")
    except Exception as exc:
        logger.error("Errore nella generazione dell'export: %s", exc)
        raise HTTPException(status_code=500, detail="Errore nella generazione dell'export")
    finally:
        await client.close()

    return export
