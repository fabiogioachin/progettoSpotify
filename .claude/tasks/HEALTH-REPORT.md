# Project Health Report

Generated: 2026-03-25
Project: Spotify Listening Intelligence (progettoWrap)
Stack: FastAPI (Python 3.12) + React 18 (Vite) + PostgreSQL 16 + Redis 7
Mode: scan + auto-fix

## Summary

| Metric | Count |
|--------|-------|
| Total findings | 9 |
| Auto-fixed | 5 |
| Manual action needed | 4 |
| Dead code removed | 1 endpoint + 1 function + 1 component (~70 lines) |
| Dependencies cleaned | 0 (2 missing flagged) |
| UI issues found | 4 |

## Auto-Applied Fixes

| # | Type | File | What Changed |
|---|------|------|-------------|
| 1 | DEAD-1 | `backend/app/routers/analytics.py` | Removed dead `/api/v1/analytics/features` endpoint (no frontend caller) |
| 2 | DEAD-2 | `backend/app/services/audio_analyzer.py` | Removed `save_snapshot()` (only caller was DEAD-1) |
| 3 | DEAD-3 | `frontend/src/components/ui/Skeleton.jsx` | Removed `SkeletonTrackRow` (exported but never imported) |
| 4 | UI-5 | `frontend/src/pages/DiscoveryPage.jsx` | Wrapped recommendations section in `{recommendations.length > 0 && ...}` guard |
| 5 | UI-6 | `frontend/src/pages/PlaylistAnalyticsPage.jsx` | Wrapped size distribution chart in `{sizeDistribution.length > 0 && ...}` guard |

**Verification**: backend ruff passed, frontend vite build passed, 250/250 backend tests passed.

## Manual Action Required

### MEDIUM

| # | ID | File | Issue | Suggested Fix | Effort |
|---|-----|------|-------|--------------|--------|
| 1 | UI-3 | `frontend/src/components/wrapped/slides/SlideArtistEvolution.jsx:16` | `<img>` with no fallback when artist has no image — renders broken image icon in Wrapped story | Add conditional render: if no imgUrl, show placeholder div with Music icon | 5 min |
| 2 | UI-4 | `frontend/src/components/wrapped/slides/SlideTopTracks.jsx:31,53` | `<img>` with no fallback for track #1 and tracks 2-5 — broken image icon in most visible Wrapped card | Add conditional render with placeholder div, same pattern as Outliers in DiscoveryPage | 10 min |

### LOW

| # | ID | File | Issue | Suggested Fix | Effort |
|---|-----|------|-------|--------------|--------|
| 3 | DEP-1 | `backend/requirements.txt` | `pytest` imported in 12 test files but not in `requirements.txt` | Already in `requirements-dev.txt` — **no action needed** | 0 min |
| 4 | DEP-2 | `backend/requirements-dev.txt` | `soundfile` imported in tests, only transitive dep of librosa | Add `soundfile>=0.12` to `requirements-dev.txt` | 1 min |

## Quick-Fix Commands

```bash
# Add missing test dependency
echo "soundfile>=0.12" >> backend/requirements-dev.txt
```

## Files Safe to Delete

None — all orphan files were cleaned in this run.

## Suggested Follow-Up Commands

No structural refactors needed — findings were isolated deletions and guards.
The two Wrapped slide image fallbacks (UI-3, UI-4) are small manual fixes.

## Invalidated by /feature on 2026-03-25

Feature: Artist Genre Cache + Cap Removal + Dead Table Cleanup
- Added `artist_genres` table (persistent genre cache, 7d TTL)
- Removed `listening_snapshots` table (dead)
- Removed playlist/genre caps (500 tracks, 200 tracks, 20/50 artists)
- Integrated genre cache into background jobs
Re-run `/health` for an updated report.
