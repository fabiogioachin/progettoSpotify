# Lessons Learned

## Active
Lessons that affect future tasks. Target: under 15 entries.

### 2026-03-18 — [codebase] NaN from numpy/sklearn crashes JSON serialization
**Context**: `GET /api/profile` returned 500 — `ValueError: Out of range float values are not JSON compliant: nan`
**What happened**: PCA, StandardScaler, NetworkX PageRank/betweenness, and cosine similarity can produce NaN/inf when input data has zero variance or edge cases. Python's `json.dumps` rejects non-finite floats.
**Root cause**: No defense-in-depth — individual fixes (e.g. nan_to_num in PCA) missed other NaN sources in the same response pipeline.
**Action**: Always wrap router returns with `sanitize_nans()` from `app.utils.json_utils` when the response includes float data from numpy/sklearn/NetworkX. Applied to profile, analytics, artist_network, wrapped.

### 2026-03-14 — [codebase] Spotify dev mode keeps removing endpoints
**Context**: `/artists/{id}/related-artists` started returning 403
**What happened**: Fourth+ deprecated endpoint. artist_network.py and discovery.py wasted calls on always-failing requests.
**Root cause**: Spotify dev mode progressively removes endpoints without advance warning.
**Action**: When any endpoint returns 403, treat as permanently removed — delete entirely, never wrap in try/except.

### 2026-03-14 — [codebase] Don't re-fetch data the frontend already has
**Context**: `POST /api/analyze-tracks` received only track_ids, re-fetched 50 tracks → instant 429.
**Action**: Pass full objects in request body when the frontend already has them.

### 2026-03-10 — [workflow] Task marked complete without live verification
**Context**: Bug fix marked `[x]` after code change, without verifying data flows end-to-end.
**Action**: Bug fix cycle: code → lint/test → live verification with real data → only then mark complete.

### 2026-03-06 — [codebase] dict.get() failures are silent in Python
**Context**: prompt_builder accessed wrong keys → silent empty output.
**Action**: Always verify key names between service return values and consumer code.

### 2026-03-14 — [workflow] git status -u non eseguito durante verifica
**Context**: `pip install networkx>=3.2` senza quoting ha creato file `backend/=3.2` e `backend/=1.4` (shell redirect). Non intercettati fino al commit finale.
**Root cause**: Il workflow di verifica (lint/test/build) non include `git status -u` per individuare file spazzatura.
**Action**: Dopo ogni wave di agenti, eseguire `git status -u` per individuare file non tracked inattesi. Verificare che i comandi pip usino quoting (`"pkg>=version"`).

## Archive
Resolved or one-off entries. Not read by agents.

### 2026-03 — [codebase] html2canvas doesn't resolve CSS variables
Pass explicit `backgroundColor: '#121212'` to html2canvas options. Fixed.

### 2026-03 — [codebase] framer-motion AnimatePresence requires mode="wait"
Always use `mode="wait"` for sequential page transitions. Fixed.

### 2026-03 — [codebase] Spotify IDs aren't always 22 characters
Use regex `{15,25}` for Spotify ID validation. Fixed.

### 2026-03 — [codebase] Expected 403s confuse debugging
Deprecated API 403s are expected — check if handled before investigating. Resolved.

### 2026-03 — [codebase] Deprecated API calls removed
get_or_fetch_features → pure cache lookup, get_recommendations removed, get_related_artists removed. All resolved.

### 2026-03 — [codebase] Various fixes
globals.css path, circular import, datetime.utcnow(), CI branch, snapshot dedup, rate limiter memory leak, X-Forwarded-For, TrendTimeline gradients, MoodScatter quadrants, PlaylistComparePage stale comparison. All resolved.

### 2026-03-14 — [codebase] Artist network data quality issues — RESOLVED
NetworkX + fuzzy genre matching implemented. BFS replaced with Louvain communities, PageRank + betweenness centrality added. Tooltips fixed. Resolved by scikit-learn + NetworkX integration feature.
