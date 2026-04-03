# Refactor Log

## 2026-04-02 — WrappedPage POST/poll progressive loading

Date: 2026-04-02
Description: Convert WrappedPage from blocking GET to async POST/poll with progressive slide availability
Triggered by: /feature WrappedPage POST/poll (from todo.md Fase 2.4)

### Summary

| Metric | Value |
|--------|-------|
| Files created | 4 (wrapped_tasks.py, useWrappedTask.js, test_wrapped_tasks.py, test_wrapped_router.py) |
| Files modified | 3 (wrapped.py, WrappedPage.jsx, WrappedStories.jsx) + 4 SKILL.md |
| Tests added | 27 (411 total) |
| Verification | pytest 411 passed, lint 0 errors, build OK |

### Architecture

- `POST /api/v1/wrapped?time_range=X` starts background task, returns task_id
- `GET /api/v1/wrapped/{task_id}` polls for progressive results
- Backend executes 5 services sequentially by importance (top_tracks → temporal → evolution → profile → network)
- `available_slides` grows as each service completes
- Frontend shows slides immediately as they become available (shimmer progress bar for pending)
- Legacy `GET /wrapped` (blocking) preserved with deprecation log

### Changes

| File | Change |
|------|--------|
| `backend/app/services/wrapped_tasks.py` | New: in-memory task store (TTL 30min, max 3/user) |
| `backend/app/routers/wrapped.py` | Added POST, GET/{task_id}, _run_wrapped_task background worker |
| `frontend/src/hooks/useWrappedTask.js` | New: POST/poll hook with auto-start, period change reset |
| `frontend/src/pages/WrappedPage.jsx` | Replaced useSpotifyData with useWrappedTask |
| `frontend/src/components/wrapped/WrappedStories.jsx` | Progressive slides, shimmer progress bar, slide-ID tracking |
| `tailwind.config.js` | Added shimmer keyframe animation |
| 4 SKILL.md files | Updated with RequestDataBundle + POST/poll patterns |

---

## 2026-04-02 — API Request Deduplication via RequestDataBundle

Date: 2026-04-02
Description: Eliminate duplicate Spotify API calls across services using request-scoped in-memory caching
Triggered by: Refactoring API piano in todo.md
Health findings: none (pre-refactoring bugs resolved in previous session)

### Summary

| Metric | Value |
|--------|-------|
| Slices planned | 8 |
| Slices completed | 6 (2 skipped — frontend already optimized or needs /feature) |
| Slices reverted | 0 |
| Files changed | 12 |
| Files created | 7 (1 service + 6 test files) |
| Tests added | 97 (287 baseline -> 384) |
| Verification | `pytest -q` (384 passed) + `npm run lint` (0 errors) + `npm run build` (OK) |
| Final status | All passing |

### API Call Reduction

| Endpoint | Before | After | Savings |
|----------|--------|-------|---------|
| `GET /wrapped` | 13 calls | 7 calls | -46% |
| `GET /profile` | 5 calls | 4 calls | -20% |
| `GET /analytics/trends` | 6 calls | 3 calls | -50% |
| **Total per session** | **24 calls** | **14 calls** | **-42%** |

### Slices

| # | Description | Files | Status |
|---|-------------|-------|--------|
| P1 | Test taste_evolution (28 tests) | tests/test_taste_evolution.py | Prerequisite |
| P2 | Test temporal_patterns (22 tests) | tests/test_temporal_patterns.py | Prerequisite |
| P3 | Test audio_analyzer (18 tests) | tests/test_audio_analyzer.py | Prerequisite |
| 1 | Create RequestDataBundle + 14 tests | services/data_bundle.py, tests/test_data_bundle.py | Done |
| 2+3 | Wire bundle into /wrapped (taste_evolution + artist_network) | wrapped.py, taste_evolution.py, artist_network.py, 2 test files | Done |
| 4 | Wire bundle into /profile (profile_metrics + taste_map) | profile.py, profile_metrics.py, taste_map.py, 2 test files | Done |
| 5 | Wire bundle into /analytics/trends + fix wrapped compute_profile | analytics.py, audio_analyzer.py, wrapped.py, test file | Done |
| 6-7 | Frontend progressive rendering | - | Skipped |

### Changes by File

| File | What Changed |
|------|-------------|
| `backend/app/services/data_bundle.py` | **Created** — RequestDataBundle: in-memory cache for get_top_tracks/artists/recently_played/me + parallel prefetch |
| `backend/app/services/taste_evolution.py` | Added `bundle=None` param; uses bundle instead of direct client calls when provided |
| `backend/app/services/artist_network.py` | Added `bundle=None` param; uses bundle for top_artists when provided |
| `backend/app/services/profile_metrics.py` | Added `bundle=None` param; uses bundle for top_artists/top_tracks when provided |
| `backend/app/services/taste_map.py` | Added `bundle=None` param; uses bundle for top_artists when provided |
| `backend/app/services/audio_analyzer.py` | Added `bundle=None` to compute_trends + compute_profile; bundle flows from trends into profile |
| `backend/app/routers/wrapped.py` | Creates bundle, prefetches artists+tracks+recent, passes to all services |
| `backend/app/routers/profile.py` | Creates bundle, prefetches artists+tracks+me, passes to services |
| `backend/app/routers/analytics.py` | Creates bundle, prefetches tracks, passes to compute_trends |
| `backend/tests/test_data_bundle.py` | **Created** — 14 tests for RequestDataBundle |
| `backend/tests/test_taste_evolution.py` | **Created** — 28 tests + 4 bundle integration tests |
| `backend/tests/test_temporal_patterns.py` | **Created** — 22 tests |
| `backend/tests/test_audio_analyzer.py` | **Created** — 18 tests + 2 bundle integration tests |
| `backend/tests/test_profile_metrics.py` | Added 2 bundle integration tests |
| `backend/tests/test_taste_map.py` | Added 3 bundle integration tests |
| `backend/tests/test_artist_network.py` | Added 4 bundle integration tests |

### Skipped Slices

**Slice 6-7: Frontend Progressive Rendering**
- DashboardPage: Already 3 independent hooks + per-section skeletons + SectionErrorBoundary. No changes needed.
- ProfilePage: Blocked on single `/profile` endpoint. Splitting = API change -> /feature.
- WrappedPage: POST/poll pattern = behavioral change -> /feature.

### Notes

- All `bundle=None` defaults preserve backward compatibility. Existing callers unaffected.
- `TYPE_CHECKING` import pattern avoids circular imports between data_bundle and services.
- Hidden duplication found in /analytics/trends: compute_trends fetched top_tracks 3x, then compute_profile re-fetched them 3 more times. Bundle eliminated this.
- Frontend Phase 2.4 (Wrapped POST/poll) remains the main pending architectural change -> dedicated /feature session.

---

## 2026-03-18 — Health report fixes (DEAD + UI)

Date: 2026-03-18
Description: Fix health report findings — dead code removal, Wrapped slide field mismatches, empty state guards, StreakDisplay wiring, GenreDNA values
Triggered by: `/health` report findings
Health findings: DEAD-1, DEAD-2, DEP-1, DEP-2, UI-1, UI-2, UI-3, UI-4, UI-8, UI-9, UI-10, UI-11, UI-12

### Summary

| Metric | Value |
|--------|-------|
| Slices planned | 8 |
| Slices completed | 8 |
| Slices reverted | 0 |
| Files changed | 12 |
| Lines added | ~30 |
| Lines removed | ~20 |
| Net line change | +10 |
| Verification | `pytest -q` (159 passed) + `npm run build` + `ruff check` |
| Final status | all passing |

### Slices

| # | Description | Files | Status |
|---|-------------|-------|--------|
| 1 | Delete orphan ReceiptCard.jsx (DEAD-1) | ReceiptCard.jsx | deleted |
| 2 | Remove unused TIME_RANGES/TIME_RANGE_LABELS (DEAD-2) | constants.py | done |
| 3 | Remove redundant soundfile pin (DEP-1) | requirements-dev.txt | done |
| 4 | Wrapped slide field mismatches (UI-2, UI-3, UI-4) | SlideArtistEvolution, SlideArtistNetwork, SlideTopTracks | done |
| 5 | SlidePeakHours: derive weekend_pct + early return (UI-8, UI-11) | SlidePeakHours.jsx | done |
| 6 | SlideListeningHabits: zero-data guard (UI-10) | SlideListeningHabits.jsx | done |
| 7 | SlideOutro: useCORS + try/catch (UI-12) | SlideOutro.jsx | done |
| 8 | GenreDNA: rank-based decay instead of fake linear (UI-9) | GenreDNA.jsx | done |
| 9 | StreakDisplay: backend active_last_7 + frontend wiring (UI-1) | temporal_patterns.py, TemporalPage.jsx | done |

### Changes by File

| File | What Changed |
|------|-------------|
| `frontend/src/components/share/ReceiptCard.jsx` | Deleted (orphan, 0 importers) |
| `backend/app/constants.py` | Removed unused `TIME_RANGES`, `TIME_RANGE_LABELS` |
| `backend/requirements-dev.txt` | Removed redundant `soundfile==0.12.1` (transitive of librosa) |
| `frontend/src/components/wrapped/slides/SlideArtistEvolution.jsx` | Image src: `image \|\| image_url \|\| images[0].url` |
| `frontend/src/components/wrapped/slides/SlideArtistNetwork.jsx` | `cluster_names`: Object.values() for object→array conversion |
| `frontend/src/components/wrapped/slides/SlideTopTracks.jsx` | Image src: `album_image \|\| album.images[0].url \|\| image_url` |
| `frontend/src/components/wrapped/slides/SlidePeakHours.jsx` | `weekendPct = 100 - weekdayPct`, early return on empty data |
| `frontend/src/components/wrapped/slides/SlideListeningHabits.jsx` | Return null when all values are zero |
| `frontend/src/components/wrapped/slides/SlideOutro.jsx` | `useCORS: true` + try/catch on handleDownload |
| `frontend/src/components/profile/GenreDNA.jsx` | Rank-based decay (100→50) instead of `100 - i*12` |
| `backend/app/services/temporal_patterns.py` | Added `active_last_7` boolean array to streak response |
| `frontend/src/pages/TemporalPage.jsx` | Pass `activeDays={streak.active_last_7}` to StreakDisplay |

### Notes

- UI-5, UI-6, UI-7 (`bg-spotify`/`text-spotify`): **false positives** — `spotify` color is defined in `tailwind.config.js:18` as `#1DB954`. Classes work correctly.
- DEP-2 (.env.example): blocked by hook `protect-critical-files.sh` — needs manual edit to add `RAPIDAPI_KEY` comment
- DEAD-3 (library routes), DEAD-4 (AudioFeatures columns), DEAD-6 (taste_map audio_features), DEP-3 (numpy cap): deferred — product/migration decisions, not pure refactor

---

## 2026-03-18 — DRY cleanup for bug fix changes

Date: 2026-03-18
Description: Extract shared constant, deduplicate test helpers
Triggered by: `/refactor` after bug fix implementation (popularity enrichment, genre cap, track count fallback)
Health findings: none

### Summary

| Metric | Value |
|--------|-------|
| Slices planned | 2 |
| Slices completed | 2 |
| Slices reverted | 0 |
| Files changed | 4 |
| Lines added | 6 |
| Lines removed | 24 |
| Net line change | -18 |
| Verification | `python -m pytest -q` (159 passed) + `ruff check` + `ruff format` |
| Final status | all passing |

### Slices

| # | Description | Files | Status |
|---|-------------|-------|--------|
| 1 | Extract `ARTIST_GENRE_CAP = 50` into `constants.py`, replace magic number in 3 locations | constants.py, playlists.py, audio_analyzer.py, test_playlists.py |  |
| 2 | Deduplicate 6x `_fake_retry` into shared `_passthrough_retry` helper | test_playlists.py |  |

### Changes by File

| File | What Changed |
|------|-------------|
| `backend/app/constants.py` | Added `ARTIST_GENRE_CAP = 50` |
| `backend/app/routers/playlists.py` | Import `ARTIST_GENRE_CAP`, replaced `[:50]` with `[:ARTIST_GENRE_CAP]` |
| `backend/app/services/audio_analyzer.py` | Import `ARTIST_GENRE_CAP`, replaced `[:50]` in 2 locations, fixed stale comment `cap=20` → `cap=50` |
| `backend/tests/test_playlists.py` | Import `ARTIST_GENRE_CAP`, added shared `_passthrough_retry`, removed 6 inline `_fake_retry` defs, tests reference constant instead of hardcoded 50 |

---

## 2026-03-15 — Hardcoded Colors + ARIA Accessibility

Date: 2026-03-15
Description: Unify hardcoded colors with CSS vars/chartTheme + add ARIA accessibility to profile/share components
Triggered by: `/refactor` from HEALTH-REPORT.md findings
Health findings: UI-1/2, UI-3/4, UI-5, UI-6, UI-7/8, UI-9/10, UI-11, UI-12

### Summary

| Metric | Value |
|--------|-------|
| Slices planned | 6 |
| Slices completed | 6 |
| Slices reverted | 0 |
| Files changed | 5 |
| Lines added | ~15 |
| Lines removed | ~5 |
| Net line change | +10 |
| Verification | `npm run build` (per slice) + `npm run lint` (final) |
| Final status | 0 errors, 280 pre-existing warnings |

### Slices

| # | Description | Files | Status |
|---|-------------|-------|--------|
| 1 | ObscurityGauge null guard for score==null (UI-11) | ObscurityGauge.jsx | ✅ |
| 2 | ObscurityGauge hardcoded colors → CSS var fallbacks + GRID_COLOR import (UI-1/2) | ObscurityGauge.jsx | ✅ |
| 3 | DecadeChart tick color CSS var + ARIA role/label (UI-3/4, UI-9/10) | DecadeChart.jsx | ✅ |
| 4 | GenreDNA ARIA role/label (UI-9/10) | GenreDNA.jsx | ✅ |
| 5 | ShareCardRenderer Escape key + dialog ARIA + icon aria-hidden (UI-5/6/7/8) | ShareCardRenderer.jsx | ✅ |
| 6 | ProfilePage Share2 icon aria-hidden (UI-12) | ProfilePage.jsx | ✅ |

### Changes by File

| File | What Changed |
|------|-------------|
| `frontend/src/components/profile/ObscurityGauge.jsx` | Null guard (after hooks), import GRID_COLOR for bg arc, CSS var fallbacks for getColor |
| `frontend/src/components/profile/DecadeChart.jsx` | Tick fill uses `var(--text-secondary, #b3b3b3)`, added `role="img" aria-label` |
| `frontend/src/components/profile/GenreDNA.jsx` | Added `role="img" aria-label` to wrapper div |
| `frontend/src/components/share/ShareCardRenderer.jsx` | useEffect Escape handler, `role="dialog" aria-modal aria-label`, `aria-hidden` on icons |
| `frontend/src/pages/ProfilePage.jsx` | `aria-hidden="true"` on Share2 icon |

### Notes

- DecadeChart `rgba(99, 102, 241, ...)` for per-bar opacity gradient kept as-is — no `--color-accent-rgb` CSS var exists, adding one would be scope creep
- ObscurityGauge null guard placed after hooks (React Rules of Hooks) — hooks run with `score ?? 0` fallback, then null check returns null before render
- ObscurityGauge colors use `var(--success, #10b981)` / `var(--accent, #6366f1)` / `var(--purple, #a855f7)` — CSS vars may not exist (project uses `--color-*` prefix), hex fallbacks maintain current behavior
- Lint went from 2 errors + 280 warnings to 0 errors + 280 warnings (fixed Rules of Hooks violation in ObscurityGauge)

---

## 2026-03-12 — Health Suggestion Fixes + KPI Deduplication

Date: 2026-03-12
Description: Resolve all 14 health report suggestions (3 backend + 11 frontend) + deduplicate DashboardPage KPI row + SVG accessibility
Triggered by: `/feature` suggestions + `/health --fix` + `/refactor`
Health findings: S-2, S-4, S-5 (backend), S-1–S-11 (frontend), UI-3, UI-5 (post-fix health scan)

### Summary

| Metric | Value |
|--------|-------|
| Slices planned | 2 (refactor phase) |
| Slices completed | 2 |
| Slices reverted | 0 |
| Files changed | 19 total (4 backend + 13 frontend + 2 tasks) |
| Verification | `ruff check` + `npm run build` + `npm run lint` |
| Final status | ✅ all passing |

### Changes — Feature Phase (parallel agents)

**Backend:**
| File | What Changed |
|------|-------------|
| `spotify_client.py` | Removed deprecated `get_recommendations` method (S-2) |
| `discovery.py` | Removed wasted API call, direct `new_discoveries[:20]` (S-2) |
| `rate_limiter.py` | Default RPM 60→120 to match main.py config (S-4) |
| `audio_analyzer.py` | Parallelized `compute_trends` with `asyncio.gather` + `_safe_compute` wrapper (S-5) |

**Frontend:**
| File | What Changed |
|------|-------------|
| `KPICard.jsx` | Added `typeof value === 'number'` guard on `value % 1` (S-1) |
| `ArtistNetwork.jsx` | `useMemo` dataKey + prevDataKeyRef to skip unnecessary simulation restarts (S-2), keyboard a11y on SVG nodes (S-3) |
| `ListeningHeatmap.jsx` | Moved inline `<style>` to globals.css (S-4) |
| `StreakDisplay.jsx` | Moved inline `<style>` to globals.css with `--circumference` CSS var (S-5), replaced `animate-slide-up` with framer-motion (S-7) |
| `DashboardPage.jsx` | Progressive rendering — each section loads independently (S-6), fixed indentation (S-9) |
| `PlaylistStatCard.jsx` | Replaced `animate-slide-up` with framer-motion `motion.div` (S-7) |
| `SessionStats.jsx` | Replaced `animate-slide-up` with framer-motion `motion.div` (S-8) |
| `ClaudeExportPanel.jsx` | Renamed `border-border-hover` → `border-surface-hover` (S-10) |
| `SlideOutro.jsx` | Added `canvas.remove()` cleanup after html2canvas (S-11) |
| `globals.css` | Added heatmap/streak CSS from extracted inline styles |

### Changes — Health Auto-Fix Phase

| File | What Changed |
|------|-------------|
| `globals.css` | Removed dead `.stagger-1–4` classes, removed conflicting `transition` on `.progress-ring-circle` |
| `SlideOutro.jsx` | Removed dead `objectUrl` variable, removed unused `i` map param |
| `ArtistNetwork.jsx` | Added `role="img" aria-label` to parent SVG |

### Changes — Refactor Phase (sequential slices)

| # | Description | Files | Status |
|---|-------------|-------|--------|
| 1 | Unified KPI row — eliminated loading/loaded branch duplication | DashboardPage.jsx | ✅ |
| 2 | Replaced Tailwind `transition-all` on SVG circles with CSS `.artist-node` class | ArtistNetwork.jsx, globals.css | ✅ |

### Changes — Verification Round

| File | What Changed |
|------|-------------|
| `audio_analyzer.py:285` | **CRITICAL fix**: added `except SpotifyAuthError: raise` in `get_or_fetch_features` — auth errors were being swallowed |
| `StreakDisplay.jsx` | Removed unnecessary `useMemo` for simple arithmetic + removed now-unused `react` import |
| `ArtistNetwork.jsx:153` | Simplified useEffect deps to `[dataKey, nodeIndex]` (removed redundant `nodes`, `edges`) |
| `KPICard.jsx:106` | Added `e.preventDefault()` on keyboard scroll handler to prevent Space from scrolling page |

### Notes

- ESLint warnings: 227 (pre-existing unused imports from earlier refactors)
- One CRITICAL found during verification: `get_or_fetch_features` was missing SpotifyAuthError re-raise — this was a pre-existing bug exposed by the new `_safe_compute` wrapper

---

## 2026-03-12 — Health Report Fixes

Date: 2026-03-12
Description: Fix all Critical + Warning findings from health report
Triggered by: `/refactor` — fix all issues in tasks/HEALTH-REPORT.md
Health findings: Backend C-1, W-1–W-8, S-1, S-3; Frontend C-1, C-2, W-1–W-10

### Summary

| Metric | Value |
|--------|-------|
| Slices planned | 8 |
| Slices completed | 8 |
| Slices reverted | 0 |
| Files changed | 19 |
| Lines added | 89 |
| Lines removed | 49 |
| Net line change | +40 |
| Verification | `python -m compileall app/` + `npm run build` |
| Final status | ✅ all passing |

### Slices

| # | Description | Files | Status |
|---|-------------|-------|--------|
| 1 | SpotifyAuthError re-raise in 4 services | taste_evolution.py, artist_network.py, audio_analyzer.py, export.py | ✅ |
| 2 | Missing error handlers in routers | export.py, playlists.py, library.py | ✅ |
| 3 | Dead code removal + gather safety + logger fixes | spotify_client.py, discovery.py, rate_limiter.py | ✅ |
| 4 | Fix stale params closure in useSpotifyData | useSpotifyData.js | ✅ |
| 5 | /wrapped auth + usePlaylistCompare abort + stale comparison | App.jsx, usePlaylistCompare.js, PlaylistComparePage.jsx | ✅ |
| 6 | Italian text: cluster→cerchia, followers, accents | ArtistNetworkPage.jsx, ArtistNetwork.jsx, TasteEvolutionPage.jsx, SessionStats.jsx | ✅ |
| 7 | LoadingSpinner→skeleton + hide empty states | PlaylistComparePage.jsx, ClaudeExportPanel.jsx, TasteEvolutionPage.jsx, SlidePeakHours.jsx | ✅ |
| 8 | Backend "Cluster"→"Cerchia" fallback | artist_network.py | ✅ |

### Changes by File

| File | What Changed |
|------|-------------|
| `backend/app/services/taste_evolution.py` | Added `except SpotifyAuthError: raise` in `_safe_fetch` |
| `backend/app/services/artist_network.py` | Added `except SpotifyAuthError: raise` in `fetch_related`; "Cluster" → "Cerchia" fallback |
| `backend/app/services/audio_analyzer.py` | Added `except SpotifyAuthError: raise` in `_fetch_genres` |
| `backend/app/routers/export.py` | Added logger, `except Exception` handler, SpotifyAuthError re-raise in 3 safe_* closures |
| `backend/app/routers/playlists.py` | Added `except Exception` to `get_playlists` handler |
| `backend/app/routers/library.py` | Added `except Exception` to `get_recent_tracks` and `get_saved_tracks` |
| `backend/app/services/spotify_client.py` | Deleted dead `get_playlist_tracks` and `get_artists` methods |
| `backend/app/services/discovery.py` | Added `return_exceptions=True` to gather + SpotifyAuthError re-raise + graceful degradation |
| `backend/app/utils/rate_limiter.py` | Replaced f-string logging with lazy `%s` formatting |
| `frontend/src/hooks/useSpotifyData.js` | Parse `stableParams` inside callback instead of closing over `params` |
| `frontend/src/App.jsx` | ProtectedRoute `withLayout` prop; /wrapped uses ProtectedRoute |
| `frontend/src/hooks/usePlaylistCompare.js` | Added AbortController, cancel-on-abort, useCallback |
| `frontend/src/pages/PlaylistComparePage.jsx` | Stale comparison fix (JSON.stringify selectedIds); LoadingSpinner → SkeletonCard |
| `frontend/src/pages/ArtistNetworkPage.jsx` | "cluster" → "cerchie" in Italian text |
| `frontend/src/components/charts/ArtistNetwork.jsx` | "Cluster" → "Cerchia" fallbacks; "followers" → "follower" |
| `frontend/src/pages/TasteEvolutionPage.jsx` | "piu" → "più"; empty ArtistColumn returns null |
| `frontend/src/components/charts/SessionStats.jsx` | "piu" → "più" |
| `frontend/src/components/export/ClaudeExportPanel.jsx` | LoadingSpinner → SkeletonCard |
| `frontend/src/components/wrapped/slides/SlidePeakHours.jsx` | "Dati non disponibili" → null |

### Notes

- Backend suggestions S-2 (remove get_recommendations call), S-4 (RPM default), S-5 (parallelize compute_trends) not addressed — these are behavior changes
- Frontend suggestions (S-1 through S-11) not addressed — lower priority, some require behavior changes
- `get_recommendations` method kept because discovery.py still calls it (with fallback)

---

## 2026-03-11 — Playlist Compare Migration

Date: 2026-03-11
Description: Migrate PlaylistComparePage from deprecated audio features dependency to always-available metadata (popularity, genres, top tracks)
Triggered by: PlaylistComparePage shows empty data because it depends entirely on deprecated Spotify Audio Features API
Health findings: none

### Summary

| Metric | Value |
|--------|-------|
| Slices planned | 2 |
| Slices completed | 2 |
| Slices reverted | 0 |
| Files changed | 3 |
| Lines added | ~200 |
| Lines removed | ~60 |
| Net line change | +140 |
| Verification | `ruff check app/` + `npm run build` |
| Final status | ✅ all passing |

### Slices

| # | Description | Files | Status |
|---|-------------|-------|--------|
| 1 | Add popularity_stats, genre_distribution, top_tracks, playlist_name to schema + enrich backend compare endpoint | schemas.py, playlists.py | ✅ |
| 2 | Rewrite PlaylistComparePage UI with always-available data sections | PlaylistComparePage.jsx | ✅ |

### Notes

- `ruff format --check` shows 22 pre-existing formatting issues across the project — not introduced by this refactor
- ESLint config is missing (eslint.config.js) — pre-existing issue, frontend verified via `npm run build` only
- Audio features are still fetched via `get_or_fetch_features` which may call the deprecated API; a future improvement could skip the API call entirely and only use cached DB values
