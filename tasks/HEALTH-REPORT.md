# Project Health Report

Generated: 2026-03-18 (post bug-fix batch)
Project: Spotify Listening Intelligence
Stack: FastAPI (Python 3.12) + React 18 + Vite + Tailwind + SQLite + NetworkX + scikit-learn
Mode: scan-only

## Summary

| Metric | Count |
|--------|-------|
| Total findings | 19 |
| Auto-fixed | 0 (--fix not passed) |
| Manual action needed | 19 |
| Dead code found | 2 files, ~30 lines |
| Dependencies to clean | 1 package |
| UI issues found | 12 |

## Manual Action Required

### CRITICAL / P0

| # | ID | File | Issue | Suggested Fix | Effort |
|---|-----|------|-------|--------------|--------|
| 1 | DEAD-1 | `frontend/src/components/share/ReceiptCard.jsx` | Orphan component — exported but never imported anywhere | Delete file | 1 min |
| 2 | DEAD-2 | `backend/app/constants.py:13-19` | `TIME_RANGES` and `TIME_RANGE_LABELS` exported but never imported | Remove lines 13–19 | 1 min |

### HIGH / P1

| # | ID | File | Issue | Suggested Fix | Effort |
|---|-----|------|-------|--------------|--------|
| 3 | UI-1 | `frontend/src/pages/TemporalPage.jsx:93` | StreakDisplay `activeDays` prop never passed — 7-day calendar always empty | Derive active days from streak data and pass as prop | 15 min |
| 4 | UI-2 | `frontend/src/components/wrapped/slides/SlideArtistEvolution.jsx:17` | Artist images broken — reads `image_url` but backend returns `image` | Change to `artist.image \|\| artist.image_url \|\| artist.images?.[0]?.url` | 2 min |
| 5 | UI-3 | `frontend/src/components/wrapped/slides/SlideArtistNetwork.jsx:9` | Cluster pills never render — `.map()` on object instead of array | Use `Object.values(network.cluster_names)` | 2 min |
| 6 | UI-4 | `frontend/src/components/wrapped/slides/SlideTopTracks.jsx:31` | All track images broken — reads `album.images` but backend returns `album_image` | Use `track.album_image \|\| track.album?.images?.[0]?.url` | 2 min |
| 7 | DEAD-3 | `backend/app/routers/library.py:93-187` | `GET /api/library/recent` and `GET /api/library/saved` — no frontend consumer | Keep if planned for future use, or remove | 5 min |
| 8 | DEAD-4 | `backend/app/models/track.py:21-24` | `loudness`, `key`, `mode`, `time_signature` columns never read/written by app code | Remove columns + migration (legacy from deprecated API) | 10 min |
| 9 | DEP-1 | `backend/requirements-dev.txt` | `soundfile==0.12.1` — already transitive dep of librosa, redundant pin | Remove from requirements-dev.txt | 1 min |
| 10 | DEP-2 | `.env.example` | `RAPIDAPI_KEY` not documented — devs won't know it exists | Add commented entry to .env.example | 1 min |

### MEDIUM / P2

| # | ID | File | Issue | Suggested Fix | Effort |
|---|-----|------|-------|--------------|--------|
| 11 | UI-5 | `frontend/src/pages/TasteEvolutionPage.jsx:177` | Selected year button invisible — `bg-spotify` class undefined | Replace with `bg-accent` | 1 min |
| 12 | UI-6 | `frontend/src/components/charts/SessionStats.jsx:119` | Weekend bar invisible — `bg-spotify` class undefined | Replace with `bg-emerald-400` or `bg-accent` | 1 min |
| 13 | UI-7 | `frontend/src/pages/TasteEvolutionPage.jsx:147` | Calendar icon colorless — `text-spotify` class undefined | Replace with `text-accent` | 1 min |
| 14 | UI-8 | `frontend/src/components/wrapped/slides/SlidePeakHours.jsx:10-11` | Weekend % reads non-existent `weekend_pct` — bars overflow | Derive from `100 - weekday_pct` | 2 min |
| 15 | UI-9 | `frontend/src/components/profile/GenreDNA.jsx:16-19` | Radar chart uses synthetic values (100 - i*12) instead of real genre frequency | Wire actual genre count data from backend | 15 min |
| 16 | UI-10 | `frontend/src/components/wrapped/slides/SlideListeningHabits.jsx:17` | All stats show "0" with sparse history — looks broken | Return null when all values are zero | 2 min |
| 17 | DEAD-6 | `backend/app/services/taste_map.py:48` | `audio_features` hardcoded to `None` — audio branch unreachable | Known gap (in todo.md) — implement or document | 30 min |
| 18 | DEP-3 | `backend/requirements.txt:11` | `numpy<2.0` upper cap may be over-restrictive now | Relax to `numpy>=1.24` after compatibility check | 5 min |

### LOW / P3

| # | ID | File | Issue | Suggested Fix | Effort |
|---|-----|------|-------|--------------|--------|
| 19 | UI-11 | `frontend/src/components/wrapped/slides/SlidePeakHours.jsx:75` | Empty slide body when no peak-hour data | Return null to skip slide | 1 min |
| 20 | UI-12 | `frontend/src/components/wrapped/slides/SlideOutro.jsx:25-37` | Download fails silently on cross-origin images (missing `useCORS: true`) | Add useCORS + try/catch | 5 min |

## Quick-Fix Commands

```bash
# Remove orphan file
rm frontend/src/components/share/ReceiptCard.jsx

# Remove redundant dev dependency
cd backend && pip uninstall soundfile  # reinstalled by librosa anyway

# Replace all bg-spotify / text-spotify with accent (UI-5, UI-6, UI-7)
# In TasteEvolutionPage.jsx: bg-spotify → bg-accent, text-spotify → text-accent
# In SessionStats.jsx: bg-spotify → bg-emerald-400
```

## Files Safe to Delete

- `frontend/src/components/share/ReceiptCard.jsx` — 0 importers, no side effects

## Suggested Follow-Up Commands

| Condition | Suggested Command | Scope |
|-----------|------------------|-------|
| 4 HIGH UI issues in Wrapped slides | `/ux-audit` | Wrapped stories flow |
| UI-9 GenreDNA fake data | `/refactor` | ProfilePage genre wiring |
| DEAD-3, DEAD-4 backend cleanup | `/refactor` | library router + AudioFeatures model |

### Refactor Commands

```
/refactor fix Wrapped slide field mismatches — align image/album field names in SlideArtistEvolution, SlideArtistNetwork, SlideTopTracks, SlidePeakHours with backend response shapes (UI-2, UI-3, UI-4, UI-8)
```

```
/refactor replace undefined bg-spotify/text-spotify classes with bg-accent/text-accent across TasteEvolutionPage and SessionStats (UI-5, UI-6, UI-7)
```

```
/refactor wire real genre frequency data into GenreDNA radar chart — replace synthetic 100-i*12 values with actual percentages from profile endpoint (UI-9)
```

## Invalidated by /feature on 2026-03-18
Feature: API efficiency + bug fixes — trends budget reduction, taste_map wiring, dead endpoint removal, StrictMode removal, SWR cache.

## Invalidated by /feature on 2026-03-19
Feature: Bug fix sprint — popularity enrichment, playlist track count fallback, ThrottleBanner rolling countdown.
Re-run /health for an updated report.
