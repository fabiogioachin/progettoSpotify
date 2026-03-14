---
name: fastapi-spotify-patterns
description: Backend patterns for this FastAPI + Spotify API project. Router structure, SpotifyClient lifecycle, error propagation, resilience, rate limit budget, and background jobs.
---

# FastAPI Spotify Patterns

Patterns codificati in questo progetto. Leggere PRIMA di scrivere qualsiasi codice backend.

## Router Pattern

Ogni router segue questa struttura esatta — **tutti e 4 gli except sono obbligatori**:

```python
from app.services.spotify_client import SpotifyClient
from app.utils.rate_limiter import SpotifyAuthError, RateLimitError, SpotifyServerError

@router.get("/endpoint")
async def handler(
    request: Request,
    user_id: int = Depends(require_auth),
    db: AsyncSession = Depends(get_db),
):
    client = SpotifyClient(db, user_id)
    try:
        result = await some_service(client)
    except SpotifyAuthError:
        raise HTTPException(status_code=401, detail="Sessione scaduta")
    except RateLimitError as e:
        raise HTTPException(
            status_code=429,
            detail="Troppe richieste, riprova tra poco",
            headers={"Retry-After": str(int(e.retry_after))},
        )
    except SpotifyServerError:
        raise HTTPException(status_code=502, detail="Spotify non disponibile")
    except Exception as exc:
        logger.exception("Errore descrittivo: %s", exc)
        raise HTTPException(status_code=500, detail="Messaggio in italiano")
    finally:
        await client.close()
    return result
```

### Invariante critica: SpotifyAuthError PRIMA di Exception

```python
# CORRETTO — ordine: SpotifyAuthError → RateLimitError → SpotifyServerError → Exception
except SpotifyAuthError:
    raise HTTPException(status_code=401, detail="Sessione scaduta")
except RateLimitError as e:
    ...
except SpotifyServerError:
    ...
except Exception as exc:
    ...

# SBAGLIATO — inghiotte il 401, l'utente vede dati stale
except Exception as exc:
    ...
```

Se `SpotifyAuthError` viene catturato da un generico `except Exception`, il frontend non riceve il 401 e non redirige al login.

## SpotifyClient Lifecycle

- Creato nel router: `client = SpotifyClient(db, user_id)`
- Chiuso nel `finally`: `await client.close()`
- MAI passato tra richieste o riusato tra handler

## Resilience Patterns

### retry_with_backoff — OBBLIGATORIO per ogni chiamata SpotifyClient

**Ogni** chiamata a `SpotifyClient` deve passare per `retry_with_backoff`. Mai chiamare `client.get_*()` direttamente.

```python
from app.utils.rate_limiter import retry_with_backoff

# CORRETTO
result = await retry_with_backoff(client.get_top_tracks, time_range="short_term", limit=50)

# SBAGLIATO — un 429 non viene ritentato
result = await client.get_top_tracks(time_range="short_term", limit=50)
```

Backoff esponenziale (max 3 retry) su `RateLimitError` (429) e `SpotifyServerError` (5xx). Non ritenta su `SpotifyAuthError`.

**Cap retry_after**: `retry_with_backoff` ha `max_retry_after=30.0`. Se Spotify risponde con `retry_after > 30s` (dev mode può mandare 75000s+), fallisce immediatamente con `RateLimitError`. Mai fare `asyncio.sleep(retry_after)` senza cap — un `retry_after > 60s` significa "non riprovare adesso".

### _safe_fetch — per asyncio.gather con 3+ chiamate

```python
async def _safe_fetch(coro):
    """Una chiamata fallita non deve crashare l'intera pagina."""
    try:
        return await coro
    except SpotifyAuthError:
        raise  # DEVE ri-lanciare — altrimenti un token scaduto viene ignorato
    except Exception as exc:
        logger.warning("Chiamata API fallita: %s", exc)
        return {"items": []}  # o default appropriato
```

**Attenzione**: `_safe_fetch` DEVE avere `except SpotifyAuthError: raise` PRIMA di `except Exception`. La versione senza ri-lancio inghiotte il 401 e mostra dati vuoti invece di redirigere al login. Riferimento corretto: `wrapped.py:22-30`.

```python
results = await asyncio.gather(
    _safe_fetch(retry_with_backoff(client.get_top_artists, time_range="short_term")),
    _safe_fetch(retry_with_backoff(client.get_top_tracks, time_range="short_term")),
    # ...
)
```

Usare SEMPRE `_safe_fetch` quando ci sono 3+ chiamate parallele.

### Non-blocking DB writes

Le scritture DB non critiche (snapshot, log) non devono mai bloccare la risposta:

```python
try:
    await save_snapshot(db, user_id, time_range, profile)
except Exception as snap_exc:
    logger.warning("Snapshot non salvato: %s", snap_exc)
```

## API Call Budget Control

### Regola: max ~30 chiamate Spotify per endpoint

Prima di ogni `asyncio.gather` con N chiamate API, calcolare il worst-case budget. Se > 30 chiamate, ristrutturare.

### Semaphore ≤ 2 per Spotify API

```python
sem = asyncio.Semaphore(2)  # dev mode burst protection

async def fetch_with_sem(artist_id):
    async with sem:
        return await retry_with_backoff(client.get_artist, artist_id)
```

**Mai Semaphore > 2** per chiamate Spotify. 5 richieste simultanee nello stesso istante sono un burst — dev mode lo punisce con `retry_after` enormi.

### Dedup e cap artisti

```python
# CORRETTO — dedup globale, fetch una volta sola, cap 20
all_artist_ids = set()
for playlist_tracks in all_tracks:
    for track in playlist_tracks:
        for artist in track.get("artists", []):
            all_artist_ids.add(artist["id"])

capped_ids = list(all_artist_ids)[:20]  # cap globale
artist_data = await asyncio.gather(*(fetch_with_sem(aid) for aid in capped_ids))
genre_cache = {a["id"]: a.get("genres", []) for a in artist_data if a}

# POI usa genre_cache per tutti i risultati

# SBAGLIATO — fetch per-playlist senza dedup
for playlist in playlists:
    artists = await fetch_artists(playlist.tracks)  # artisti condivisi fetchati N volte
```

### No batch endpoints in dev mode

`GET /artists?ids=`, `GET /tracks?ids=`, `GET /albums?ids=` sono rimossi in dev mode. Usare endpoint individuali (`GET /artists/{id}`) con semaphore + asyncio.gather.

## Spotify Dev Mode Migration (Feb 2026)

Cambiamenti critici:

- `/playlists/{id}/tracks` → **`/playlists/{id}/items`** (il vecchio ritorna 403)
- `GET /playlists/{id}` non include più `tracks` nella risposta
- Campo dati: `item.get("item") or item.get("track")` per backwards compat
- Pagination: `/playlists/{id}/items` ha `limit` max 50 (non 100). Sempre paginare con loop `offset` + check `next`
- Batch endpoints rimossi (vedi sopra)

## Background Tasks

### Sessione DB dedicata — MAI riusare get_db()

```python
# CORRETTO
async def background_job(user_id: int, track_ids: list):
    async with async_session() as bg_db:
        # ... usa bg_db
        await bg_db.commit()

asyncio.create_task(background_job(user_id, track_ids))

# SBAGLIATO — get_db() chiude la sessione quando il handler ritorna
asyncio.create_task(process(db, user_id))  # db è già chiuso!
```

`get_db()` usa `async with async_session() as session: yield session` — il context manager chiude la sessione dopo il route handler. Il background task ha un riferimento a una sessione chiusa.

## Error Hierarchy

```
app.utils.rate_limiter
├── SpotifyAuthError    → 401, redirect a login
├── RateLimitError      → 429, retry_after propagato al frontend
└── SpotifyServerError  → 5xx, retry con backoff
```

- `SpotifyAuthError`: token scaduto/corrotto/mancante. Il frontend ascolta il 401 e dispatcha `auth:expired`.
- `RateLimitError`: ha attributo `retry_after` (float seconds). Il router propaga l'header `Retry-After`.
- `SpotifyServerError`: errore transitorio lato Spotify. Si ritenta con backoff.

## Token Management

- Encryption: Fernet (chiave derivata da `SESSION_SECRET` + `ENCRYPTION_SALT` via PBKDF2)
- Refresh proattivo: 5 minuti prima della scadenza
- Refresh reattivo: su 401, `_force_refresh()` + retry (una volta sola)
- Lock `asyncio.Lock()` previene refresh concorrenti
- `InvalidToken` (Fernet) → `SpotifyAuthError` → 401

## Spotify API Constraints

- **Deprecated/rimossi in dev mode**: Audio Features, Recommendations, Related Artists, Artist Top Tracks, batch endpoints (`/artists?ids=`, `/tracks?ids=`, `/albums?ids=`). Non usare. Non lasciare dietro try/except — un 403 "gestito" consuma rate limit budget. Rimuovere interamente.
- Time ranges: solo `short_term` (~4w), `medium_term` (~6m), `long_term` (all). Nessun range custom.
- Recently played: max 50 item (hard limit API). Workaround: `RecentPlay` model + sync orario APScheduler.
- **Sempre disponibili**: popularity, genres, track/artist metadata, user profile.
- **Pure-compute services** (`taste_clustering.py`, `taste_map.py`, `genre_utils.py`): lavorano su dati locali. Non devono MAI importare SpotifyClient o fare chiamate HTTP.

## Convenzioni

- Messaggi di errore HTTP: in italiano
- Logger: `logger = logging.getLogger(__name__)` a livello modulo
- Query params con `Literal` per time_range: `Literal["short_term", "medium_term", "long_term"]`
- Nessun dato fake/plausibile come default: `None`, `0`, `[]` oppure flag `has_*`
