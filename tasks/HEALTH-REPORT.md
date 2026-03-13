# Project Health Report

Generated: 2026-03-13
Project: Spotify Listening Intelligence
Stack: FastAPI (Python 3.12) + React 18 / Vite / Tailwind
Mode: scan + targeted refactor

## Summary

| Metric | Count |
|--------|-------|
| Total findings | 8 |
| Auto-fixed | 1 (requirements split) |
| Manual action needed | 3 (deferred, low priority) |
| Spotify API violations | 0 |
| Security issues | 0 |
| Dead code | 0 new files |
| Dependencies cleaned | 4 packages moved to dev |

## Verification Status

| Check | Result |
|-------|--------|
| `ruff check app/` | All checks passed |
| `pytest tests/ -v` | 15/15 passed |
| `npm run build` | Built in 6.2s |

## Spotify API Audit (CLEAN)

All Spotify API calls verified safe — no deprecated endpoints, no 403/429 risks.

| Endpoint | Files | Status |
|----------|-------|--------|
| `/me/top/tracks`, `/me/top/artists` | spotify_client.py | Always available |
| `/me/player/recently-played` | spotify_client.py | Always available |
| `/me/playlists` | spotify_client.py | Always available |
| `/me/tracks` | spotify_client.py | Always available |
| `/artists/{id}` (individual) | audio_analyzer.py, discovery.py | Correct (no batch) |
| `/artists/{id}/related-artists` | spotify_client.py, discovery.py | Always available |
| `/tracks/{id}` (individual) | analysis.py | Correct (no batch) |
| `/playlists/{id}/items` | playlists.py, playlist_analytics.py, historical_tops.py | Correct (`/items` not `/tracks`) |
| `/v1/audio-features` | NOT CALLED | Deprecated, fully removed |
| `/v1/recommendations` | NOT CALLED | Deprecated, fully removed |
| Batch `/artists?ids=`, `/tracks?ids=` | NOT CALLED | Removed in dev mode |

### Rate Limiting

- SpotifyClient handles 429 with `Retry-After` header propagation
- Global cooldown (10-min threshold) prevents cascading rate limit escalation
- Semaphore(2) on all parallel API call sites (genres, related artists, track fetch)
- `retry_with_backoff` on all Spotify API calls in services

### Auth Error Propagation

All 25 `except Exception` blocks in routers are preceded by `except SpotifyAuthError: raise` — invariant holds.

## Applied Fix

### DEP-FIX-1: Split requirements.txt into prod/dev

| File | Change |
|------|--------|
| `requirements.txt` | Removed: `python-multipart`, `ruff`, `pytest`, `pytest-asyncio`, `soundfile` |
| `requirements-dev.txt` (NEW) | Created with `-r requirements.txt` + dev deps |

**Rationale**: `ruff`, `pytest`, `pytest-asyncio` are dev/CI tools. `soundfile` only used in tests. `python-multipart` unused (no `Form()` or `UploadFile` in any router). Prod image sheds ~200MB.

## Security Review (NEW CODE)

All new files from the Audio Features Recovery feature are secure:

| Check | Status |
|-------|--------|
| Auth on POST `/api/analyze-tracks` | `require_auth` dependency |
| Auth on GET `/api/analyze-tracks/{task_id}` | `require_auth` + ownership check (`user_id`) |
| Background task DB session | Dedicated `async_session()`, not request-scoped |
| In-memory task store bounded | Cleanup on POST + GET, per-user cap (3 concurrent) |
| Preview download size limit | 5 MB cap on `resp.content` |
| Temp file cleanup | `finally` block with `Path.unlink(missing_ok=True)` |
| Dict mutation safety | Clean copy via comprehension, no pop/re-add |
| Frontend polling | Recursive `setTimeout` (no overlap), `mountedRef` for unmount safety |
| `trackIds` stability | `useMemo` in both DashboardPage and DiscoveryPage |
| `startedRef` guard | Prevents duplicate POST requests |

## Deferred Items (low priority)

| # | Type | File | Issue | Effort |
|---|------|------|-------|--------|
| 1 | P2 | `audio_feature_extractor.py:226` | Sequential track processing (parallelize with Semaphore for >50 tracks) | ~30min |
| 2 | P2 | `DashboardPage.jsx:47` + `DiscoveryPage.jsx:48` | Duplicated feature averaging IIFE — extract to shared utility | ~10min |
| 3 | P2 | `requirements.txt` | librosa adds ~400MB to Docker image — consider optional extra or microservice | Architectural |

## Passed Checks (carried from previous report)

- SpotifyAuthError propagation in all handlers + inner helpers
- `asyncio.gather` safety: `_safe_fetch`/`_safe_compute`/`return_exceptions=True` in all parallel call sites
- Non-blocking DB writes (5 locations)
- No fake defaults / magic numbers
- All imports resolve correctly
- framer-motion used consistently for animations
- Skeleton loaders on all pages
- All UI text in Italian with "Cerchia" naming
- Period labels: `1M / 6M / All`
- Empty sections hidden
- No XSS vectors, no `dangerouslySetInnerHTML`
- CSRF mitigated via cookie-based same-origin auth
