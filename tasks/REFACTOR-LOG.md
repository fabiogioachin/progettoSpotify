# Refactor Log

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
