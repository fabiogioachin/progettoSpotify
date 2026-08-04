"""Copertine dei brani: lettura dalla cache e riempimento in sottofondo.

La cronologia degli ascolti salva titolo, artista e orario, non l'immagine
dell'album. Le classifiche costruite su quegli ascolti resterebbero quindi senza
copertine. Qui si legge la cache (zero chiamate a Spotify) e, per i brani che
mancano, si riempie in sottofondo un brano alla volta: l'endpoint batch dei
brani non e' piu' disponibile in modalita' sviluppo, quindi serve una chiamata
per brano e conviene farla fuori dalla richiesta dell'utente.
"""

import asyncio
import logging

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import async_session
from app.models.track import TrackMetadata
from app.services.spotify_client import SpotifyClient
from app.utils.rate_limiter import (
    RateLimitError,
    SpotifyAuthError,
    SpotifyServerError,
    ThrottleError,
    retry_with_backoff,
)

logger = logging.getLogger(__name__)

# Tempo fra una chiamata e l'altra. Il limite vero e' 25 chiamate ogni 30
# secondi, condiviso con tutto il resto: 1,5 secondi lascia margine alle
# pagine che l'utente sta guardando adesso.
FETCH_DELAY_SECONDS = 1.5

# Quanti brani riempire per volta. Sono i primi della classifica, quelli che
# l'utente vede senza scorrere; il resto arriva alla visita successiva.
MAX_PER_RUN = 50

# Utenti con un riempimento gia' in corso. La pagina richiede la lista ogni
# quindici secondi finche' le copertine non ci sono tutte: senza questo, ogni
# richiesta lancerebbe un'altra coda sugli stessi brani e le code si
# moltiplicherebbero contro lo stesso limite di chiamate.
_running: set[int] = set()


async def read_track_images(db: AsyncSession, track_ids: list[str]) -> dict[str, dict]:
    """Legge dalla cache DB album e copertina dei brani richiesti.

    Ritorna solo i brani gia' in cache. Nessuna chiamata a Spotify.
    """
    if not track_ids:
        return {}

    result = await db.execute(
        select(TrackMetadata).where(TrackMetadata.track_spotify_id.in_(track_ids))
    )
    return {
        row.track_spotify_id: {
            "album": row.album_name,
            "album_image": row.album_image,
            "preview_url": row.preview_url,
        }
        for row in result.scalars().all()
    }


async def _upsert(db: AsyncSession, track_id: str, item: dict | None) -> None:
    """Scrive la riga anche quando Spotify non ha immagine, per non richiederla ancora."""
    album = (item or {}).get("album") or {}
    images = album.get("images") or []
    values = {
        "track_spotify_id": track_id,
        "album_name": album.get("name"),
        "album_image": images[0].get("url") if images else None,
        "preview_url": (item or {}).get("preview_url"),
    }
    stmt = pg_insert(TrackMetadata).values(**values)
    await db.execute(
        stmt.on_conflict_do_update(
            index_elements=["track_spotify_id"],
            set_={k: v for k, v in values.items() if k != "track_spotify_id"},
        )
    )
    await db.commit()


async def fetch_missing_images(user_id: int, track_ids: list[str]) -> None:
    """Riempie le copertine mancanti, un brano alla volta, in sottofondo.

    Usa sessione DB e client dedicati: gira dopo che la richiesta e' finita.
    """
    if not track_ids:
        return

    if user_id in _running:
        logger.debug("BG copertine: riempimento gia' in corso per user_id=%d", user_id)
        return
    _running.add(user_id)

    logger.info(
        "BG copertine: %d brani da recuperare per user_id=%d",
        len(track_ids),
        user_id,
    )

    fetched = 0
    try:
        async with async_session() as db:
            client = SpotifyClient(db, user_id)
            try:
                for track_id in track_ids[:MAX_PER_RUN]:
                    try:
                        item = await retry_with_backoff(client.get_track, track_id)
                        await _upsert(db, track_id, item)
                        fetched += 1
                    except (ThrottleError, RateLimitError):
                        # Finestra piena: si riprende alla prossima visita.
                        logger.info(
                            "BG copertine: fermato dal limite dopo %d brani", fetched
                        )
                        break
                    except SpotifyAuthError:
                        logger.warning("BG copertine: sessione Spotify scaduta")
                        break
                    except SpotifyServerError as exc:
                        logger.warning(
                            "BG copertine: errore Spotify su %s: %s", track_id, exc
                        )
                    except Exception as exc:
                        # Un brano sparito o senza album non deve fermare gli altri.
                        logger.warning(
                            "BG copertine: %s non recuperato: %s", track_id, exc
                        )
                    await asyncio.sleep(FETCH_DELAY_SECONDS)
            finally:
                await client.close()
    except Exception as exc:
        logger.warning("BG copertine: interrotto: %s", exc)
    finally:
        _running.discard(user_id)

    logger.info("BG copertine: %d recuperate per user_id=%d", fetched, user_id)
