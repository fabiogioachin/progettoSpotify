# Lessons Learned

## Active
Lessons that affect future tasks. Target: under 15 entries.

### 2026-03-26 — [codebase] Docker backend.Dockerfile must include scripts/
**Context**: `python -m scripts.backfill_artist_genres` inside container failed with `ModuleNotFoundError`
**What happened**: `docker/backend.Dockerfile` only copied `app/` and `alembic/`, not `scripts/`
**Root cause**: When `scripts/` directory was created, the Dockerfile wasn't updated to include it
**Action**: When adding new top-level directories to backend/ that need to run inside Docker, always update `docker/backend.Dockerfile` COPY statements

### 2026-03-26 — [codebase] Backfill scripts must respect API budget with delays
**Context**: `backfill_artist_genres` with P2_BATCH priority exhausted budget after 3 artists (3 call/window)
**What happened**: Script used `gather_in_chunks` with no delay between chunks — all 50 artists attempted in <1s, 47 rate-limited
**Root cause**: P2_BATCH allows only 3 calls/30s. Script assumed `gather_in_chunks` would handle throttling, but budget exhaustion happens before the throttle layer
**Action**: Backfill scripts must: (1) use P1_LOGIN priority minimum, (2) add explicit `asyncio.sleep(6)` between calls, (3) on rate limit, pause 35s then retry once

### 2026-03-21 — [tool] Local PostgreSQL intercepts Docker-mapped ports
**Context**: Docker Compose mapped postgres to host port 5432, then 5433 — both intercepted by local PG installation.
**What happened**: `asyncpg.connect()` hit the local PostgreSQL (which doesn't have the `spotify` user), not the Docker container.
**Root cause**: Local PostgreSQL listens on 5432 AND 5433. Docker port mapping creates a second listener on the same port, but the OS routes to the local PG first.
**Action**: Use port 5434 for Docker PostgreSQL on this machine. If port conflicts arise, always check `netstat -ano` before assuming Docker owns the port.

### 2026-03-19 — [codebase] Never add background API calls without budget verification
**Context**: Added `fire_bg_enrich` — a background task that called `GET /tracks/{id}` ×15 after a 35s delay to populate popularity cache.
**What happened**: The 35s delay wasn't enough. User navigation filled the budget again. The background task triggered a 429 with `retry_after=40445s` (11 hours of cooldown).
**Root cause**: Added API calls without counting the real budget impact. A rolling 30s window means a fixed delay doesn't guarantee availability — any user action during the delay refills the window.
**Action**: Never add ANY Spotify API call (even background/deferred) without explicit budget accounting in the `spotify-api-budget` skill. If an endpoint's data isn't available in dev mode, accept it and hide the feature — don't try to work around it with extra API calls.

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

### 2026-03-21 — [codebase] TrackPopularity had no writer — dead table for weeks
**Context**: `popularity_cache.py` comment said "populated by sync_recent_plays" but no write path existed.
**What happened**: Popularity null everywhere. Discovery chart disappeared (all tracks in 0-20 bucket).
**Root cause**: Writer was never implemented. Comment was aspirational, not factual.
**Action**: When creating a DB table + read function, implement the write path in the same PR. Verify the table has rows after the job runs.

### 2026-03-21 — [codebase] Listening data lost when backend is down — sync only on timer
**Context**: User reported missing listening days (Sun/Mon/Tue). `sync_recent_plays` only ran on 60-min APScheduler timer.
**What happened**: Backend was not running for days. Spotify's recently-played buffer (50 items max) rolled over. Older plays permanently lost.
**Root cause**: APScheduler is in-memory only — no persistence, no catch-up for missed fires. No sync triggered on user login.
**Action**: Always sync recent plays on login (`/auth/me`), not just on the timer. The login sync is the safety net — the timer is optimization. Applied: `_try_sync_and_snapshot` now runs `_sync_user_recent_plays` before the daily snapshot.

### 2026-03-21 — [codebase] Falsy-zero bug: `not t.get("popularity")` treats 0 as missing
**Context**: `popularity_cache.py` line 31 used truthiness check on a numeric field.
**Root cause**: Python `not 0` is `True`.
**Action**: For numeric fields that can be 0, always use `is None` check, never truthiness.

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
