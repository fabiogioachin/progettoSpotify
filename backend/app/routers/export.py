"""Router per export dati ottimizzato per Claude AI."""

from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import require_auth
from app.services.audio_analyzer import compute_profile, compute_trends
from app.services.prompt_builder import build_claude_prompt
from app.services.spotify_client import SpotifyClient
from app.utils.rate_limiter import SpotifyAuthError, retry_with_backoff

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
        from app.routers.library import _get_or_fetch_features

        track_ids = [t["id"] for t in top_items]
        features_map = await _get_or_fetch_features(db, client, track_ids)

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

        # Genera export
        export = build_claude_prompt(
            top_tracks=top_tracks,
            features_profile=profile.get("features", {}),
            trends=trends,
            genres=genres,
        )

    except SpotifyAuthError:
        raise HTTPException(status_code=401, detail="Sessione scaduta")
    finally:
        await client.close()

    return export
