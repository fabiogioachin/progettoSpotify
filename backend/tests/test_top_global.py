"""Test della classifica mondiale e della cache che la regge.

Le cose che possono sbagliare in silenzio, e che qui vengono fissate:

- la richiesta non deve MAI aspettare Last.fm: se lo facesse, un giorno lento
  di Last.fm diventerebbe una dashboard lenta per tutti;
- il task in sottofondo deve avere una sessione DB propria, perche' quella
  della richiesta e' gia' chiusa quando lui parte (invariante 4);
- se il rinfresco fallisce si continua a servire il dato vecchio con la sua
  data vera, invece di far sparire la card;
- il lock si chiude quando Redis non risponde: aprirlo lascerebbe passare tutti
  insieme, che e' la valanga che il lock esiste per fermare;
- senza chiave configurata non parte nessuna chiamata e nulla si rompe.
"""

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from app.services import global_chart_cache, lastfm_client


# --------------------------------------------------------------------------
# lookup_key — la chiave che tiene insieme Spotify e Last.fm
# --------------------------------------------------------------------------


def test_lookup_key_ignora_maiuscole_e_spazi():
    """Lo stesso brano scritto in modi diversi deve dare la stessa chiave."""
    assert global_chart_cache.lookup_key(" Daft Punk ", "One More Time") == (
        global_chart_cache.lookup_key("daft punk", "ONE MORE TIME")
    )


def test_lookup_key_non_confonde_artista_e_titolo():
    """Artista e titolo scambiati sono due brani diversi, non lo stesso."""
    assert global_chart_cache.lookup_key("a", "b") != global_chart_cache.lookup_key(
        "b", "a"
    )


# --------------------------------------------------------------------------
# is_stale — quando vale la pena richiedere
# --------------------------------------------------------------------------


def test_cache_mai_riempita_e_scaduta():
    assert global_chart_cache.is_stale(None) is True


def test_cache_appena_scritta_non_e_scaduta():
    assert global_chart_cache.is_stale(datetime.now(timezone.utc)) is False


def test_cache_vecchia_e_scaduta():
    vecchia = datetime.now(timezone.utc) - global_chart_cache.CHART_TTL - timedelta(minutes=1)
    assert global_chart_cache.is_stale(vecchia) is True


def test_data_senza_fuso_vale_utc():
    """Le date lette dal DB possono arrivare senza fuso: valgono UTC.

    Senza questo, in un fuso a est di Greenwich una classifica appena scritta
    sembrerebbe gia' vecchia e verrebbe richiesta a ogni caricamento.
    """
    naive = datetime.now(timezone.utc).replace(tzinfo=None)
    assert global_chart_cache.is_stale(naive) is False


# --------------------------------------------------------------------------
# Il lock
# --------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_lock_preso_una_volta_sola():
    """Chi arriva secondo non prende il lock e rinuncia al giro."""
    redis = AsyncMock()
    redis.set = AsyncMock(side_effect=[True, False])
    with patch("app.services.global_chart_cache.get_redis", return_value=redis):
        assert await global_chart_cache._acquire_lock() is True
        assert await global_chart_cache._acquire_lock() is False


@pytest.mark.asyncio
async def test_lock_si_chiude_se_redis_non_risponde():
    """Fail-closed, al contrario del rate limiter che e' fail-open per policy."""
    redis = AsyncMock()
    redis.set = AsyncMock(side_effect=ConnectionError("redis giu'"))
    with patch("app.services.global_chart_cache.get_redis", return_value=redis):
        assert await global_chart_cache._acquire_lock() is False


@pytest.mark.asyncio
async def test_ttl_del_lock_sopravvive_alla_fetch_piu_lenta():
    """Un TTL corto scadrebbe a fetch in corso e riaprirebbe la valanga."""
    assert global_chart_cache._CHART_LOCK_TTL >= 90


# --------------------------------------------------------------------------
# refresh_chart — cosa succede quando Last.fm non collabora
# --------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_senza_chiave_non_si_chiama_nessuno():
    """Nessuna chiave: nessuna chiamata, nessun lock, nessun errore."""
    db = AsyncMock()
    with (
        patch.object(lastfm_client, "is_configured", return_value=False),
        patch.object(lastfm_client, "fetch_global_chart", AsyncMock()) as fetch,
        patch("app.services.global_chart_cache._acquire_lock", AsyncMock()) as lock,
    ):
        assert await global_chart_cache.refresh_chart(db) is False
    fetch.assert_not_called()
    lock.assert_not_called()


@pytest.mark.asyncio
async def test_fetch_fallita_non_alza_e_non_cancella_il_dato_vecchio():
    """Il rinfresco fallisce in silenzio: la card mostrera' il dato precedente."""
    db = AsyncMock()
    with (
        patch.object(lastfm_client, "is_configured", return_value=True),
        patch.object(
            lastfm_client,
            "fetch_global_chart",
            AsyncMock(side_effect=lastfm_client.LastfmUnavailable("giu'")),
        ),
        patch("app.services.global_chart_cache._acquire_lock", AsyncMock(return_value=True)),
        patch("app.services.global_chart_cache._release_lock", AsyncMock()),
        patch("app.services.global_chart_cache._store_chart", AsyncMock()) as store,
    ):
        assert await global_chart_cache.refresh_chart(db) is False
    # La cosa che conta: non ha toccato la tabella.
    store.assert_not_called()


@pytest.mark.asyncio
async def test_risposta_vuota_non_svuota_la_classifica():
    """Last.fm che risponde senza brani non deve cancellare quella buona."""
    db = AsyncMock()
    with (
        patch.object(lastfm_client, "is_configured", return_value=True),
        patch.object(lastfm_client, "fetch_global_chart", AsyncMock(return_value=[])),
        patch("app.services.global_chart_cache._acquire_lock", AsyncMock(return_value=True)),
        patch("app.services.global_chart_cache._release_lock", AsyncMock()),
        patch("app.services.global_chart_cache._store_chart", AsyncMock()) as store,
    ):
        assert await global_chart_cache.refresh_chart(db) is False
    store.assert_not_called()


@pytest.mark.asyncio
async def test_il_lock_viene_rilasciato_anche_se_la_fetch_esplode():
    """Un lock non rilasciato bloccherebbe ogni rinfresco fino alla scadenza."""
    db = AsyncMock()
    release = AsyncMock()
    with (
        patch.object(lastfm_client, "is_configured", return_value=True),
        patch.object(
            lastfm_client, "fetch_global_chart", AsyncMock(side_effect=RuntimeError("boom"))
        ),
        patch("app.services.global_chart_cache._acquire_lock", AsyncMock(return_value=True)),
        patch("app.services.global_chart_cache._release_lock", release),
    ):
        assert await global_chart_cache.refresh_chart(db) is False
    release.assert_awaited_once()


# --------------------------------------------------------------------------
# Il client Last.fm
# --------------------------------------------------------------------------


def test_errore_dentro_un_200_non_passa_per_risposta_valida():
    """Last.fm segnala i suoi errori dentro un 200: vanno riconosciuti."""
    import httpx

    resp = httpx.Response(200, json={"error": 6, "message": "Track not found"})
    with (
        patch.object(lastfm_client.settings, "lastfm_api_key", "k"),
        patch("httpx.AsyncClient.get", AsyncMock(return_value=resp)),
    ):
        import asyncio

        with pytest.raises(lastfm_client.LastfmUnavailable):
            asyncio.run(lastfm_client._call("chart.getTopTracks"))


@pytest.mark.asyncio
async def test_chart_scarta_le_voci_senza_nome_o_artista():
    """Una riga senza titolo o senza artista sarebbe muta in classifica."""
    payload = {
        "tracks": {
            "track": [
                {"name": "Buono", "artist": {"name": "Tizio"}, "playcount": "10"},
                {"name": "", "artist": {"name": "Tizio"}},
                {"name": "Senza artista", "artist": {}},
                "non un dizionario",
            ]
        }
    }
    with patch.object(lastfm_client, "_call", AsyncMock(return_value=payload)):
        chart = await lastfm_client.fetch_global_chart()

    assert [t["name"] for t in chart] == ["Buono"]
    assert chart[0]["rank"] == 1
    assert chart[0]["playcount"] == 10


@pytest.mark.asyncio
async def test_chart_regge_la_lista_collassata_a_dizionario():
    """Con un solo risultato Last.fm restituisce un dizionario, non una lista."""
    payload = {"tracks": {"track": {"name": "Solo", "artist": {"name": "Tizio"}}}}
    with patch.object(lastfm_client, "_call", AsyncMock(return_value=payload)):
        chart = await lastfm_client.fetch_global_chart()
    assert len(chart) == 1


@pytest.mark.asyncio
async def test_immagine_vuota_diventa_none():
    """Last.fm manda spesso url vuoti: meglio niente che una stringa vuota."""
    payload = {
        "tracks": {
            "track": [
                {
                    "name": "X",
                    "artist": {"name": "Y"},
                    "image": [{"#text": "", "size": "small"}],
                }
            ]
        }
    }
    with patch.object(lastfm_client, "_call", AsyncMock(return_value=payload)):
        chart = await lastfm_client.fetch_global_chart()
    assert chart[0]["image"] is None


@pytest.mark.asyncio
async def test_playcount_non_numerico_non_diventa_zero():
    """Un contatore illeggibile e' 'non lo so', non 'zero ascolti'."""
    payload = {"track": {"playcount": "non-un-numero"}}
    with patch.object(lastfm_client, "_call", AsyncMock(return_value=payload)):
        assert await lastfm_client.fetch_track_playcount("a", "b") is None


@pytest.mark.asyncio
async def test_brano_sconosciuto_non_e_un_guasto():
    """Last.fm che non conosce un brano risponde, non si rompe.

    Trattarlo come un guasto farebbe interrompere il giro al primo brano
    oscuro della lista, lasciando senza peso tutti quelli dopo di lui.
    Successo dal vivo il 03/09/2026: 4 brani su 60 fermavano gli altri 56.
    """
    errore = lastfm_client.LastfmUnavailable("Track not found", code=6)
    with patch.object(lastfm_client, "_call", AsyncMock(side_effect=errore)):
        assert await lastfm_client.fetch_track_playcount("Tizio", "Ignoto") is None


@pytest.mark.asyncio
async def test_servizio_giu_invece_si_propaga():
    """Un guasto vero deve fermare il giro, altrimenti si martella a vuoto."""
    errore = lastfm_client.LastfmUnavailable("Service offline", code=11)
    with patch.object(lastfm_client, "_call", AsyncMock(side_effect=errore)):
        with pytest.raises(lastfm_client.LastfmUnavailable):
            await lastfm_client.fetch_track_playcount("Tizio", "Brano")


@pytest.mark.asyncio
async def test_un_brano_sconosciuto_non_ferma_gli_altri():
    """Il giro di riempimento prosegue oltre il brano che Last.fm non conosce."""
    chiamate = []

    async def _playcount(artist, track):
        chiamate.append(track)
        if track == "Ignoto":
            return None
        return 1000

    session = AsyncMock()
    session.__aenter__ = AsyncMock(return_value=session)
    session.__aexit__ = AsyncMock(return_value=False)

    with (
        patch.object(lastfm_client, "is_configured", return_value=True),
        patch.object(lastfm_client, "fetch_track_playcount", _playcount),
        patch("app.services.global_chart_cache.async_session", return_value=session),
        patch(
            "app.services.global_chart_cache.read_world_playcounts",
            AsyncMock(return_value={}),
        ),
        patch("app.services.global_chart_cache.asyncio.sleep", AsyncMock()),
    ):
        scritti = await global_chart_cache.fetch_missing_playcounts(
            [("A", "Primo"), ("A", "Ignoto"), ("A", "Terzo")]
        )

    assert chiamate == ["Primo", "Ignoto", "Terzo"]
    assert scritti == 3


@pytest.mark.asyncio
async def test_senza_chiave_il_client_non_chiama():
    with patch.object(lastfm_client.settings, "lastfm_api_key", ""):
        assert await lastfm_client.fetch_global_chart() is None
        assert await lastfm_client.fetch_track_playcount("a", "b") is None


# --------------------------------------------------------------------------
# L'endpoint
# --------------------------------------------------------------------------


def _chart_rows(fetched_at):
    return [
        SimpleNamespace(
            rank=1,
            track_name="Primo",
            artist_name="Tizio",
            playcount=100,
            listeners=10,
            image=None,
            url=None,
            fetched_at=fetched_at,
        )
    ]


def _closing_create_task():
    """Sostituto di `asyncio.create_task` che chiude la coroutine ricevuta.

    Senza questo la coroutine non parte e non viene chiusa: Python lo segnala
    con un RuntimeWarning che sporca l'output della suite e fa sembrare rotto
    un test che invece passa.
    """

    def _fake(coro):
        coro.close()
        return SimpleNamespace()

    return patch("app.routers.library.asyncio.create_task", side_effect=_fake)


def _db_with(rows):
    db = AsyncMock()
    result = AsyncMock()
    result.scalars = lambda: SimpleNamespace(all=lambda: rows)
    db.execute = AsyncMock(return_value=result)
    return db


@pytest.mark.asyncio
async def test_endpoint_non_aspetta_mai_lastfm():
    """Cache vuota: la risposta esce subito, la fetch parte in sottofondo."""
    from app.routers.library import get_top_global

    db = _db_with([])
    with (
        _closing_create_task() as create_task,
        patch.object(lastfm_client, "is_configured", return_value=True),
    ):
        result = await get_top_global(limit=50, user_id=1, db=db)

    assert result["tracks"] == []
    assert result["updated_at"] is None
    create_task.assert_called_once()


@pytest.mark.asyncio
async def test_endpoint_serve_il_dato_vecchio_mentre_lo_rinfresca():
    """Cache scaduta: si mostra comunque, con la sua data vera."""
    from app.routers.library import get_top_global

    vecchia = datetime.now(timezone.utc) - timedelta(days=3)
    db = _db_with(_chart_rows(vecchia))
    with (
        _closing_create_task() as create_task,
        patch.object(lastfm_client, "is_configured", return_value=True),
    ):
        result = await get_top_global(limit=50, user_id=1, db=db)

    assert len(result["tracks"]) == 1
    assert result["updated_at"] == vecchia.isoformat()
    create_task.assert_called_once()


@pytest.mark.asyncio
async def test_cache_fresca_non_scatena_nessun_rinfresco():
    """Nessuna chiamata inutile quando il dato e' ancora buono."""
    from app.routers.library import get_top_global

    db = _db_with(_chart_rows(datetime.now(timezone.utc)))
    with (
        _closing_create_task() as create_task,
        patch.object(lastfm_client, "is_configured", return_value=True),
    ):
        await get_top_global(limit=50, user_id=1, db=db)

    create_task.assert_not_called()


@pytest.mark.asyncio
async def test_il_task_di_sfondo_si_fa_la_sua_sessione():
    """Invariante 4: la sessione della richiesta e' gia' chiusa quando lui parte."""
    session = AsyncMock()
    session.__aenter__ = AsyncMock(return_value=session)
    session.__aexit__ = AsyncMock(return_value=False)

    with (
        patch(
            "app.services.global_chart_cache.async_session", return_value=session
        ) as factory,
        patch(
            "app.services.global_chart_cache.refresh_chart", AsyncMock(return_value=True)
        ) as refresh,
    ):
        await global_chart_cache.refresh_chart_detached()

    factory.assert_called_once()
    # La sessione passata al refresh e' quella nuova, non una catturata altrove.
    assert refresh.await_args.args[0] is session


@pytest.mark.asyncio
async def test_configured_false_quando_manca_la_chiave():
    """Il frontend usa questo flag per nascondere la card senza inventare errori."""
    from app.routers.library import get_top_global

    db = _db_with([])
    with (
        _closing_create_task(),
        patch.object(lastfm_client, "is_configured", return_value=False),
    ):
        result = await get_top_global(limit=50, user_id=1, db=db)

    assert result["configured"] is False
