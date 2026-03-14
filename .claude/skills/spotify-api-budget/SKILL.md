---
name: spotify-api-budget
description: "Spotify dev mode rate limit budget. Rolling 30-second window, per-endpoint call counts, defensive patterns. Read BEFORE adding any new Spotify API call."
---

# Spotify API Budget — Dev Mode

## Dev Mode Constraints (Feb 2026+)

Spotify does NOT publish exact rate limit numbers. What we know:

| Constraint | Value | Source |
|------------|-------|--------|
| Rate limit window | **Rolling 30 seconds** | [Official docs](https://developer.spotify.com/documentation/web-api/concepts/rate-limits) |
| Exact call limit | **Not published** — community reports suggest ~30-50 calls/30s, but varies by endpoint and account | Community, empirical |
| Max users | **5** (dev mode) | [Quota modes](https://developer.spotify.com/documentation/web-api/concepts/quota-modes) |
| User requirement | **Premium only** | Quota modes |
| Penalty for exceeding | **429 with Retry-After** — values can be extreme (75000s+ reported) | Project experience |
| Batch endpoints | **Removed** (`/artists?ids=`, `/tracks?ids=`, `/albums?ids=`) | Dev mode migration |
| Playlist tracks | **`/playlists/{id}/items`** only (old `/tracks` returns 403) | Dev mode migration |

### Key Insight: Rolling Window

The rate limit is NOT "X calls per minute." It's a **rolling 30-second window** — every call counts for 30 seconds from the moment it was made. Bursts of 10+ simultaneous calls can trigger rate limiting even if overall throughput is low.

## Budget Per Endpoint

Count every Spotify API call. Each endpoint must stay under budget.

### Profile Page (`GET /api/profile`)

| Call | Count | TTL Cache | Effective |
|------|-------|-----------|-----------|
| `get_top_artists(short_term)` | 1 | 5 min | 0-1 |
| `get_top_artists(medium_term)` | 1 | 5 min | 0-1 |
| `get_top_artists(long_term)` | 1 | 5 min | 0-1 |
| `get_top_tracks(long_term)` | 1 | 5 min | 0-1 |
| `get_me()` | 1 | 5 min | 0-1 |
| TasteMap computation | 0 | N/A | 0 |
| **Total worst-case** | **5** | | **0-5** |

Note: TasteMap (PCA, clustering) is pure-compute on local data — zero API calls. `get_me()` now cached in `_cache_5m`.

### Dashboard (`GET /api/dashboard`)

| Call | Count | TTL Cache | Effective |
|------|-------|-----------|-----------|
| `get_top_tracks(short/medium/long)` | 3 | 5 min | 0-3 |
| `get_top_artists(short/medium/long)` | 3 | 5 min | 0-3 |
| `get_recently_played` | 1 | 2 min | 0-1 |
| **Total worst-case** | **7** | | **0-7** |

### Background Jobs

| Job | Frequency | Calls/user | Max users |
|-----|-----------|------------|-----------|
| `sync_recent_plays` | Every 60 min | 1 (`get_recently_played`) | 5 |
| `save_daily_snapshot` | 1x/day (first login) | 2 (`get_top_artists` + `get_top_tracks`) | 5 |
| `compute_daily_aggregates` | 02:00 daily | 0 (DB only) | 5 |

**Critical rule**: `sync_recent_plays` MUST `break` on `RateLimitError`. If one user hits rate limit, stop iterating — the window applies to the app, not the user.

### Discovery (`GET /api/analytics/discovery`)

| Call | Count | TTL Cache | Effective |
|------|-------|-----------|-----------|
| `get_top_tracks(medium_term)` | 1 | 5 min | 0-1 |
| `get_top_artists(medium_term)` | 1 | 5 min | 0-1 |
| `get_top_tracks(short_term)` | 1 | 5 min | 0-1 |
| **Total worst-case** | **3** | | **0-3** |

Note: `get_related_artists` removed (403 in dev mode). No API calls for recommendations — uses `new_discoveries` from short vs medium comparison.

### Artist Network (`GET /api/artist-network`)

| Call | Count | TTL Cache | Effective |
|------|-------|-----------|-----------|
| `get_top_artists(short_term)` | 1 | 5 min | 0-1 |
| `get_top_artists(medium_term)` | 1 | 5 min | 0-1 |
| `get_top_artists(long_term)` | 1 | 5 min | 0-1 |
| **Total worst-case** | **3** | | **0-3** |

Note: Expanded to 3 time ranges (was 2). No `get_related_artists` (403 in dev mode). Graph edges from fuzzy genre similarity. NetworkX metrics (PageRank, Louvain, betweenness) computed locally — zero additional API calls.

### Audio Analysis (`POST /api/analyze-tracks`)

| Call | Count | TTL Cache | Effective |
|------|-------|-----------|-----------|
| Spotify API calls | **0** | N/A | **0** |

The frontend sends full track objects (id, name, artist, preview_url) in the POST body — these are already available from `/api/library/top`. The backend does NOT re-fetch tracks from Spotify. Analysis uses librosa on preview MP3s (downloaded from CDN, not Spotify API) + optional RapidAPI fallback.

**Critical rule**: never add Spotify API calls to this endpoint. The frontend already has the data.

### Worst-Case Scenario: User Opens App Fresh

All caches empty, first visit of the day:
1. Auth: `get_me()` — 1 call
2. Dashboard load: up to 7 calls
3. Profile navigation: up to 3 more calls (some cached from dashboard)
4. Background snapshot: 2 calls (but cached from dashboard)
5. Audio analysis: 0 calls (frontend passes track data)
6. **Total: ~10-13 unique calls** (cachetools deduplicates the rest)

With cachetools active and normal navigation: **3-5 calls** per page visit.

## Defensive Patterns

### 1. cachetools TTL (Module-Level)

```python
from cachetools import TTLCache

_cache_5m = TTLCache(maxsize=256, ttl=300)   # top_tracks, top_artists, playlists, get_me, get_artist
_cache_2m = TTLCache(maxsize=64, ttl=120)    # recently_played

def _cache_key(user_id, method_name, *args, **kwargs):
    return (user_id, method_name, args, tuple(sorted(kwargs.items())))
```

Caches are **module-level** (survive per-request client instances). Per-user isolation via `user_id` in key.

### 2. Global Semaphore in `SpotifyClient._request()`

```python
class SpotifyClient:
    _global_sem = asyncio.Semaphore(6)

    async def _request(self, ...):
        async with SpotifyClient._global_sem:
            # ... entire request body
```

All Spotify API calls go through `_request()`, so **max 6 concurrent calls globally** regardless of how many services fire `asyncio.gather` in parallel. With ~100-200ms RTT, ~90 calls/30s max — well within budget. Local semaphores in individual services are no longer needed and have been removed.

### 3. retry_with_backoff with max_retry_after Cap

```python
result = await retry_with_backoff(
    client.get_top_tracks,
    time_range="short_term",
    max_retry_after=30.0,  # default — fail fast on extreme retry_after
)
```

If `retry_after > 30s`, fail immediately. Dev mode can send `retry_after=75000s+` — sleeping that long blocks the app.

### 4. Global Cooldown — Always-On (SpotifyClient)

```python
# In SpotifyClient._request — EVERY 429 activates cooldown:
if resp.status_code == 429:
    retry_after = float(resp.headers.get("Retry-After", "1"))
    SpotifyClient._cooldown_until = now + retry_after
    raise RateLimitError(retry_after)
```

EVERY 429 activates cooldown (not just > 60s). Requests pending in the semaphore fail immediately. `retry_with_backoff` sleeps and retries — by then cooldown has expired. Log level: `warning` for > 60s, `info` for brief.

### 5. Sliding Window Throttle (SpotifyClient)

```python
class SpotifyClient:
    _call_timestamps: deque = deque()
    _WINDOW_SIZE: float = 30.0
    _MAX_CALLS_PER_WINDOW: int = 25
    _window_lock = asyncio.Lock()
```

Preventive throttle: tracks calls in a 30s sliding window. At 25 calls, raises `ThrottleError(wait_time)` instead of hitting Spotify. `ThrottleError` is a subclass of `RateLimitError` — caught by routers → 429 with `throttled: true` → frontend shows countdown banner. `retry_with_backoff` does NOT retry `ThrottleError` (it's our own limit, not Spotify's).

### 6. gather_in_chunks for Burst Control

```python
from app.utils.rate_limiter import gather_in_chunks

results = await gather_in_chunks(tasks, chunk_size=4)
# results may contain Exception instances (return_exceptions=True)
```

Sequential batch execution: runs coroutines in groups of 4 instead of all at once. Used in `playlist_analytics.py` and `historical_tops.py`. Complements the semaphore — reduces burst pressure on the sliding window.

### 7. ThrottleBanner (Frontend)

When the backend returns 429 with `throttled: true`, the axios interceptor emits `api:throttle` event. `ThrottleBanner` (mounted in AppLayout) shows an animated countdown. Auto-retries after the countdown expires.

### 8. Background Job Early Break

```python
for user_id in user_ids:
    try:
        await _sync_user_recent_plays(db, user_id)
    except RateLimitError as e:
        logger.warning("Rate limited — stopping sync for all remaining users")
        break  # CRITICAL: stop iterating, rate limit is app-wide
```

### 9. Dedup + Cap for Individual Artist Fetches

```python
all_artist_ids = set()
for track in tracks:
    for artist in track.get("artists", []):
        all_artist_ids.add(artist["id"])

capped_ids = list(all_artist_ids)[:20]  # hard cap
```

## Rules for Adding New API Calls

1. **Count calls**: before writing code, count total Spotify API calls in the worst case
2. **Check cache**: is this data already cached by another endpoint? Use the same cache key
3. **Add to budget table**: update this skill with the new endpoint's call count
4. **Global sem handles concurrency**: no local semaphores needed — `_request()` limits to 6 concurrent calls
5. **Always retry_with_backoff**: never call `client.get_*()` directly
6. **Test with empty cache**: clear `_cache_*` and verify the endpoint works within budget
7. **Cap individual fetches**: if fetching per-item (artists, tracks), cap at 20 and dedup globally

## Anti-Patterns

| Pattern | Why It's Bad | Fix |
|---------|-------------|-----|
| `await client.get_artist(id)` without retry | 429 not retried | `retry_with_backoff(client.get_artist, id)` |
| `asyncio.gather(*[fetch(id) for id in ids])` with 5+ items | Burst bypasses sliding window | `gather_in_chunks(tasks, chunk_size=4)` |
| `except Exception: return default` without `except SpotifyAuthError: raise` | Swallows 401 | Add SpotifyAuthError handler first |
| `retry_after > 60s` → sleep | Blocks app for minutes | Cap at 30s, fail immediately |
| Background job continues after 429 | Cascading rate limits | `break` on RateLimitError |
| Fetching same artist in multiple endpoints | Duplicate calls | Module-level cache deduplicates |
