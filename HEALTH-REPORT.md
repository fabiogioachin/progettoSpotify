# Project Health Report

Generated: 2026-03-21
Project: Spotify Listening Intelligence
Stack: FastAPI (Python 3.12) + React 18 (Vite + Tailwind)
Mode: scan + auto-fix

## Summary

| Metric | Count |
|--------|-------|
| Total findings | 19 |
| Auto-fixed | 4 |
| Manual action needed | 15 |
| Dead code removed | 4 schemas (~30 lines) |
| Dependencies cleaned | 0 |
| UI issues found | 12 |

## Auto-Applied Fixes

| # | Type | File | What Changed |
|---|------|------|-------------|
| 1 | DEAD-1 | `backend/app/schemas.py` | Removed 4 unused Pydantic models (`RecentTrackResponse`, `RecentTracksResponse`, `SavedTrackResponse`, `SavedTracksResponse`) — 0 importers |
| 2 | UI-2 | `frontend/src/pages/DiscoveryPage.jsx` | Fixed popularity chart guard: now checks both `has_popularity_data` flag AND `popularityDistribution.length > 0` |
| 3 | UI-3 | `frontend/src/pages/ArtistNetworkPage.jsx` | Removed dead `clusterIndexMap` variable in CerchieSection (never referenced) |
| 4 | UI-7 | `frontend/src/components/cards/PlaylistStatCard.jsx` | Replaced `#1DB954` (Spotify green) with `#6366f1` (accent indigo) in variety bar |

## Manual Action Required

### HIGH / P1

| # | ID | File | Issue | Suggested Fix | Effort |
|---|-----|------|-------|--------------|--------|
| 1 | UI-1 | `components/charts/SessionStats.jsx:118` | Weekend bar uses `bg-spotify` (reserved for branding) | Replace with `bg-accent-hover` | 1 min |
| 2 | UI-4 | `pages/TasteEvolutionPage.jsx:147` | Calendar icon uses `text-spotify` | Replace with `text-accent` | 1 min |
| 3 | UI-5 | `pages/TemporalPage.jsx:68,73` | TrendingUp icon + span use `text-spotify` | Replace with `text-accent` | 1 min |
| 4 | UI-6 | `pages/TasteEvolutionPage.jsx:177` | Year buttons active state uses `bg-spotify` | Replace with `bg-accent` | 1 min |
| 5 | UI-9 | `components/wrapped/slides/SlideArtistEvolution.jsx:16` | Artist image renders broken when no image URL | Add conditional render with fallback avatar | 5 min |
| 6 | UI-10 | `components/wrapped/slides/SlideTopTracks.jsx:31` | Same broken image issue as UI-9 | Add conditional render with fallback | 5 min |
| 7 | DEP-3 | `backend/app/main.py`, `rate_limiter.py` | Direct `starlette` imports (transitive dep) | Pin `starlette` in requirements.txt or use FastAPI re-exports | 2 min |
| 8 | DEP-4 | `backend/app/schemas.py`, `routers/analysis.py` | Direct `pydantic` import (transitive dep) | Pin `pydantic>=2.0` in requirements.txt | 1 min |

### MEDIUM / P2

| # | ID | File | Issue | Suggested Fix | Effort |
|---|-----|------|-------|--------------|--------|
| 9 | DEAD-2 | `services/discovery.py:235` | `recommendations_source` is always `"recent_discoveries"` (dead branch) | Inline the string literal at return dict | 1 min |
| 10 | DEAD-3 | `main.py:234-252` | `/api/rate-limit-status` endpoint unused by frontend | Add `require_auth` or remove if not used externally | 2 min |
| 11 | DEAD-5 | `services/profile_metrics.py:252-254` | `top_genre` and `avg_popularity` always None in daily stats | Implement or remove placeholder fields | 15 min |
| 12 | UI-8 | `pages/PlaylistComparePage.jsx:201,222` | `border-border` may be undefined Tailwind token | Replace with `border-surface-hover` | 1 min |
| 13 | UI-11 | `pages/FriendsPage.jsx:76-78,101-108` | Silent error swallowing on invite/remove friend | Add error toast feedback | 5 min |
| 14 | DEP-6 | `audio_feature_extractor.py` ↔ `audio_analyzer.py` | Latent circular import risk | Extract shared functions to `audio_cache.py` | 30 min |
| 15 | DEP-7 | `audio_feature_extractor.py` | Mixed-source audio features (librosa vs RapidAPI) lack `source` column | Add source tracking to AudioFeatures model | 20 min |

## Quick-Fix Commands

```bash
# Fix Spotify green color violations (UI-1, UI-4, UI-5, UI-6)
cd frontend/src
# SessionStats.jsx:118 — bg-spotify → bg-accent-hover
# TasteEvolutionPage.jsx:147 — text-spotify → text-accent
# TasteEvolutionPage.jsx:177 — bg-spotify → bg-accent
# TemporalPage.jsx:68,73 — text-spotify → text-accent

# Pin transitive deps (DEP-3, DEP-4)
echo "starlette>=0.41.0  # direct use in main.py, rate_limiter.py" >> backend/requirements.txt
echo "pydantic>=2.0  # direct use in schemas.py, analysis.py" >> backend/requirements.txt

# Fix border token (UI-8)
# PlaylistComparePage.jsx:201,222 — border-border → border-surface-hover
```

## Suggested Follow-Up Commands

| Condition | Suggested Command | Scope |
|-----------|------------------|-------|
| 5 Spotify green violations | `/refactor` | Color palette consistency |
| Broken images in Wrapped slides | `/ux-audit` | Wrapped component |

## Invalidated by /feature on 2026-03-21
Feature: bug fixes (first login 502, popularity null, discovery chart, cerchie redesign)

## Invalidated by /feature on 2026-03-21
Feature: sync on login + daily stats pipeline (1C)
Re-run /health for an updated report.
