# Project Health Report

Generated: 2026-03-12 (post-verification)
Project: Spotify Listening Intelligence
Stack: FastAPI (Python 3.12) + React 18 / Vite / Tailwind
Mode: scan + auto-fix + verification round

## Summary

| Metric | Count |
|--------|-------|
| Original suggestions (S-1–S-14) | 14 ✅ all resolved |
| Health auto-fixes | 5 ✅ applied |
| Refactor slices | 2 ✅ applied |
| Verification round fixes | 4 ✅ applied |
| Deferred (user decision) | 7 |

## Verification Status

| Check | Result |
|-------|--------|
| `ruff check app/` | ✅ All checks passed |
| `npm run build` | ✅ Built in ~5s |
| `npm run lint` | ✅ 0 errors, 227 warnings (pre-existing unused imports) |

## All Resolved Items

### Original Suggestions (14/14 done)

**Backend:**
| # | File | Fix |
|---|------|-----|
| S-2 | `spotify_client.py`, `discovery.py` | Removed deprecated `get_recommendations` + wasted API call |
| S-4 | `rate_limiter.py` | Default RPM 60→120 to match main.py |
| S-5 | `audio_analyzer.py` | Parallelized `compute_trends` with `asyncio.gather` + `_safe_compute` |

**Frontend:**
| # | File | Fix |
|---|------|-----|
| S-1 | `KPICard.jsx` | `typeof value === 'number'` guard on `value % 1` |
| S-2 | `ArtistNetwork.jsx` | `useMemo` dataKey + prevDataKeyRef to skip simulation restarts |
| S-3 | `ArtistNetwork.jsx` | `role="button"`, `tabIndex`, `aria-label`, `onKeyDown` on SVG nodes |
| S-4 | `ListeningHeatmap.jsx` | Inline `<style>` → globals.css |
| S-5 | `StreakDisplay.jsx` | Inline `<style>` → globals.css with `--circumference` CSS var |
| S-6 | `DashboardPage.jsx` | Progressive rendering — each section independent |
| S-7 | `PlaylistStatCard.jsx`, `StreakDisplay.jsx` | `animate-slide-up` → framer-motion `motion.div` |
| S-8 | `SessionStats.jsx` | `animate-slide-up` → framer-motion `motion.div` |
| S-9 | `DashboardPage.jsx` | Consistent 2-space indentation |
| S-10 | `ClaudeExportPanel.jsx` | `border-border-hover` → `border-surface-hover` |
| S-11 | `SlideOutro.jsx` | `canvas.remove()` cleanup after html2canvas |

### Health Auto-Fixes (5)

| # | File | Fix |
|---|------|-----|
| 1 | `globals.css` | Removed dead `.stagger-1–4` CSS classes |
| 2 | `SlideOutro.jsx` | Removed dead `objectUrl` variable |
| 3 | `SlideOutro.jsx` | Removed unused `i` map param |
| 4 | `globals.css` | Removed conflicting `transition` on `.progress-ring-circle` |
| 5 | `ArtistNetwork.jsx` | Added `role="img" aria-label` to parent SVG |

### Refactor Phase (2 slices)

| # | File | Fix |
|---|------|-----|
| 1 | `DashboardPage.jsx` | Unified KPI row — single StaggerContainer with per-card skeleton |
| 2 | `ArtistNetwork.jsx`, `globals.css` | Replaced Tailwind transition on SVG circles with `.artist-node` CSS |

### Verification Round Fixes (4)

| # | File | Fix |
|---|------|-----|
| 1 | `audio_analyzer.py:285` | **CRITICAL** — Added `except SpotifyAuthError: raise` in `get_or_fetch_features` |
| 2 | `StreakDisplay.jsx` | Removed unnecessary `useMemo` + unused `react` import |
| 3 | `ArtistNetwork.jsx:153` | Simplified useEffect deps from `[nodes, edges, nodeIndex, dataKey]` to `[dataKey, nodeIndex]` |
| 4 | `KPICard.jsx:106` | Added `e.preventDefault()` on keyboard scroll handler |

## Deferred Items (user decision required)

### Security Hardening

| # | File | Issue | Impact | When needed |
|---|------|-------|--------|-------------|
| 1 | `rate_limiter.py` | Behind proxy, `client.host` = proxy IP — per-user limiting ineffective | Rate limiting bypassed | Production deploy behind proxy |
| 2 | `rate_limiter.py` | `_requests` dict grows unbounded under high traffic | Memory exhaustion (DoS) | Public deploy with many users |
| 3 | `spotify_client.py` | Spotify IDs not validated against `^[a-zA-Z0-9]{22}$` | Path injection (theoretical) | Adding user-input endpoints |
| 4 | `spotify_client.py` | Error messages expose HTTP status codes to frontend | Info disclosure (minor) | UX polish |

### Code Simplification

| # | File | Issue | Effort |
|---|------|-------|--------|
| 5 | `audio_analyzer.py:133-161` | `save_snapshot` field assignments duplicated in update/insert branches | ~10min |
| 6 | `discovery.py:125,148,170` | Album-image extraction pattern repeated 3x — extract helper | ~5min |
| 7 | `SessionStats.jsx:24-28` | `mounted` state + useEffect replaceable with framer-motion | ~15min |

## Passed Checks

- SpotifyAuthError propagation in all router handlers + inner helpers (including newly fixed `get_or_fetch_features`)
- asyncio.gather safety: `_safe_fetch`/`_safe_compute`/`return_exceptions=True` in all 3+ parallel call sites
- Non-blocking DB writes (4 locations)
- No fake defaults / magic numbers
- All imports resolve correctly
- framer-motion used consistently for animations (CSS `animate-slide-up` fully eliminated)
- Skeleton loaders on all main pages
- All UI text in Italian with "Cerchia" naming
- Period labels match convention (`1M / 6M / All`)
- Empty sections hidden (no "nessun dato disponibile")
- No XSS vectors, no `dangerouslySetInnerHTML`
- CSRF mitigated via cookie-based same-origin auth
- html2canvas captures only non-sensitive summary data
