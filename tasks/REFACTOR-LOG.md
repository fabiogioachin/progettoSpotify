# Refactor Log

Date: 2026-03-11
Description: Migrate PlaylistComparePage from deprecated audio features dependency to always-available metadata (popularity, genres, top tracks)
Triggered by: PlaylistComparePage shows empty data because it depends entirely on deprecated Spotify Audio Features API
Health findings: none

## Summary

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

## Slices

| # | Description | Files | Status |
|---|-------------|-------|--------|
| 1 | Add popularity_stats, genre_distribution, top_tracks, playlist_name to schema + enrich backend compare endpoint | schemas.py, playlists.py | ✅ |
| 2 | Rewrite PlaylistComparePage UI with always-available data sections | PlaylistComparePage.jsx | ✅ |

## Changes by File

| File | What Changed |
|------|-------------|
| backend/app/schemas.py | Added `PlaylistComparisonTopTrack` model; extended `PlaylistComparisonItem` with `playlist_name`, `popularity_stats`, `genre_distribution`, `top_tracks` fields (with defaults for backwards compat) |
| backend/app/routers/playlists.py | `compare_playlists()` now fetches playlist metadata (name), collects full track objects, computes popularity stats (avg/min/max), extracts genre distribution via artist batch fetch, selects top 5 tracks by popularity. Audio features still included if available from cache. |
| frontend/src/pages/PlaylistComparePage.jsx | Summary table shows playlist name, track count, avg popularity, top genre (always available) + audio feature columns (conditional). Added: popularity comparison bar chart, horizontal genre distribution chart, top tracks per playlist cards. Audio radar + PlaylistComparison charts kept as conditional when audio features exist. |

## Notes

- `ruff format --check` shows 22 pre-existing formatting issues across the project — not introduced by this refactor
- ESLint config is missing (eslint.config.js) — pre-existing issue, frontend verified via `npm run build` only
- Audio features are still fetched via `get_or_fetch_features` which may call the deprecated API; a future improvement could skip the API call entirely and only use cached DB values
