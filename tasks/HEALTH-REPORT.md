# Health Report — 2026-03-12 (Post-Refactor)

## Backend (0 Critical, 0 Warning, 3 Suggestion)

### Critical — ✅ All fixed

| # | Status | Issue |
|---|--------|-------|
| C-1 | ✅ Fixed | Dead `get_playlist_tracks` + `get_artists` — deleted from `spotify_client.py` |

### Warning — ✅ All fixed

| # | Status | Issue |
|---|--------|-------|
| W-1 | ✅ Fixed | `discovery.py` gather — added `return_exceptions=True` + SpotifyAuthError re-raise |
| W-2 | ✅ Fixed | `artist_network.py` `fetch_related` — added `except SpotifyAuthError: raise` |
| W-3 | ✅ Fixed | `export.py` — added `logger`, `except Exception` handler |
| W-4 | ✅ Fixed | `export.py` safe_* closures — added `except SpotifyAuthError: raise` |
| W-5 | ✅ Fixed | `taste_evolution.py` `_safe_fetch` — added `except SpotifyAuthError: raise` |
| W-6 | ✅ Fixed | `playlists.py` `get_playlists` — added `except Exception` |
| W-7 | ✅ Fixed | `library.py` — added `except Exception` to `get_recent_tracks` + `get_saved_tracks` |
| W-8 | ✅ Fixed | `audio_analyzer.py` `_fetch_genres` — added `except SpotifyAuthError: raise` |

### Suggestion (open)

| # | File | Issue |
|---|------|-------|
| S-2 | `spotify_client.py` | `get_recommendations` calls deprecated endpoint, always falls back. Wastes API call. |
| S-4 | `rate_limiter.py:58` vs `main.py:87` | Default RPM=60 but app configures 120. Misleading default. |
| S-5 | `audio_analyzer.py:70-87` | `compute_trends` runs 3 profiles sequentially. Could parallelize with `asyncio.gather` for ~3x speedup. |

---

## Frontend (0 Critical, 0 Warning, 11 Suggestion)

### Critical — ✅ All fixed

| # | Status | Issue |
|---|--------|-------|
| C-1 | ✅ Fixed | `useSpotifyData.js` — parse `stableParams` inside callback |
| C-2 | ✅ Fixed | `App.jsx` — `/wrapped` route uses `ProtectedRoute withLayout={false}` |

### Warning — ✅ All fixed

| # | Status | Issue |
|---|--------|-------|
| W-1 | ✅ Fixed | "cluster" → "cerchie/cerchia" in ArtistNetworkPage + ArtistNetwork |
| W-2 | ✅ Fixed | "followers" → "follower" in ArtistNetwork tooltip |
| W-3 | ✅ Fixed | PlaylistComparePage: `LoadingSpinner` → `SkeletonCard` |
| W-4 | ✅ Fixed | ClaudeExportPanel: `LoadingSpinner` → `SkeletonCard` |
| W-5 | ✅ Fixed | `constants.js` period labels → `1M / 6M / All` (matches CLAUDE.md) |
| W-6 | ✅ Fixed | TasteEvolutionPage: empty ArtistColumn returns `null` instead of text |
| W-7 | ✅ Fixed | SlidePeakHours: "Dati non disponibili" → `null` |
| W-8 | ✅ Fixed | "piu" → "più" in TasteEvolutionPage + SessionStats |
| W-9 | ✅ Fixed | `usePlaylistCompare.js`: added `AbortController` |
| W-10 | ✅ Fixed | PlaylistComparePage: stale comparison depends on `JSON.stringify(selectedIds)` |

### Suggestion (open)

| # | File | Issue |
|---|------|-------|
| S-1 | `KPICard.jsx:30` | `value % 1` applied to strings (harmless but unclear). |
| S-2 | `ArtistNetwork.jsx:46-141` | Force simulation restarts on new array refs even if data unchanged. |
| S-3 | `ArtistNetwork.jsx:207-218` | No keyboard focus/aria-label on interactive SVG nodes. |
| S-4 | `ListeningHeatmap.jsx:102-118` | Inline `<style>` — move to globals.css or framer-motion. |
| S-5 | `StreakDisplay.jsx:25-42` | Inline `<style>` — same. |
| S-6 | `DashboardPage.jsx:54` | Combined loading blocks page on slowest endpoint. Progressive rendering possible. |
| S-7 | `PlaylistStatCard.jsx:21` | CSS `animate-slide-up` instead of framer-motion. |
| S-8 | `SessionStats.jsx:36` + `StreakDisplay.jsx:24` | Same CSS animation inconsistency. |
| S-9 | `DashboardPage.jsx:14-53` | Inconsistent indentation. |
| S-10 | `ClaudeExportPanel.jsx:132,143` | `border-border-hover` naming confusing. |
| S-11 | `SlideOutro.jsx:25-35` | html2canvas canvases accumulate on repeated clicks. |

---

## Passed Checks

- SpotifyAuthError propagation in all 11 **top-level router handlers** + all inner helpers
- Non-blocking DB writes (4 locations)
- No fake defaults / magic numbers
- Dev mode `/items` migration (3 active paths correct)
- Semaphore usage for batch calls (5 locations)
- Rate limiter middleware
- Token management (proactive + reactive refresh, Fernet, asyncio.Lock)
- Session security (HMAC state, signed cookies)
- Skeleton loaders on all main pages (including PlaylistCompare, ClaudeExport)
- framer-motion page transitions + stagger on all 7 main pages
- Period labels match CLAUDE.md convention (`1M / 6M / All`)
- All user-visible text uses "Cerchia/Cerchie" (not "Cluster")

## Summary

| Area | Critical | Warning | Suggestion |
|------|----------|---------|------------|
| Backend | 0 ✅ | 0 ✅ | 3 |
| Frontend | 0 ✅ | 0 ✅ | 11 |
| **Total** | **0** | **0** | **14** |

All critical and warning issues resolved. Only suggestions remain (low priority, some require behavior changes).
