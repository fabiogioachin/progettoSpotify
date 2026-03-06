---
name: fastapi-spotify-patterns
description: Backend patterns for this FastAPI + Spotify API project. Router structure, SpotifyClient lifecycle, error propagation, resilience, and background jobs.
---

# FastAPI Spotify Patterns

Patterns codificati in questo progetto. Leggere PRIMA di scrivere qualsiasi codice backend.

## Router Pattern

Ogni router segue questa struttura esatta:

```python
from app.services.spotify_client import SpotifyClient
from app.utils.rate_limiter import SpotifyAuthError

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
    except Exception as exc:
        logger.error("Errore descrittivo: %s", exc)
        raise HTTPException(status_code=500, detail="Messaggio in italiano")
    finally:
        await client.close()
    return result
```

### Invariante critica: SpotifyAuthError PRIMA di Exception

```python
# CORRETTO
except SpotifyAuthError:
    raise HTTPException(status_code=401, detail="Sessione scaduta")
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

### _safe_fetch — per asyncio.gather con 3+ chiamate

```python
async def _safe_fetch(coro):
    """Una chiamata fallita non deve crashare l'intera pagina."""
    try:
        return await coro
    except Exception as exc:
        logger.warning("Chiamata API fallita: %s", exc)
        return {"items": []}  # o default appropriato

results = await asyncio.gather(
    _safe_fetch(retry_with_backoff(client.get_top_artists, time_range="short_term")),
    _safe_fetch(retry_with_backoff(client.get_top_tracks, time_range="short_term")),
    # ...
)
```

Usare SEMPRE `_safe_fetch` quando ci sono 3+ chiamate parallele. Un timeout Spotify su una chiamata non deve far fallire tutta la pagina.

### retry_with_backoff — per 429 e 5xx

```python
from app.utils.rate_limiter import retry_with_backoff

result = await retry_with_backoff(client.get_top_tracks, time_range="short_term", limit=50)
```

Backoff esponenziale (max 3 retry) su `RateLimitError` (429) e `SpotifyServerError` (5xx). Non ritenta su `SpotifyAuthError`.

### Non-blocking DB writes

Le scritture DB non critiche (snapshot, log) non devono mai bloccare la risposta:

```python
try:
    await save_snapshot(db, user_id, time_range, profile)
except Exception as snap_exc:
    logger.warning("Snapshot non salvato: %s", snap_exc)
```

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

- **Audio Features** e **Recommendations**: DEPRECATED. Non usare per nuove feature.
- Time ranges: solo `short_term` (~4w), `medium_term` (~6m), `long_term` (all). Nessun range custom.
- Recently played: max 50 item (hard limit API). Workaround: `RecentPlay` model + sync orario APScheduler.
- Endpoints sempre disponibili: popularity, genres, track/artist metadata, related artists, artist top tracks.

## Convenzioni

- Messaggi di errore HTTP: in italiano
- Logger: `logger = logging.getLogger(__name__)` a livello modulo
- Query params con `Literal` per time_range: `Literal["short_term", "medium_term", "long_term"]`
- Nessun dato fake/plausibile come default: `None`, `0`, `[]` oppure flag `has_*`
