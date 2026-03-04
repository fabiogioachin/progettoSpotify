---
name: async-service-review
description: >
  Review asyncio patterns in the FastAPI backend: gather error handling,
  Semaphore usage, race conditions, SpotifyAuthError propagation.
  Project-specific skill.
---

# Async Service Review

Targeted review of asyncio patterns in the FastAPI backend. Ensures resilient concurrent API calls and proper error propagation.

## Agents

| Agent | Focus |
|-------|-------|
| **Concurrency** | asyncio.gather patterns, Semaphore limits, race conditions, task cancellation |
| **Error Flow** | SpotifyAuthError propagation through async chains, try/finally/close patterns |

## Patterns to Verify

### 1. asyncio.gather with Error Isolation
```python
# GOOD: per-call error handling
results = await asyncio.gather(
    _safe_fetch(client.get_top_tracks, "short_term"),
    _safe_fetch(client.get_top_tracks, "medium_term"),
    _safe_fetch(client.get_top_tracks, "long_term"),
)

# BAD: one failure kills all
results = await asyncio.gather(
    client.get_top_tracks("short_term"),
    client.get_top_tracks("medium_term"),
    client.get_top_tracks("long_term"),
)
```

### 2. SpotifyAuthError Must Not Be Swallowed
```python
# GOOD
try:
    data = await client.method()
except SpotifyAuthError:
    raise  # Re-raise BEFORE generic except
except Exception as e:
    logger.error(...)
    raise HTTPException(500)
```

### 3. Client Lifecycle
```python
# GOOD: try/finally/close pattern
client = SpotifyClient(db, user_id)
try:
    result = await client.get_data()
finally:
    await client.close()
```

### 4. Semaphore for Rate Limiting
```python
semaphore = asyncio.Semaphore(10)
async def _limited_call(coro):
    async with semaphore:
        return await coro
```

## Key Files
- `backend/app/services/taste_evolution.py` — `_safe_fetch` pattern (6 parallel calls)
- `backend/app/services/spotify_client.py` — HTTP client lifecycle
- `backend/app/routers/*.py` — require_auth → client → try/finally/close
