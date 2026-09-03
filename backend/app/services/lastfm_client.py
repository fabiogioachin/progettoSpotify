"""Ponte verso Last.fm: la classifica mondiale e il peso mondiale di un brano.

Perche' esiste. Spotify in dev mode ha chiuso due porte: le playlist editoriali
(Top 50 - Global e simili rispondono 404) e il campo `popularity`, che non
compare piu' fra le chiavi di nessuna risposta. Restava una sola fonte per dire
qualcosa su cosa ascolta il mondo, ed e' questa.

Due domande, due funzioni:
- `fetch_global_chart()` — la classifica mondiale, da `chart.getTopTracks`;
- `fetch_track_playcount()` — quante volte il mondo ha ascoltato un brano, da
  `track.getInfo`.

Senza chiave configurata ogni funzione ritorna subito `None`: le card che ne
dipendono si nascondono e nient'altro cambia. Stesso patto gia' in uso in
`rapidapi_bridge.py`.
"""

import asyncio
import logging

import httpx

from app.config import settings

logger = logging.getLogger(__name__)

LASTFM_API = "https://ws.audioscrobbler.com/2.0/"

# Last.fm non pubblica un tetto rigido ma chiede di restare "ragionevoli": due
# richieste per volta e un timeout corto bastano, visto che il risultato finisce
# comunque in una cache condivisa e non viene richiesto a ogni pagina.
_sem = asyncio.Semaphore(2)
_TIMEOUT = 10.0


class LastfmUnavailable(Exception):
    """La chiamata non e' andata a buon fine. Chi chiama decide se e' grave."""


def is_configured() -> bool:
    return bool(settings.lastfm_api_key)


async def _call(method: str, **params) -> dict | None:
    """Una chiamata a Last.fm. `None` se non c'e' chiave; alza se fallisce.

    La distinzione conta: "non configurato" e' uno stato normale e silenzioso,
    "configurato ma rotto" e' un errore che chi chiama deve poter vedere per
    decidere se continuare a servire il dato vecchio.
    """
    if not is_configured():
        return None

    query = {
        "method": method,
        "api_key": settings.lastfm_api_key,
        "format": "json",
        **params,
    }
    async with _sem:
        try:
            async with httpx.AsyncClient(timeout=_TIMEOUT) as http:
                resp = await http.get(LASTFM_API, params=query)
        except httpx.HTTPError as exc:
            raise LastfmUnavailable(f"Last.fm irraggiungibile: {exc}") from exc

    if resp.status_code != 200:
        raise LastfmUnavailable(f"Last.fm ha risposto {resp.status_code} a {method}")

    try:
        payload = resp.json()
    except ValueError as exc:
        raise LastfmUnavailable("Last.fm ha risposto con un corpo non JSON") from exc

    # Last.fm segnala i propri errori dentro un 200: senza questo controllo un
    # errore applicativo passerebbe per una risposta valida e vuota.
    if isinstance(payload, dict) and "error" in payload:
        raise LastfmUnavailable(
            f"Last.fm errore {payload.get('error')}: {payload.get('message')}"
        )
    return payload


def _to_int(value) -> int | None:
    """I contatori di Last.fm arrivano come stringhe, e a volte vuoti."""
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _biggest_image(images) -> str | None:
    """L'immagine piu' grande fra quelle offerte, se ce n'e' una vera.

    Last.fm restituisce spesso una lista di url vuoti: in quel caso la
    copertina non c'e', e va detto con `None` invece che con una stringa vuota
    che il frontend proverebbe a caricare.
    """
    if not isinstance(images, list):
        return None
    for entry in reversed(images):
        if isinstance(entry, dict):
            url = (entry.get("#text") or "").strip()
            if url:
                return url
    return None


async def fetch_global_chart(limit: int = 50) -> list[dict] | None:
    """La classifica mondiale di Last.fm. `None` se manca la chiave.

    Ogni voce porta nome, artista, ascolti mondiali e ascoltatori. I brani senza
    nome o senza artista vengono scartati: sarebbero righe mute in classifica.
    """
    payload = await _call("chart.getTopTracks", limit=limit)
    if payload is None:
        return None

    raw = ((payload.get("tracks") or {}).get("track")) or []
    if isinstance(raw, dict):  # Last.fm collassa la lista quando c'e' un solo elemento
        raw = [raw]

    chart = []
    for position, entry in enumerate(raw, start=1):
        if not isinstance(entry, dict):
            continue
        name = (entry.get("name") or "").strip()
        artist = ((entry.get("artist") or {}).get("name") or "").strip()
        if not name or not artist:
            continue
        chart.append(
            {
                "rank": position,
                "name": name,
                "artist": artist,
                "playcount": _to_int(entry.get("playcount")),
                "listeners": _to_int(entry.get("listeners")),
                "url": entry.get("url") or None,
                "image": _biggest_image(entry.get("image")),
            }
        )
    return chart


async def fetch_track_playcount(artist: str, track: str) -> int | None:
    """Quante volte il mondo ha ascoltato questo brano.

    `None` sia quando manca la chiave sia quando Last.fm non conosce il brano:
    in entrambi i casi il brano resta fuori dalla classifica invece di entrarci
    con uno zero, che sembrerebbe una misura e non lo sarebbe.
    """
    if not artist or not track:
        return None
    try:
        payload = await _call(
            "track.getInfo", artist=artist, track=track, autocorrect=1
        )
    except LastfmUnavailable:
        raise
    if payload is None:
        return None
    return _to_int((payload.get("track") or {}).get("playcount"))
