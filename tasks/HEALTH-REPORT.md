# Project Health Report

Generated: 2026-03-14 (post-refactor scan)
Project: Spotify Listening Intelligence
Stack: FastAPI (Python 3.12) + React 18 + Vite + Tailwind + SQLite
Mode: scan-only

## Summary

| Metric | Count |
|--------|-------|
| Total findings | 9 |
| Auto-fixed | 0 |
| Manual action needed | 9 |
| Dead code | 1 file (ReceiptCard.jsx, ~45 lines) |
| Dependencies cleaned | 0 |
| UI issues found | 8 |
| Bug fix | not requested |

## Refactor Verification (all PASS)

| ID | Check | Status |
|----|-------|--------|
| API-1 | `get_me()` cached in `_cache_5m` | **PASS** |
| API-2 | `Semaphore(2)` in `profile_metrics.py` | **PASS** |
| API-5 | Early `break` on `RateLimitError` in `sync_recent_plays` | **PASS** |
| UI-1 | `toBlob` null guard in ShareCardRenderer | **PASS** |
| UI-2/3 | GenreDNA uses `GRID_COLOR` + CSS vars | **PASS** |

## API Call Budget — GET /api/profile

| Call | Endpoint | Cache | TTL |
|------|----------|-------|-----|
| `get_top_artists(short_term)` | `/me/top/artists` | `_cache_5m` | 5 min |
| `get_top_artists(long_term)` | `/me/top/artists` | `_cache_5m` | 5 min |
| `get_top_tracks(long_term)` | `/me/top/tracks` | `_cache_5m` | 5 min |
| `get_me()` | `/me` | `_cache_5m` | 5 min |
| DB queries (loyalty, consistency, stats) | — | — | — |

**Worst-case: 4 calls** | With cache: 0 calls | Budget: **well under 30**

## Import Verification (all PASS)

All imports in modified files verified — zero broken or unused imports:
- `spotify_client.py` — all OK
- `profile_metrics.py` — all OK
- `background_tasks.py` — `RateLimitError` import verified
- `profile.py` router — all OK
- `GenreDNA.jsx` — `GRID_COLOR` export verified in chartTheme.js
- `ShareCardRenderer.jsx` — all OK

## Manual Action Required

### HIGH / P1

| # | ID | File | Issue | Suggested Fix | Effort |
|---|-----|------|-------|--------------|--------|
| 1 | UI-5 | `share/ShareCardRenderer.jsx` | Modal non chiudibile con Escape (WCAG 2.1 SC 2.1.1) | Aggiungere `useEffect` con `keydown` listener per Escape | 5 min |

### MEDIUM / P2

| # | ID | File | Issue | Suggested Fix | Effort |
|---|-----|------|-------|--------------|--------|
| 2 | DEAD-2 | `share/ReceiptCard.jsx` | Componente orfano, 0 importers | Integrare in una pagina o eliminare | 5 min |
| 3 | UI-1/2 | `profile/ObscurityGauge.jsx` | Colori hardcoded (#10b981, #6366f1, #a855f7, #282828) | Importare `GRID_COLOR` da chartTheme + usare CSS vars | 10 min |
| 4 | UI-3/4 | `profile/DecadeChart.jsx` | Colori hardcoded (#b3b3b3, rgba accent) | Usare `var(--text-secondary)` e `var(--accent)` | 10 min |
| 5 | UI-6 | `share/ShareCardRenderer.jsx` | Modal senza `role="dialog"` e `aria-modal="true"` | Aggiungere attributi ARIA al motion.div esterno | 5 min |

### LOW / P3

| # | ID | File | Issue | Suggested Fix | Effort |
|---|-----|------|-------|--------------|--------|
| 6 | UI-7/8 | `share/ShareCardRenderer.jsx` | Icone Download/Share2 senza `aria-hidden="true"` | Aggiungere `aria-hidden="true"` alle icone | 2 min |
| 7 | UI-9/10 | `profile/DecadeChart.jsx`, `profile/GenreDNA.jsx` | Chart container senza `role="img"` e `aria-label` | Aggiungere ruoli ARIA ai wrapper div | 5 min |
| 8 | UI-11 | `profile/ObscurityGauge.jsx` | Gauge a 0 con score null (mostra "Molto mainstream") | Aggiungere `if (score == null) return null` | 2 min |
| 9 | UI-12 | `pages/ProfilePage.jsx` | Icona Share2 nel bottone senza `aria-hidden` | Aggiungere `aria-hidden="true"` | 1 min |

## Quick-Fix Commands

```bash
# Delete orphan file (DEAD-2)
rm frontend/src/components/share/ReceiptCard.jsx
```

## Files Safe to Delete

- `frontend/src/components/share/ReceiptCard.jsx` — 0 importers, no side effects, no dynamic imports

## Suggested Follow-Up Commands

| Condition | Suggested Command | Scope |
|-----------|------------------|-------|
| 8 UI findings in profile/share | `/refactor` | profile + share components |
| Hardcoded colors pattern | `/ux-audit` | All profile components |

### Refactor Commands

```
/refactor Unify hardcoded colors in ObscurityGauge.jsx and DecadeChart.jsx — import GRID_COLOR from chartTheme, replace hex values with CSS variables var(--accent), var(--text-secondary). Add Escape key handler + ARIA attributes to ShareCardRenderer.jsx. Add null guard to ObscurityGauge (UI-1/2, UI-3/4, UI-5, UI-6, UI-7/8, UI-11)
```
