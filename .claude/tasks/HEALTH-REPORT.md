# Project Health Report

Generated: 2026-04-01
Project: Spotify Listening Intelligence (progettoWrap)
Stack: FastAPI 0.115 + React 18 + Vite 6 + PostgreSQL 16 + Redis 7
Mode: scan-only

## Summary

| Metric | Count |
|--------|-------|
| Total findings | 21 |
| Auto-fixed | 0 |
| Manual action needed | 21 |
| Dead code found | 2 items |
| Dependencies to review | 4 packages |
| UI issues found | 18 |

## Completed Task Audit

These findings relate directly to tasks marked `[x]` in todo.md:

| Task | Status | Finding |
|------|--------|---------|
| Endpoint recent-summary | **Incomplete** | DEAD-2: endpoint implemented but no frontend caller exists |
| first_play_date disclaimer | **Bug** | UI-14: banner shows "0 ascolti" during loading |
| Fix onboarding modal | **Partial** | UI-6: only checks localStorage, ignores server-side `onboarding_completed` |
| Fix timezone | OK | No issues found |
| Startup sync | OK | No issues found |

## Manual Action Required

### CRITICAL / P0

| # | ID | File | Issue | Suggested Fix | Effort |
|---|-----|------|-------|--------------|--------|
| 1 | DEP-9 | `frontend/package.json` | `vite-plugin-pwa` in devDependencies but used at build time — Docker prod build may fail | Move to dependencies | 1 min |

### HIGH / P1

| # | ID | File | Issue | Suggested Fix | Effort |
|---|-----|------|-------|--------------|--------|
| 2 | DEAD-1 | `backend/app/routers/analytics.py:39` | `"historical": []` hardcoded empty field in every trends response, never consumed | Remove from response dict | 1 min |
| 3 | DEAD-2 | `backend/app/routers/library.py:104-184` | `GET /api/v1/library/recent-summary` — no frontend caller | Wire to frontend or remove | 30 min |
| 4 | UI-1 | `frontend/src/components/profile/GenreDNA.jsx:14-19` | Radar chart uses fabricated rank-decay values (100→50) instead of real frequencies | Wire real genre_distribution from API | 15 min |
| 5 | UI-2 | `frontend/src/components/charts/StreakDisplay.jsx:108-111` | Renders full visual when streak=0 instead of hiding (violates convention) | Add early return when streak===0 && uniqueDays===0 | 5 min |
| 6 | UI-3 | `frontend/src/components/wrapped/slides/SlideOutro.jsx:76` | Year hardcoded to 2026 | Use `new Date().getFullYear()` | 2 min |
| 7 | UI-4 | `frontend/src/pages/AdminPage.jsx:51-57` | handleSuspend swallows non-401/429 errors silently | Add error state + user feedback | 5 min |
| 8 | UI-5 | `frontend/src/pages/AdminPage.jsx:181-188` | handleCreate (invite) swallows errors silently | Add error state + user feedback | 5 min |
| 9 | DEP-1 | `backend/requirements.txt` | `psycopg2-binary` only used by one-time migration script | Move to requirements-dev.txt | 2 min |
| 10 | DEP-5 | `backend/requirements.txt` | librosa (~300MB) imported unconditionally even if RapidAPI is primary path | Lazy-import librosa | 15 min |

### MEDIUM / P2

| # | ID | File | Issue | Suggested Fix | Effort |
|---|-----|------|-------|--------------|--------|
| 11 | UI-6 | `frontend/src/pages/DashboardPage.jsx:21-22` | Onboarding modal ignores server-side `onboarding_completed` | Combine localStorage + server flag check | 5 min |
| 12 | UI-7 | `frontend/src/components/charts/TrendTimeline.jsx:101-116` | Renders flat lines for missing feature keys | Filter to keys with data | 10 min |
| 13 | UI-14 | `frontend/src/pages/TemporalPage.jsx:67-88` | Disclaimer banner shows "0 ascolti" during loading | Guard with `!loading` | 2 min |
| 14 | UI-8 | `frontend/src/pages/PlaylistComparePage.jsx:58-60` | eslint-disable on useEffect deps — potential stale closure | Verify reset stability | 10 min |
| 15 | UI-9 | `frontend/src/components/charts/ArtistNetwork.jsx:205,307` | eslint-disable on simulation useEffect deps | Review dep correctness | 10 min |
| 16 | UI-10 | `frontend/src/pages/FriendsPage.jsx:72-79` | handleInvite error swallowed (console only) | Add toast on error | 5 min |
| 17 | UI-11 | `frontend/src/pages/FriendsPage.jsx:98-109` | handleRemove error swallowed (console only) | Add toast on error | 5 min |
| 18 | DEP-8 | `frontend/package.json` | html2canvas (200kB) always in main bundle | Convert to dynamic import | 5 min |

### LOW / P3

| # | ID | File | Issue | Suggested Fix | Effort |
|---|-----|------|-------|--------------|--------|
| 19 | UI-15 | `frontend/src/components/wrapped/slides/SlideTopTracks.jsx:43-46` | Hidden fallback div always in DOM | Use conditional rendering | 5 min |
| 20 | UI-16 | `frontend/src/components/social/TasteComparison.jsx:35` | Dead `type` prop passed but never consumed | Implement icon selection or remove | 5 min |
| 21 | UI-18 | `frontend/src/pages/AdminPage.jsx:480-489` | JobsTab status badge logic too loose | Tighten condition | 5 min |

## Quick-Fix Commands

```bash
# Move psycopg2-binary to dev requirements
# Edit backend/requirements.txt — remove psycopg2-binary line
# Edit backend/requirements-dev.txt — add psycopg2-binary==2.9.10

# Move vite-plugin-pwa to dependencies
cd frontend && npm install vite-plugin-pwa --save

# Remove dead historical field
# In backend/app/routers/analytics.py:39
# Change: return sanitize_nans({"current": trends, "historical": []})
# To:     return sanitize_nans({"current": trends})
```

## Suggested Follow-Up Commands

| Condition | Suggested Command | Scope |
|-----------|------------------|-------|
| UI-4,UI-5,UI-10,UI-11 silent errors | `/refactor` | AdminPage, FriendsPage error handling |
| UI-1 fake data in GenreDNA | `/refactor` | GenreDNA real data wiring |
| DEAD-2 uncalled endpoint | Decision needed | Wire to frontend or remove |

### Refactor Commands

```
/refactor fix completed task integration — UI-14 (TemporalPage banner during loading), UI-6 (onboarding server-side check), UI-2 (StreakDisplay zero guard)
```

```
/refactor consolidate error handling — UI-4,UI-5 (AdminPage silent errors) + UI-10,UI-11 (FriendsPage silent errors): add user-facing error feedback on all catch blocks
```
