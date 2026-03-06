---
name: spotify-api-audit
description: Audit Spotify API usage for deprecated endpoints, rate limiting patterns, error handling, and token management. Project-specific skill for the Spotify Listening Intelligence app.
---
# Spotify API Audit
Targeted audit of Spotify Web API usage. Checks for deprecated endpoints, proper error handling, rate limiting, and token lifecycle.
## Agents
| Agent | Focus |
|-------|-------|
| **API Surface** | Deprecated endpoints (Audio Features, Recommendations), proper use of always-available data (popularity, genres, track names) |
| **Resilience** | SpotifyAuthError propagation, _safe_fetch patterns, asyncio.gather per-call error handling, InvalidToken → 401 |
## Checklist
### Deprecated API Detection
- [ ] No calls to `/audio-features` for new features
- [ ] No calls to `/recommendations` for new features
- [ ] Existing deprecated calls have `has_*` flags for frontend fallback
- [ ] Fallback UIs explain WHY data is missing (not silent empty)
### Error Handling
- [ ] Every router with SpotifyClient has `except SpotifyAuthError: raise` BEFORE `except Exception`
- [ ] `asyncio.gather` with 3+ calls uses `_safe_fetch()` per coroutine
- [ ] Non-critical DB writes (snapshots) wrapped in inner try/except
- [ ] Fernet InvalidToken raises SpotifyAuthError (not generic error)
### Rate Limiting
- [ ] `asyncio.Semaphore(10)` used for parallel API calls
- [ ] Rate limiter on auth endpoints uses IP (not full cookie) as key
- [ ] Stale rate limiter keys cleaned periodically
### Data Integrity
- [ ] No hardcoded fallback values that look like real data (e.g., `default=180000`)
- [ ] Missing data defaults to `0`, `None`, or empty — never a plausible fake value
- [ ] Time ranges: only `short_term`, `medium_term`, `long_term` (no custom ranges)
- [ ] Recently played: max 50 items communicated in UI
## Key Files
- `backend/app/services/spotify_client.py` — 12 API methods, Fernet encryption
- `backend/app/services/discovery.py` — genre/popularity analysis (no deprecated APIs)
- `backend/app/services/taste_evolution.py` — 3-period comparison, `_safe_fetch`
- `backend/app/services/temporal_patterns.py` — DB-accumulated history
- `backend/app/routers/*.py` — all 10 routers
- `backend/app/utils/rate_limiter.py` — rate limiting implementation
