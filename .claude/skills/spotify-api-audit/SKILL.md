---
name: spotify-api-audit
description: Audit Spotify API usage for deprecated endpoints, rate limiting patterns, error handling, token management, and dev mode migration. Project-specific skill for the Spotify Listening Intelligence app.
---
# Spotify API Audit
Targeted audit of Spotify Web API usage. Checks for deprecated endpoints, proper error handling, rate limiting, dev mode compliance, and token lifecycle.
## Agents
| Agent | Focus |
|-------|-------|
| **API Surface** | Deprecated endpoints (Audio Features, Recommendations, Related Artists, Artist Top Tracks), dev mode migration (Feb 2026), proper use of always-available data (popularity, genres, track names) |
| **Resilience** | SpotifyAuthError propagation, _safe_fetch patterns, asyncio.gather per-call error handling, retry_with_backoff coverage, API call budget, InvalidToken → 401 |
## Checklist
### Deprecated API Detection
- [ ] No calls to `/audio-features` — not even behind try/except (403 "gestiti" consumano rate limit budget)
- [ ] No calls to `/recommendations` — removed entirely, not wrapped in fallback
- [ ] No calls to `/artists/{id}/related-artists` — removed in dev mode Feb 2026, returns 403
- [ ] No calls to `/artists/{id}/top-tracks` — removed in dev mode Feb 2026, returns 403
- [ ] No cache-then-fetch patterns for deprecated APIs — cache-only (DB lookup), no API call on cache miss
- [ ] Existing deprecated data shown only from DB cache with `has_*` flags for frontend conditional rendering
- [ ] No dead code: deprecated methods (e.g. `get_audio_features`, `get_recommendations`, `get_related_artists`) removed from SpotifyClient
### Dev Mode Migration (Feb 2026)
- [ ] Playlist tracks fetched via `/playlists/{id}/items` (NOT `/playlists/{id}/tracks` — returns 403)
- [ ] Track data extracted with `item.get("item") or item.get("track")` for backwards compat
- [ ] Pagination uses `limit=50` max (not 100) with offset loop + `next` check
- [ ] No batch endpoints: `GET /artists?ids=`, `GET /tracks?ids=`, `GET /albums?ids=` — use individual `GET /artists/{id}` with semaphore
- [ ] All consumers of playlist tracks paginate: `playlists.py`, `playlist_analytics.py`, `historical_tops.py`
### Error Handling
- [ ] Every router with SpotifyClient has full error chain: `except SpotifyAuthError` → `except RateLimitError` → `except SpotifyServerError` → `except Exception`
- [ ] `asyncio.gather` with 3+ calls uses `_safe_fetch()` per coroutine
- [ ] `_safe_fetch` has `except SpotifyAuthError: raise` BEFORE `except Exception` (ref: `wrapped.py:22-30`)
- [ ] SpotifyAuthError propagation verified at EVERY level of call chain, not just outermost handler
- [ ] Non-critical DB writes (snapshots) wrapped in inner try/except
- [ ] Fernet InvalidToken raises SpotifyAuthError (not generic error)
### Rate Limiting & Budget
- [ ] **Every** SpotifyClient call wrapped in `retry_with_backoff` — no direct `client.get_*()` without retry
- [ ] `retry_with_backoff` has `max_retry_after` cap (≤30s) — dev mode sends `retry_after=75000s+`, must fail immediately
- [ ] Global `_global_sem = asyncio.Semaphore(6)` in `SpotifyClient._request()` — no local semaphores needed in services
- [ ] API call budget per endpoint ≤ 30 calls worst-case
- [ ] Gather with 5+ tasks uses `gather_in_chunks(chunk_size=4)` instead of raw `asyncio.gather`
- [ ] ThrottleError propagated to routers → 429 with `throttled: true` in detail dict
- [ ] Artist IDs deduped globally before fetching (not per-playlist/per-iteration)
- [ ] Global artist fetch cap ≤ 20 per endpoint invocation
- [ ] Rate limiter on auth endpoints uses IP (not full cookie) as key
- [ ] Stale rate limiter keys cleaned periodically (not per-request — O(n log n) eviction amortized on timer)
### Background Tasks
- [ ] Background tasks (`asyncio.create_task`) use dedicated DB session via `async_session()`, NOT request-scoped `get_db()`
- [ ] Background task calls wrapped in `retry_with_backoff`
- [ ] `profile_metrics.py` uses dedicated `async_session()` for DB writes (same pattern as background tasks)
### Data Integrity
- [ ] No hardcoded fallback values that look like real data (e.g., `default=180000`)
- [ ] Missing data defaults to `0`, `None`, or empty — never a plausible fake value
- [ ] Time ranges: only `short_term`, `medium_term`, `long_term` (no custom ranges)
- [ ] Recently played: max 50 items communicated in UI
## Key Files
- `backend/app/services/spotify_client.py` — API wrapper, Fernet encryption
- `backend/app/services/discovery.py` — genre/popularity analysis (no deprecated APIs)
- `backend/app/services/taste_evolution.py` — 3-period comparison, `_safe_fetch`
- `backend/app/services/temporal_patterns.py` — DB-accumulated history
- `backend/app/services/audio_feature_extractor.py` — librosa-based extraction (recovery path for deprecated audio features)
- `backend/app/routers/*.py` — all routers
- `backend/app/utils/rate_limiter.py` — rate limiting, retry_with_backoff, error classes
- `backend/app/services/background_tasks.py` — APScheduler tasks (must use dedicated DB sessions)
