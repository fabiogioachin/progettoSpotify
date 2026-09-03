"""Cache condivisa della classifica mondiale e del peso mondiale dei brani.

Il dato e' identico per ogni utente, quindi la cache non ha mai una chiave per
utente: e' la regola che la skill `spotify-api-budget` impone per tutto cio' che
non dipende da chi guarda.

Due garanzie che vale la pena dichiarare, perche' sono quelle che tengono in
piedi la card nei giorni storti:

1. **Se il rinfresco fallisce si continua a servire l'ultimo dato buono**, col
   suo timestamp vero. Una card che mostra la classifica di ieri dicendo che e'
   di ieri e' onesta; una card che sparisce a ogni singhiozzo di rete no.
2. **Il lock si chiude quando Redis non risponde**, al contrario del rate
   limiter, che per policy dichiarata resta aperto. Qui aprire vorrebbe dire
   lasciare che ogni richiesta chiami Last.fm insieme alle altre: esattamente
   la valanga che il lock esiste per fermare.
"""

import asyncio
import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import async_session
from app.models.track import GlobalChartEntry, TrackWorldPlaycount
from app.services import lastfm_client
from app.services.redis_client import get_redis

logger = logging.getLogger(__name__)

# La classifica mondiale si muove di giorno in giorno, non di ora in ora.
CHART_TTL = timedelta(hours=12)
# Il peso mondiale di un brano si muove ancora piu' lentamente.
PLAYCOUNT_TTL = timedelta(days=7)

_CHART_LOCK_KEY = "lock:global_chart_refresh"
# Il lock deve sopravvivere al caso peggiore della fetch, non a quello medio: se
# scade a fetch in corso riapre la valanga che doveva chiudere.
_CHART_LOCK_TTL = 120

CHART_LIMIT = 50


def lookup_key(artist: str, track: str) -> str:
    """Chiave di ricerca insensibile a maiuscole e spazi accidentali."""
    normalized_artist = (artist or "").strip().lower()
    normalized_track = (track or "").strip().lower()
    return normalized_artist + "|||" + normalized_track


async def _acquire_lock() -> bool:
    """`True` solo se questo processo ha preso il lock.

    Redis irraggiungibile conta come "non l'ho preso": vedi la garanzia 2 in
    cima al file.
    """
    try:
        redis = get_redis()
        return bool(await redis.set(_CHART_LOCK_KEY, "1", nx=True, ex=_CHART_LOCK_TTL))
    except Exception as exc:
        logger.warning(
            "Lock classifica mondiale non verificabile, si rinuncia al giro: %s", exc
        )
        return False


async def _release_lock() -> None:
    try:
        await get_redis().delete(_CHART_LOCK_KEY)
    except Exception:
        logger.debug("Rilascio lock classifica fallito", exc_info=True)


async def read_chart(db: AsyncSession) -> tuple[list[dict], datetime | None]:
    """La classifica in cache e la sua data. Solo database, nessuna rete."""
    result = await db.execute(
        select(GlobalChartEntry).order_by(GlobalChartEntry.rank.asc())
    )
    rows = result.scalars().all()
    if not rows:
        return [], None

    fetched_at = rows[0].fetched_at
    if fetched_at is not None and fetched_at.tzinfo is None:
        fetched_at = fetched_at.replace(tzinfo=timezone.utc)

    chart = [
        {
            "rank": row.rank,
            "name": row.track_name,
            "artist": row.artist_name,
            "playcount": row.playcount,
            "listeners": row.listeners,
            "image": row.image,
            "url": row.url,
        }
        for row in rows
    ]
    return chart, fetched_at


def is_stale(fetched_at: datetime | None) -> bool:
    if fetched_at is None:
        return True
    if fetched_at.tzinfo is None:
        fetched_at = fetched_at.replace(tzinfo=timezone.utc)
    return datetime.now(timezone.utc) - fetched_at > CHART_TTL


async def _store_chart(db: AsyncSession, chart: list[dict]) -> None:
    """Riscrive la classifica per intero.

    Sostituire invece di aggiornare posizione per posizione evita il caso in cui
    una classifica nuova piu' corta lascia in coda le posizioni della vecchia,
    che sembrerebbero attuali e non lo sarebbero.
    """
    now = datetime.now(timezone.utc)
    await db.execute(delete(GlobalChartEntry))
    for entry in chart:
        db.add(
            GlobalChartEntry(
                rank=entry["rank"],
                track_name=entry["name"],
                artist_name=entry["artist"],
                playcount=entry.get("playcount"),
                listeners=entry.get("listeners"),
                image=entry.get("image"),
                url=entry.get("url"),
                source="lastfm",
                fetched_at=now,
            )
        )
    await db.commit()


async def refresh_chart(db: AsyncSession) -> bool:
    """Rinfresca la classifica se ha senso farlo. `True` se ha scritto.

    Non alza mai: chi chiama e' o un task in sottofondo che nessuno attende, o
    il giro orario. In entrambi i casi un errore qui non deve rompere nulla —
    l'ultimo dato buono resta al suo posto.
    """
    if not lastfm_client.is_configured():
        return False

    if not await _acquire_lock():
        logger.info("Classifica mondiale: rinfresco gia' in corso altrove, si salta")
        return False

    try:
        chart = await lastfm_client.fetch_global_chart(limit=CHART_LIMIT)
        if not chart:
            logger.warning("Classifica mondiale: Last.fm ha risposto senza brani")
            return False
        await _store_chart(db, chart)
        logger.info("Classifica mondiale aggiornata: %d posizioni", len(chart))
        return True
    except Exception as exc:
        # Il dato vecchio resta servibile: la card mostrera' la sua data vera.
        logger.warning(
            "Classifica mondiale: rinfresco fallito, resta il dato precedente: %s", exc
        )
        return False
    finally:
        await _release_lock()


async def refresh_chart_detached() -> None:
    """Rinfresco per un task in sottofondo, con una sessione DB tutta sua.

    La sessione dell'handler viene chiusa appena la risposta parte, e qui la
    risposta parte apposta prima che la fetch finisca: riusarla darebbe un
    errore che nessuno vedrebbe, perche' nessuno attende questo task
    (invariante 4 di CLAUDE.md).
    """
    try:
        async with async_session() as db:
            await refresh_chart(db)
    except Exception:
        logger.warning("Rinfresco classifica in sottofondo fallito", exc_info=True)


async def read_world_playcounts(
    db: AsyncSession, pairs: list[tuple[str, str]]
) -> dict[str, int]:
    """Il peso mondiale dei brani chiesti, solo da cache fresca. Zero rete."""
    if not pairs:
        return {}

    keys = {lookup_key(artist, track) for artist, track in pairs}
    cutoff = datetime.now(timezone.utc) - PLAYCOUNT_TTL
    result = await db.execute(
        select(TrackWorldPlaycount).where(
            TrackWorldPlaycount.lookup_key.in_(keys),
            TrackWorldPlaycount.cached_at >= cutoff,
            TrackWorldPlaycount.playcount.isnot(None),
        )
    )
    return {row.lookup_key: row.playcount for row in result.scalars().all()}


async def fetch_missing_playcounts(
    pairs: list[tuple[str, str]], limit: int = 50
) -> int:
    """Chiede a Last.fm i brani che la cache non ha ancora. Task in sottofondo.

    Ha una sessione DB propria per lo stesso motivo di `refresh_chart_detached`.
    Scrive anche i brani che Last.fm non conosce, con `playcount` a `None`: cosi'
    non li si richiede a ogni giro, e restano comunque fuori dalla classifica
    invece di entrarci con uno zero che sembrerebbe una misura.
    """
    if not pairs or not lastfm_client.is_configured():
        return 0

    written = 0
    try:
        async with async_session() as db:
            known = await read_world_playcounts(db, pairs)
            todo = [(a, t) for a, t in pairs if lookup_key(a, t) not in known][:limit]

            for artist, track in todo:
                try:
                    playcount = await lastfm_client.fetch_track_playcount(artist, track)
                except lastfm_client.LastfmUnavailable as exc:
                    logger.warning(
                        "Last.fm non risponde, si interrompe il giro: %s", exc
                    )
                    break

                now = datetime.now(timezone.utc)
                stmt = (
                    pg_insert(TrackWorldPlaycount)
                    .values(
                        lookup_key=lookup_key(artist, track),
                        artist_name=artist,
                        track_name=track,
                        playcount=playcount,
                        cached_at=now,
                    )
                    .on_conflict_do_update(
                        index_elements=["lookup_key"],
                        set_={"playcount": playcount, "cached_at": now},
                    )
                )
                await db.execute(stmt)
                written += 1
                # Last.fm chiede di non martellare: un respiro fra una e l'altra.
                await asyncio.sleep(0.25)

            if written:
                await db.commit()
                logger.info("Peso mondiale: %d brani aggiornati", written)
    except Exception:
        logger.warning("Aggiornamento peso mondiale fallito", exc_info=True)
    return written


async def chart_age_hours(db: AsyncSession) -> float | None:
    """Da quante ore la classifica non si aggiorna. `None` se non c'e' mai stata.

    Serve a `/health/detailed`: senza questo, un rinfresco fermo da giorni
    resterebbe invisibile finche' qualcuno non guarda la card.
    """
    _, fetched_at = await read_chart(db)
    if fetched_at is None:
        return None
    return (datetime.now(timezone.utc) - fetched_at).total_seconds() / 3600
