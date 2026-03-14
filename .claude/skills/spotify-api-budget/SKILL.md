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
| `get_top_artists(long_term)` | 1 | 5 min | 0-1 |
| `get_top_tracks(long_term)` | 1 | 5 min | 0-1 |
| `get_me()` | 1 | uncached* | 1 |
| **Total worst-case** | **4** | | **1-4** |

*`get_me()` should be cached (API-1 finding — add to `_cache_5m`).

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

### Artist Network (`GET /api/analytics/artist-network`)

| Call | Count | TTL Cache | Effective |
|------|-------|-----------|-----------|
| `get_top_artists(medium_term)` | 1 | 5 min | 0-1 |
| `get_top_artists(long_term)` | 1 | 5 min | 0-1 |
| **Total worst-case** | **2** | | **0-2** |

Note: No `get_related_artists` calls (403 in dev mode). Graph edges built from shared genres between top artists — zero additional API calls.

### Worst-Case Scenario: User Opens App Fresh

All caches empty, first visit of the day:
1. Auth: `get_me()` — 1 call
2. Dashboard load: up to 7 calls
3. Profile navigation: up to 3 more calls (some cached from dashboard)
4. Background snapshot: 2 calls (but cached from dashboard)
5. **Total: ~10-13 unique calls** (cachetools deduplicates the rest)

With cachetools active and normal navigation: **3-5 calls** per page visit.

## Defensive Patterns

### 1. cachetools TTL (Module-Level)

```python
from cachetools import TTLCache

_cache_5m = TTLCache(maxsize=256, ttl=300)   # top_tracks, top_artists, playlists, get_me
_cache_2m = TTLCache(maxsize=64, ttl=120)    # recently_played

def _cache_key(user_id, method_name, *args, **kwargs):
    return (user_id, method_name, args, tuple(sorted(kwargs.items())))
```

Caches are **module-level** (survive per-request client instances). Per-user isolation via `user_id` in key.

### 2. Semaphore(2) for Parallel Calls

```python
sem = asyncio.Semaphore(2)

async def fetch_with_sem(coro):
    async with sem:
        return await coro
```

Never fire 3+ Spotify calls simultaneously. Dev mode punishes bursts.

### 3. retry_with_backoff with max_retry_after Cap

```python
result = await retry_with_backoff(
    client.get_top_tracks,
    time_range="short_term",
    max_retry_after=30.0,  # default — fail fast on extreme retry_after
)
```

If `retry_after > 30s`, fail immediately. Dev mode can send `retry_after=75000s+` — sleeping that long blocks the app.

### 4. Global Cooldown (SpotifyClient)

```python
# In SpotifyClient._request:
if retry_after and retry_after > 600:  # 10 minutes
    SpotifyClient._cooldown_until = time.time() + retry_after
```

If retry_after exceeds 10 minutes, block ALL requests (not just the current one). This prevents cascading 429s.

### 5. Background Job Early Break

```python
for user_id in user_ids:
    try:
        await _sync_user_recent_plays(db, user_id)
    except RateLimitError as e:
        logger.warning("Rate limited — stopping sync for all remaining users")
        break  # CRITICAL: stop iterating, rate limit is app-wide
```

### 6. Dedup + Cap for Individual Artist Fetches

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
4. **Use Semaphore(2)**: if calling 3+ in parallel
5. **Always retry_with_backoff**: never call `client.get_*()` directly
6. **Test with empty cache**: clear `_cache_*` and verify the endpoint works within budget
7. **Cap individual fetches**: if fetching per-item (artists, tracks), cap at 20 and dedup globally

## Anti-Patterns

| Pattern | Why It's Bad | Fix |
|---------|-------------|-----|
| `await client.get_artist(id)` without retry | 429 not retried | `retry_with_backoff(client.get_artist, id)` |
| `asyncio.gather(*[fetch(id) for id in ids])` with 50+ items | Burst of 50 calls | Semaphore(2) + cap 20 |
| `except Exception: return default` without `except SpotifyAuthError: raise` | Swallows 401 | Add SpotifyAuthError handler first |
| `retry_after > 60s` → sleep | Blocks app for minutes | Cap at 30s, fail immediately |
| Background job continues after 429 | Cascading rate limits | `break` on RateLimitError |
| Fetching same artist in multiple endpoints | Duplicate calls | Module-level cache deduplicates |
