---
name: fastapi-spotify-patterns
description: Backend patterns for this FastAPI + Spotify API project. Router structure, SpotifyClient lifecycle, error propagation, resilience, rate limit budget, and background jobs.
---

# FastAPI Spotify Patterns

Patterns codificati in questo progetto. Leggere PRIMA di scrivere qualsiasi codice backend.

## Router Pattern

**Gestione errori centralizzata** — `main.py` registra 3 global exception handler:

- `SpotifyAuthError` → 401 `"Sessione scaduta"`
- `RateLimitError` (incluso `ThrottleError`) → 429 con `Retry-After` + `throttled` flag
- `SpotifyServerError` → 502 `"Spotify non disponibile"`

I router NON devono gestire questi errori individualmente. Basta ri-lanciarli:

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
    except (SpotifyAuthError, RateLimitError, SpotifyServerError):
        raise  # Handled by global exception handlers in main.py
    except Exception as exc:
        logger.error("Errore descrittivo: %s", exc)
        raise HTTPException(status_code=500, detail="Messaggio in italiano")
    finally:
        await client.close()
    return result
```

### Invariante critica: mai inghiottire SpotifyAuthError/RateLimitError

```python
# CORRETTO — ri-lancia, il global handler converte in 401/429/502
except (SpotifyAuthError, RateLimitError, SpotifyServerError):
    raise
except Exception as exc:
    ...

# SBAGLIATO — inghiotte il 401/429, l'utente vede 500 o dati stale
except Exception as exc:
    ...
```

Se `SpotifyAuthError` viene catturato da un generico `except Exception`, il frontend non riceve il 401 e non redirige al login. Se `RateLimitError` viene inghiottito, il frontend non vede il `Retry-After`.

## SpotifyClient Lifecycle

- Creato nel router: `client = SpotifyClient(db, user_id)`
- Chiuso nel `finally`: `await client.close()`
- MAI passato tra richieste o riusato tra handler

## RequestDataBundle — Request-Scoped Deduplication

`RequestDataBundle` (`data_bundle.py`) wrappa SpotifyClient con cache in-memory per la durata di una singola request. Evita chiamate duplicate quando più servizi richiedono gli stessi dati.

### Pattern: router crea bundle → prefetch → passa ai servizi

```python
from app.services.data_bundle import RequestDataBundle

@router.get("/endpoint")
async def handler(
    request: Request,
    user_id: int = Depends(require_auth),
    db: AsyncSession = Depends(get_db),
):
    client = SpotifyClient(db, user_id)
    try:
        bundle = RequestDataBundle(client)
        await bundle.prefetch()  # fetch all 3 time_ranges in parallel
        result = await some_service(client, db, bundle=bundle)
    except (SpotifyAuthError, RateLimitError, SpotifyServerError):
        raise
    except Exception as exc:
        logger.error("Errore: %s", exc)
        raise HTTPException(status_code=500, detail="Errore interno")
    finally:
        await client.close()
    return result
```

### Metodi cached dal bundle

- `get_top_tracks(time_range, limit)` — cached per `(time_range, limit)`
- `get_top_artists(time_range, limit)` — cached per `(time_range, limit)`
- `get_recently_played()` — cached (singola chiave)
- `get_me()` — cached (singola chiave)
- `prefetch()` — fetch parallelo di tutti e 3 i time_range per tracks e artists

### Servizi: accettano bundle=None (backward compatible)

```python
async def compute_something(client, db, *, bundle=None):
    if bundle:
        data = await bundle.get_top_tracks(time_range="short_term")
    else:
        data = await retry_with_backoff(client.get_top_tracks, time_range="short_term")
```

## Async Task Pattern (POST/Poll)

Per operazioni pesanti (wrapped, playlist-analytics), usare il pattern POST → poll:

1. `POST /endpoint` avvia un background task, ritorna `task_id`
2. `GET /endpoint/{task_id}` polling per risultati progressivi
3. Il background task usa `async_session()` dedicata (non `get_db()`)

### Riferimento: `_run_wrapped_task` in `wrapped.py`

```python
@router.post("/wrapped")
async def start_wrapped(request: Request, ...):
    task_id = str(uuid.uuid4())
    # Store task state in _tasks dict
    _tasks[task_id] = {"status": "waiting", ...}
    asyncio.create_task(_run_wrapped_task(task_id, user_id, time_range))
    return {"task_id": task_id}

@router.get("/wrapped/{task_id}")
async def poll_wrapped(task_id: str):
    task = _tasks.get(task_id)
    if not task:
        raise HTTPException(404)
    return task  # {status: "waiting"|"completed"|"error", result: {...}}

async def _run_wrapped_task(task_id, user_id, time_range):
    async with async_session() as bg_db:  # Sessione DB dedicata
        client = SpotifyClient(bg_db, user_id)
        try:
            bundle = RequestDataBundle(client)
            await bundle.prefetch()
            # ... compute with bundle ...
            _tasks[task_id] = {"status": "completed", "result": result}
        except Exception as exc:
            _tasks[task_id] = {"status": "error", "detail": str(exc)}
        finally:
            await client.close()
```

**Regole**:
- Background task DEVE usare `async_session()`, mai `get_db()`
- Il client viene creato dentro il task, non passato dal router
- `RequestDataBundle` funziona anche nei background task

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

### Atomic Rate Limit Check — Lua Script (1 Redis call)

`SpotifyClient._request()` chiama `_check_and_register()` che esegue un singolo `EVALSHA` Lua in Redis. Lo script atomicamente:
1. Controlla cooldown TTL → `RateLimitError` se attivo
2. Pulisce entries scadute dal sorted set
3. Conta chiamate per-tier e per-user (parsing formato `{uuid}:{priority}:{user_id}`)
4. Controlla capacità sliding window (25 chiamate/30s) → `ThrottleError` se pieno
5. Se tutto ok, ZADD registra la chiamata

**Prima**: 3 round-trip Redis per chiamata Spotify (cooldown + budget + throttle)
**Ora**: 1 round-trip Redis (Lua script atomico)

Gestione errori: NOSCRIPT → reload automatico. Redis down → fail-open.

### Global Semaphore = 3

```python
# In SpotifyClient (class-level):
_global_sem = asyncio.Semaphore(3)
```

Il semaphore globale in `SpotifyClient._request()` limita a 3 richieste Spotify concorrenti in-process. Il Lua script gestisce lo stato distribuito in Redis. Non creare semaphore locali nei servizi — il globale gestisce tutto. Non aumentare oltre 3: dev mode punisce i burst con `retry_after` enormi (75000s+).

### Dedup e cap artisti

```python
from app.constants import ARTIST_GENRE_CAP_TRENDS  # = 20 (for trends/dashboard)
# or: from app.constants import ARTIST_GENRE_CAP_PLAYLIST  # = 50 (for playlist compare)

# CORRETTO — dedup globale, fetch una volta sola, cap da costante
all_artist_ids = set()
for playlist_tracks in all_tracks:
    for track in playlist_tracks:
        for artist in track.get("artists", []):
            all_artist_ids.add(artist["id"])

capped_ids = list(all_artist_ids)[:ARTIST_GENRE_CAP_TRENDS]
artist_data = await gather_in_chunks(
    [fetch_artist(aid) for aid in capped_ids], chunk_size=4
)
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
