# Project Health Report

Generated: 2026-03-14 (post scikit-learn + NetworkX integration)
Project: Spotify Listening Intelligence
Stack: FastAPI (Python 3.12) + React 18 + Vite + Tailwind + SQLite + NetworkX + scikit-learn
Mode: scan-only

## Summary

| Metric | Count |
|--------|-------|
| Total findings | 10 |
| Auto-fixed | 0 |
| Manual action needed | 10 |
| Dead code | 1 file (ReceiptCard.jsx, ~33 lines) |
| Dependencies cleaned | 0 |
| UI issues found | 8 |
| Circular imports | 0 |
| Bug fix | not requested |

## Scan Results

### Dead Code

| # | ID | Severity | File | Issue | Evidence | Safe to Remove |
|---|-----|----------|------|-------|----------|----------------|
| 1 | DEAD-1 | P2 | `frontend/src/components/share/ReceiptCard.jsx` | Orphan component — 0 importers across all source files | grep "ReceiptCard" returns only self-reference | YES |

No other orphan files found. All backend services have at least 1 importer. All frontend pages are routed in App.jsx and linked in Sidebar.jsx (routes match 1:1).

### Dependencies

All dependencies are actively used:

**Backend** (14 packages — all verified):
- `aiosqlite`: no direct import, but used as SQLAlchemy async driver via `sqlite+aiosqlite://` in config.py
- `networkx`: imported in artist_network.py (NEW)
- `scikit-learn`: imported as `sklearn` in taste_clustering.py (NEW)
- All other packages: 1-26 direct imports each

**Frontend** (8 packages — all verified):
- All packages have 1-27 importers across source files
- No unused dependencies, no missing packages
- devDependencies (eslint, vite, tailwindcss, etc.) are config/tooling only — correct placement

**Circular imports**: None detected. Dependency graph is a clean DAG:
```
genre_utils ← taste_clustering ← { artist_network, discovery, taste_map }
spotify_client ← { artist_network, discovery, taste_map, ... }
```

### UI Issues (carried forward from pre-integration scan, still valid)

### HIGH / P1

| # | ID | File | Issue | Suggested Fix | Effort |
|---|-----|------|-------|--------------|--------|
| 1 | UI-5 | `share/ShareCardRenderer.jsx` | Modal non chiudibile con Escape (WCAG 2.1 SC 2.1.1) | Aggiungere `useEffect` con `keydown` listener per Escape | 5 min |

### MEDIUM / P2

| # | ID | File | Issue | Suggested Fix | Effort |
|---|-----|------|-------|--------------|--------|
| 2 | DEAD-1 | `share/ReceiptCard.jsx` | Componente orfano, 0 importers | Eliminare | 1 min |
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

### New Code Quality Notes (scikit-learn + NetworkX integration)

| # | ID | Severity | File | Issue | Note |
|---|-----|----------|------|-------|------|
| 10 | NOTE-1 | P3 | `taste_map.py:48` | `# TODO: fetch from AudioFeatures table if available` | Audio features enrichment not yet wired — works fine on genre+popularity mode |

## Integration Health

The scikit-learn + NetworkX integration is clean:
- **No circular imports** in the new service graph
- **Pure-compute invariant respected**: genre_utils.py and taste_clustering.py never import SpotifyClient
- **All new exports used**: every function in genre_utils, taste_clustering, taste_map has at least 1 consumer
- **No new deprecated API calls**: NetworkX/sklearn operate on local data only
- **All 113 backend tests pass** (89 new + 24 existing)
- **Frontend builds clean** (0 errors, 280 warnings — all pre-existing unused imports in unrelated files)

## Quick-Fix Commands

```bash
# Delete orphan file (DEAD-1)
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
