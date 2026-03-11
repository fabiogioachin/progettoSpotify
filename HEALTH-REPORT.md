# Project Health Report

Generated: 2026-03-11
Project: Spotify Listening Intelligence
Stack: FastAPI (Python 3.12) + React 18 / Vite / Tailwind CSS
Mode: scan + auto-fix

## Summary

| Metric | Count |
|--------|-------|
| Total findings | 16 |
| Auto-fixed | 14 |
| Manual action needed | 2 |
| Dead code removed | 3 files, ~55 lines + 3 unused exports + 3 dead EmptyState functions |
| Dependencies cleaned | 0 (all clean) |
| UI issues fixed | 8 (convention violations + duplicate section + dead expression) |
| Bug fix | not requested |

## Verification

- `npm run build` — passed
- `ruff check app/` — passed
- No regressions introduced

## Auto-Applied Fixes

| # | Type | File | What Changed |
|---|------|------|-------------|
| 1 | DEAD | `backend/app/models/playlist.py` | Deleted (orphan file, `PlaylistCache` model never used) |
| 2 | DEAD | `backend/app/models/track.py` | Removed dead `Track` class, kept `AudioFeatures` |
| 3 | DEAD | `frontend/src/components/layout/DashboardGrid.jsx` | Deleted (orphan file, 3 components never imported) |
| 4 | DEAD | `frontend/src/hooks/useAuth.js` | Deleted (dead re-export, all consumers import from AuthContext directly) |
| 5 | DEAD | `frontend/src/lib/constants.js` | Removed unused `FEATURE_KEYS` export |
| 6 | DEAD | `frontend/src/lib/chartTheme.js` | Removed unused `CHART_COLORS` export |
| 7 | UI | `frontend/src/pages/ArtistNetworkPage.jsx` | Removed duplicate genre cloud section (copy-paste bug) |
| 8 | UI | `frontend/src/components/charts/AudioRadar.jsx` | Return `null` instead of EmptyState; removed dead `EmptyState` function |
| 9 | UI | `frontend/src/components/charts/TrendTimeline.jsx` | Return `null` instead of EmptyState; removed dead `EmptyState` function |
| 10 | UI | `frontend/src/pages/DiscoveryPage.jsx:100` | Removed "Nessun outlier trovato" visible empty state |
| 11 | UI | `frontend/src/pages/DiscoveryPage.jsx:157` | Removed "Nessun suggerimento disponibile" visible empty state |
| 12 | UI | `frontend/src/pages/DiscoveryPage.jsx:170` | `PopularityDistribution` returns `null` when empty |
| 13 | UI | `frontend/src/components/charts/PlaylistComparison.jsx` | Return `null` instead of EmptyState; removed dead `EmptyState` function |
| 14 | UI | `frontend/src/pages/DashboardPage.jsx:129` | Removed dead expression `{tracks.length === 0 && null}` |

## Manual Action Required

### MEDIUM / P2

| # | ID | File | Issue | Suggested Fix | Effort |
|---|-----|------|-------|--------------|--------|
| 1 | UI-9 | `frontend/src/pages/TemporalPage.jsx:84` | `StreakDisplay` receives no `activeDays` prop — 7-day calendar always shows all days inactive | Pass `streak.active_days` from backend temporal data | 5 min |

### LOW / P3

| # | ID | File | Issue | Suggested Fix | Effort |
|---|-----|------|-------|--------------|--------|
| 2 | UI-7 | `frontend/src/pages/TasteEvolutionPage.jsx:55-56` | Empty column messages in artist grid ("Nessun nuovo artista" etc.) | Consider hiding empty columns or entire row when all are empty | 5 min |

## Dependencies

All clean. No unused, missing, misplaced, circular, or duplicate dependencies found. Backend service graph is a clean DAG.

## Suggested Follow-Up Commands

| Condition | Suggested Command | Scope |
|-----------|------------------|-------|
| StreakDisplay missing data wiring (UI-9) | Manual investigation | `TemporalPage.jsx` + `StreakDisplay.jsx` + backend `/api/temporal` |
