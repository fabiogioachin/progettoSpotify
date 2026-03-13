"""Fallback opzionale per audio features via RapidAPI.

Usato quando un brano non ha preview_url (quindi librosa non puo' analizzarlo).
Se la chiave RapidAPI non e' configurata, ogni chiamata ritorna None immediatamente.
"""

import asyncio
import logging

import httpx

from app.config import settings

logger = logging.getLogger(__name__)

# Semaforo per limitare le chiamate concorrenti a RapidAPI
_sem = asyncio.Semaphore(2)

# Feature keys che ci aspettiamo dal response
_EXPECTED_KEYS = [
    "danceability",
    "energy",
    "valence",
    "acousticness",
    "instrumentalness",
    "liveness",
    "speechiness",
    "tempo",
]


async def fetch_features_rapidapi(
    track_id: str, track_name: str, artist_name: str
) -> dict | None:
    """Recupera audio features da RapidAPI.

    Returns:
        dict con features normalizzate, oppure None se non configurato o in caso di errore.
    """
    if not settings.rapidapi_key:
        return None

    async with _sem:
        try:
            async with httpx.AsyncClient(timeout=10.0) as http:
                resp = await http.get(
                    "https://spotify-scraper.p.rapidapi.com/v1/track/metadata",
                    params={"trackId": track_id},
                    headers={
                        "X-RapidAPI-Key": settings.rapidapi_key,
                        "X-RapidAPI-Host": "spotify-scraper.p.rapidapi.com",
                    },
                )

            if resp.status_code != 200:
                logger.debug(
                    "RapidAPI risposta %d per track %s", resp.status_code, track_id
                )
                return None

            data = resp.json()

            # Normalizza il response nel nostro formato
            features = {}
            for key in _EXPECTED_KEYS:
                val = data.get(key)
                if val is not None:
                    try:
                        features[key] = float(val)
                    except (TypeError, ValueError):
                        pass

            # Deve avere almeno alcune features per essere utile
            if len(features) < 3:
                return None

            return features

        except Exception as exc:
            logger.debug("RapidAPI errore per track %s: %s", track_id, exc)
            return None
