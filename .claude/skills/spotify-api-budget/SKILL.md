---
name: spotify-api-budget
description: "Spotify dev mode rate limit budget. Rolling 30-second window, per-endpoint call counts, defensive patterns, cache architecture. Read BEFORE adding any new Spotify API call."
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

## Cache Architecture (3 tiers)

```python
_cache_5m = TTLCache(maxsize=256, ttl=300)    # top_tracks, top_artists, playlists, get_me, playlist_items, saved_tracks
_cache_2m = TTLCache(maxsize=64, ttl=120)     # recently_played
_artist_cache_1h = TTLCache(maxsize=512, ttl=3600)  # get_artist — CROSS-USER (no user_id in key)
```

### Cache key rules
- **User-scoped data** (top_tracks, playlists, etc.): key = `(user_id, method, *args)`
- **Artist data** (identical for all users): key = `("artist", artist_id)` — TTL 1h, shared across all 5 dev users
- **CRITICAL**: always use default `limit=50` for `get_top_tracks` and `get_top_artists`. Slice in-memory if you need fewer items. Different `limit` values create separate cache entries that never hit.

### Anti-pattern: cache key fragmentation
```python
# BAD — creates separate cache entry, never hits existing cache
data = await client.get_top_tracks(time_range="short_term", limit=10)

# GOOD — hits the same cache entry as every other caller
data = await client.get_top_tracks(time_range="short_term")  # default limit=50
items = data.get("items", [])[:10]  # slice in-memory
```

## Budget Per Endpoint

Count every Spotify API call. Each endpoint must stay under budget.

### Profile Page (`GET /api/v1/profile`)

| Call | Count | TTL Cache | Effective |
|------|-------|-----------|-----------|
| `get_top_artists(short_term)` | 1 | 5 min | 0-1 |
| `get_top_artists(medium_term)` | 1 | 5 min | 0-1 |
| `get_top_artists(long_term)` | 1 | 5 min | 0-1 |
| `get_top_tracks(long_term)` | 1 | 5 min | 0-1 |
| `get_me()` | 1 | 5 min | 0-1 |
| TasteMap computation | 0 | N/A | 0 |
| **Total worst-case** | **5** | | **0-5** |

### Dashboard (`GET /api/v1/dashboard`)

| Call | Count | TTL Cache | Effective |
|------|-------|-----------|-----------|
| `get_top_tracks(short/medium/long)` | 3 | 5 min | 0-3 |
| `get_top_artists(short/medium/long)` | 3 | 5 min | 0-3 |
| `get_recently_played` | 1 | 2 min | 0-1 |
| **Total worst-case** | **7** | | **0-7** |

### Trends (`GET /api/v1/analytics/trends`)

| Call | Count | TTL Cache | Effective |
|------|-------|-----------|-----------|
| `get_top_tracks(short/medium/long)` | 3 | 5 min | 0-3 |
| `get_artist` × N (via `genre_cache`, no cap) | 0-80 | **DB 7d** + Redis 1h | **0-80** |
| **Total worst-case (cold cache)** | **~83** | | **0-83** |
| **Total typical (warm genre cache)** | **~3** | | **0-3** |

Note: Genre fetching uses `genre_cache.get_artist_genres_cached()` — DB cache (7-day TTL) + Spotify API on miss. No artist cap. First-time cost is high but amortizes across 7 days and all users. Cross-user Redis cache (1h) further reduces API hits.

### Discovery (`GET /api/v1/analytics/discovery`)

| Call | Count | TTL Cache | Effective |
|------|-------|-----------|-----------|
| `get_top_tracks(medium_term)` | 1 | 5 min | 0-1 |
| `get_top_artists(medium_term)` | 1 | 5 min | 0-1 |
| `get_top_tracks(short_term)` | 1 | 5 min | 0-1 |
| **Total worst-case** | **3** | | **0-3** |

### Artist Network (`GET /api/v1/artist-network`)

| Call | Count | TTL Cache | Effective |
|------|-------|-----------|-----------|
| `get_top_artists(short_term)` | 1 | 5 min | 0-1 |
| `get_top_artists(medium_term)` | 1 | 5 min | 0-1 |
| `get_top_artists(long_term)` | 1 | 5 min | 0-1 |
| **Total worst-case** | **3** | | **0-3** |

Note: Uses default `limit=50`, slices `[:max_seed_artists]` in-memory. Graph edges from fuzzy genre similarity. NetworkX metrics computed locally — zero additional API calls.

### Wrapped (`GET /api/v1/wrapped`)

| Call | Count | TTL Cache | Effective |
|------|-------|-----------|-----------|
| `get_top_tracks(time_range)` | 1 | 5 min | 0-1 |
| compute_profile (via get_top_tracks) | 0 | cached | 0 |
| compute_taste_evolution | 6 | 5 min | 0-6 |
| compute_temporal_patterns | 1 | 2 min | 0-1 |
| build_artist_network | 3 | 5 min | 0-3 |
| **Total worst-case** | **11** | | **0-11** |

Note: `get_top_tracks(limit=50)` now used everywhere (was `limit=10`). Items sliced `[:10]` in-memory.

### Playlist Compare (`GET /api/v1/playlists/compare`)

| Call | Count | TTL Cache | Effective |
|------|-------|-----------|-----------|
| `get(/playlists/{pid})` × N | N (2-4) | none | 2-4 |
| `get_playlist_items(pid)` × pages (no track cap) | ~4-80+ | **5 min** | 0-80+ |
| `get_track(tid)` × 100 (popularity enrichment) | ≤100 | **5 min** | 0-100 |
| `get_artist` × N (via `genre_cache`, no cap) | 0-300+ | **DB 7d** + Redis 1h | **0-300+** |
| **Total worst-case (4 large playlists, cold cache)** | **~484+** | | **~4-484+** |
| **Total typical (warm genre cache)** | **~84** | | **~4-84** |

Note: No track-per-playlist or artist genre caps. `get_playlist_items()` cached 5min. Genre fetching via `genre_cache.get_artist_genres_cached()` — DB (7d TTL), first-visit cost amortized. Large playlists naturally throttled by sliding window (25 calls/30s). Frontend shows ThrottleBanner during waits.

### Export (`GET /api/v1/export/claude-prompt`)

| Call | Count | TTL Cache | Effective |
|------|-------|-----------|-----------|
| `compute_trends` | same as Trends above | cached | 0-23 |
| `get_top_tracks(time_range)` | 1 | 5 min | 0 (cached by trends) |
| taste_evolution + network + temporal | same as Wrapped above | cached | 0-10 |
| **Total worst-case** | **~33** | | **mostly cached** |

Note: Export no longer calls `compute_profile` separately — extracts profile from `compute_trends` result, eliminating duplicate work.

### Background Jobs

| Job | Frequency | Calls/user | Max users |
|-----|-----------|------------|-----------|
| `sync_recent_plays` | Every 60 min | 1 (`get_recently_played`) + upsert TrackPopularity (DB only) + genre cache (0-N `get_artist` for uncached, P2, cross-user 1h cache) | 5 |
| `save_daily_snapshot` | 1x/day (first login) | 2 (`get_top_artists` + `get_top_tracks`) | 5 |
| `compute_daily_aggregates` | 02:00 daily | 0 (DB only) | 5 |

**Critical rule**: `sync_recent_plays` MUST `break` on `RateLimitError`. Rate limit is app-wide.

### Audio Analysis (`POST /api/v1/analyze-tracks`)

| Call | Count | TTL Cache | Effective |
|------|-------|-----------|-----------|
| Spotify API calls | **0** | N/A | **0** |

Frontend sends full track objects in POST body. Backend uses librosa on preview MP3s (CDN, not Spotify API).

### Worst-Case Scenario: User Opens App Fresh

All caches empty, first visit of the day:
1. Auth: `get_me()` — 1 call
2. Dashboard load: up to 4 calls (library/top + temporal + trends overhead)
3. Trends: genre fetching via `genre_cache` — 0 calls if DB cache warm (7d TTL), up to ~80 artist calls if cold
4. Profile navigation: up to 5 calls (some cached from dashboard)
5. Background snapshot: 0 calls (cached from dashboard)
6. Audio analysis: 0 calls (frontend passes track data)
7. **Total first-ever visit (cold genre cache): ~10-90 calls** — throttled naturally by sliding window
8. **Total typical visit (warm genre cache): ~10-15 calls** (genre cache eliminates artist fetches)

With caches warm (typical navigation): **0-5 calls** per page visit.

**Multi-user benefit**: `artist_genres` DB cache is shared across all users (7-day TTL). The second user to visit pays zero genre API calls. Redis artist cache (1h) provides hot-path optimization on top.

## Defensive Patterns

### 1. Three-tier cachetools TTL (Module-Level)

```python
_cache_5m = TTLCache(maxsize=256, ttl=300)         # user-specific data
_cache_2m = TTLCache(maxsize=64, ttl=120)          # recently played
_artist_cache_1h = TTLCache(maxsize=512, ttl=3600) # cross-user artist data
```

### 2. Global Semaphore (max 3 concurrent)

```python
_global_sem = asyncio.Semaphore(3)  # in SpotifyClient._request()
```

### 3. retry_with_backoff (max_retry_after=30s)

Fail immediately if `retry_after > 30s`. Dev mode sends extreme values.

### 4. Global Cooldown (every 429 activates)

Requests pending in the semaphore fail immediately during cooldown.

### 5. Sliding Window Throttle (25 calls/30s, atomic lock)

Preventive throttle — raises `ThrottleError` before hitting Spotify. Single `async with _window_lock` block (no TOCTOU gap).

### 6. gather_in_chunks (chunk_size=4)

Sequential batch execution for parallel fetches. Reduces burst pressure.

### 7. ThrottleBanner (Frontend)

Animated countdown on 429 with `throttled: true`. Auto-retries after countdown.

### 8. Background Job Early Break on RateLimitError

### 9. Genre Cache (DB 7d TTL + Redis 1h + Spotify API)

`genre_cache.get_artist_genres_cached(db, client, artist_ids)` centralizes all genre fetching. DB cache (7-day TTL) eliminates repeat API calls. No artist caps — the cache naturally bounds API usage. Background jobs populate cache opportunistically via `sync_recent_plays`.

## Rules for Adding New API Calls

1. **Count calls**: before writing code, count total Spotify API calls worst-case
2. **Check cache**: is this data already cached? Use the same cache key. ALWAYS use default `limit=50` for top tracks/artists
3. **Add to budget table**: update this skill with the new endpoint's call count
4. **Global sem handles concurrency**: no local semaphores needed — `_request()` limits to 3
5. **Always retry_with_backoff**: never call `client.get_*()` directly
6. **Test with empty cache**: verify the endpoint works within budget
7. **Genre fetching**: always use `genre_cache.get_artist_genres_cached()` — no artificial caps, DB cache (7d TTL) bounds API calls naturally
8. **Cross-user data**: if the data is user-independent (artist profiles, album data), use `_artist_cache_1h` pattern (no `user_id` in key)
9. **Re-raise critical exceptions from gather_in_chunks**: always check for `SpotifyAuthError` and `RateLimitError` in `gather_in_chunks` results before processing

## Anti-Patterns

| Pattern | Why It's Bad | Fix |
|---------|-------------|-----|
| `client.get_top_tracks(limit=10)` | Creates separate cache entry, never hits | Use default `limit=50`, slice in-memory |
| `await client.get_artist(id)` without retry | 429 not retried | `retry_with_backoff(client.get_artist, id)` |
| `asyncio.gather(*[fetch(id) for id in ids])` 5+ items | Burst bypasses sliding window | `gather_in_chunks(tasks, chunk_size=4)` |
| `except Exception` without `except SpotifyAuthError: raise` | Swallows 401 | Add SpotifyAuthError handler first |
| `except Exception` without `except RateLimitError: raise` in gather results | Swallows 429, ignores budget exhaustion | Re-raise `(SpotifyAuthError, RateLimitError)` |
| `retry_after > 60s` → sleep | Blocks app for minutes | Cap at 30s, fail immediately |
| Background job continues after 429 | Cascading rate limits | `break` on RateLimitError |
| `get_artist` with `user_id` in cache key | Same artist fetched per-user | Use `_artist_cache_1h` with `("artist", id)` key |
| `compute_profile` + `compute_trends` for same range | Duplicate work | Extract profile from trends result |
| `_extract_genres` called per-period in loops | 3 × 50 = 150 artist calls | Use `genre_cache.get_artist_genres_cached()` — DB cache (7d TTL), no caps |
