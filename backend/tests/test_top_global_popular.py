"""Test della card "Popolari nel mondo, fra i tuoi".

La classifica riordina i brani ascoltati dall'utente per quante volte il mondo
li ha ascoltati, secondo Last.fm. Non usa piu' l'indice di popolarita' di
Spotify perche' in dev mode quel campo non esiste piu': non arriva a zero,
proprio non compare fra le chiavi della risposta.

Le cose che possono sbagliare in silenzio, e che qui vengono fissate:

- un brano di cui non si conosce il peso mondiale non deve entrare in
  classifica con uno zero: sarebbe un dato finto che sembra vero (invariante 5);
- la richiesta non deve chiamare nessuno: ne' Spotify ne' Last.fm. Cio' che
  manca si chiede in sottofondo, dopo che la risposta e' partita;
- l'ordine dev'essere deterministico a pari peso, altrimenti la classifica
  cambia da un caricamento all'altro senza che nulla sia cambiato;
- il periodo "Tutto" non deve applicare alcun taglio temporale.
"""

from contextlib import ExitStack
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from app.routers.library import _PLAYED_DAYS_MAP, get_top_global_popular
from app.services.global_chart_cache import lookup_key


def _row(track_id: str, play_count: int, total_ms: int | None = None, name=None):
    when = datetime(2026, 3, 21, 8, 7, 31, tzinfo=timezone.utc)
    return SimpleNamespace(
        track_spotify_id=track_id,
        track_name=name or f"Brano {track_id}",
        artist_name="Artista",
        artist_spotify_id="art1",
        duration_ms=180000,
        total_ms=total_ms if total_ms is not None else 180000 * play_count,
        first_played_at=when,
        last_played_at=when,
        play_count=play_count,
    )


def _make_db(rows: list) -> AsyncMock:
    """DB finto: l'endpoint fa una sola query, il group-by sugli ascolti."""
    db = AsyncMock()
    db.statements = []

    grouped = AsyncMock()
    grouped.all = lambda: rows

    async def _execute(stmt):
        db.statements.append(str(stmt))
        return grouped

    db.execute = _execute
    return db


def _patches(world: dict[str, int] | None, spawned: list):
    """Le dipendenze dell'endpoint.

    `world` e' la cache del peso mondiale, indicizzata per titolo del brano —
    piu' leggibile della chiave composta, che il test costruisce da se'.
    `spawned` raccoglie i task di sottofondo, cosi' si puo' verificare che
    partano senza farli davvero girare.
    """
    by_name = world or {}

    async def _fake_read(db, pairs):
        return {
            lookup_key(artist, track): by_name[track]
            for artist, track in pairs
            if track in by_name
        }

    def _fake_create_task(coro):
        coro.close()  # non lo eseguiamo: qui interessa solo che sia stato lanciato
        spawned.append(coro)
        return SimpleNamespace()

    return [
        patch(
            "app.routers.library.global_chart_cache.read_world_playcounts", _fake_read
        ),
        patch("app.routers.library.get_or_fetch_features", AsyncMock(return_value={})),
        patch("app.routers.library.read_track_images", AsyncMock(return_value={})),
        patch("app.routers.library.asyncio.create_task", side_effect=_fake_create_task),
    ]


async def _call(rows, world=None, **kwargs):
    db = _make_db(rows)
    spawned: list = []
    with ExitStack() as stack:
        for p in _patches(world, spawned):
            stack.enter_context(p)
        result = await get_top_global_popular(
            range=kwargs.get("range", "30d"),
            limit=kwargs.get("limit", 50),
            user_id=1,
            db=db,
        )
    return result, db, spawned


@pytest.mark.asyncio
async def test_ordina_per_peso_mondiale_non_per_ascolti_tuoi():
    """Il brano che ascolti meno ma che il mondo ascolta di piu' sta primo."""
    rows = [_row("a", play_count=99, name="Poco famoso"), _row("b", 1, name="Hit")]
    result, _, _ = await _call(rows, world={"Poco famoso": 1000, "Hit": 900000})

    assert [t["name"] for t in result["tracks"]] == ["Hit", "Poco famoso"]
    assert result["tracks"][0]["world_playcount"] == 900000


@pytest.mark.asyncio
async def test_brano_senza_peso_mondiale_resta_fuori_e_viene_contato():
    """Niente zero inventati: chi non ha il dato esce, e lo si dichiara."""
    rows = [_row("a", 5, name="Noto"), _row("b", 5, name="Ignoto"), _row("c", 5, name="Altro")]
    result, _, _ = await _call(rows, world={"Noto": 50})

    assert [t["name"] for t in result["tracks"]] == ["Noto"]
    assert result["popularity_missing"] == 2
    assert result["total"] == 1
    assert all(t["world_playcount"] is not None for t in result["tracks"])


@pytest.mark.asyncio
async def test_pari_peso_ordine_deterministico():
    """A parita' di peso mondiale vince chi ascolti di piu', sempre uguale."""
    rows = [_row("x", play_count=2, name="Poco"), _row("y", play_count=40, name="Tanto")]
    result, _, _ = await _call(rows, world={"Poco": 50, "Tanto": 50})

    assert [t["name"] for t in result["tracks"]] == ["Tanto", "Poco"]


@pytest.mark.asyncio
async def test_la_richiesta_non_chiama_nessuno():
    """Ne' Spotify ne' Last.fm dentro il ciclo richiesta/risposta."""
    rows = [_row("a", 5, name="Noto")]
    with (
        patch("app.routers.library.SpotifyClient") as client_cls,
        patch(
            "app.routers.library.global_chart_cache.fetch_missing_playcounts"
        ) as fetch,
    ):
        await _call(rows, world={"Noto": 60})

    client_cls.assert_not_called()
    fetch.assert_not_called()


@pytest.mark.asyncio
async def test_i_brani_mancanti_si_chiedono_in_sottofondo():
    """Cio' che la cache non ha si chiede dopo, non durante la richiesta."""
    rows = [_row("a", 5, name="Noto"), _row("b", 5, name="Ignoto")]
    _, _, spawned = await _call(rows, world={"Noto": 60})

    assert len(spawned) == 1, "deve partire un solo task di recupero"


@pytest.mark.asyncio
async def test_nessun_task_se_la_cache_e_completa():
    """Cache piena: nessuna chiamata inutile a Last.fm."""
    rows = [_row("a", 5, name="Noto")]
    _, _, spawned = await _call(rows, world={"Noto": 60})

    assert spawned == []


@pytest.mark.asyncio
async def test_periodo_tutto_non_taglia_lo_storico():
    """'all' vale None nella mappa: nessun filtro temporale nella query."""
    assert _PLAYED_DAYS_MAP["all"] is None

    result, db, _ = await _call([_row("a", 5, name="Noto")], world={"Noto": 60}, range="all")

    assert result["range"] == "all"
    assert "played_at >=" not in db.statements[0]


@pytest.mark.asyncio
async def test_limit_taglia_dopo_aver_ordinato():
    """Il taglio arriva sulla classifica ordinata, non sulle righe grezze."""
    rows = [_row(f"t{i}", play_count=100 - i, name=f"n{i}") for i in range(5)]
    world = {"n0": 1, "n1": 2, "n2": 3, "n3": 4, "n4": 99}

    result, _, _ = await _call(rows, world=world, limit=2)

    assert [t["name"] for t in result["tracks"]] == ["n4", "n3"]
    # total resta il numero di brani classificabili, non quello mostrato.
    assert result["total"] == 5


@pytest.mark.asyncio
async def test_card_vuota_quando_nessun_brano_ha_peso_mondiale():
    """Zero brani classificabili: lista vuota, cosi' il frontend nasconde la card."""
    result, _, _ = await _call([_row("a", 5), _row("b", 3)], world={})

    assert result["tracks"] == []
    assert result["total"] == 0
    assert result["popularity_missing"] == 2
    assert result["source"] == "lastfm_playcount"
