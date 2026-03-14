# Lessons Learned

## Active
Lessons that affect future tasks. Target: under 15 entries.

### 2026-03-14 — [codebase] analyze-tracks re-fetched 50 tracks from Spotify API
**Context**: `POST /api/analyze-tracks` received only track_ids, then fetched each track individually via `/tracks/{id}`
**What happened**: 50 individual Spotify API calls in a 30-second rolling window → instant 429 with retry_after=82881s (23 hours)
**Root cause**: Frontend already had full track objects (with preview_url) from `/api/library/top` but only sent IDs. Backend re-fetched redundantly.
**Action**: When the frontend already has data, pass it in the request body — never re-fetch from Spotify what's already available client-side. Updated spotify-api-budget skill.

### 2026-03-14 — [codebase] Spotify dev mode keeps removing endpoints
**Context**: `/artists/{id}/related-artists` started returning 403
**What happened**: Third deprecated endpoint (after audio-features and recommendations). artist_network.py and discovery.py were wasting API calls on always-failing requests.
**Root cause**: Spotify dev mode progressively removes endpoints without clear advance warning. Feb 2026 migration removed related-artists, artist-top-tracks, batch endpoints, and more.
**Action**: When any Spotify endpoint starts returning 403, treat it as permanently removed — delete the API call entirely, never wrap in try/except. Check the [migration guide](https://developer.spotify.com/documentation/web-api/tutorials/february-2026-migration-guide) periodically.

### 2026-03-10 — [workflow] Task marked complete without live verification
**Context**: Bug fix marked `[x]` after code change, without verifying data flows end-to-end
**What happened**: Fix was structurally correct but didn't actually produce data in the frontend
**Root cause**: Confusing "code looks right" with "feature works"
**Action**: Bug fix cycle is: code → lint/test → live verification with real data → only then mark complete

### 2026-03-10 — [codebase] Expected 403s confuse debugging
**Context**: Log showed `403 Forbidden` on `GET /audio-features` during unrelated bug investigation
**What happened**: Spent time investigating a handled error instead of the real issue (tracks not parsed from `/items`)
**Root cause**: Deprecated API 403s are expected but still logged at WARNING level, creating noise
**Action**: When tracelog shows an error, check if it's already handled in code before investigating

### 2026-03-08 — [codebase] html2canvas doesn't resolve CSS variables
**Context**: Wrapped export share card had black background instead of dark theme
**What happened**: `html2canvas` rendered CSS `var(--background)` as transparent/black
**Root cause**: html2canvas doesn't compute CSS custom properties
**Action**: Pass explicit `backgroundColor: '#121212'` to html2canvas options

### 2026-03-08 — [codebase] framer-motion AnimatePresence requires mode="wait"
**Context**: Page transitions overlapped — old page still visible while new page animates in
**What happened**: Exit and enter animations played simultaneously
**Root cause**: Default AnimatePresence mode allows overlap
**Action**: Always use `mode="wait"` with AnimatePresence for sequential page transitions

### 2026-03-06 — [codebase] dict.get() failures are silent in Python
**Context**: prompt_builder accessed wrong keys from service return values
**What happened**: Silent empty output — no error, just missing data
**Root cause**: Python dict.get() returns None on miss, never raises
**Action**: Always verify key names between service return values and consumer code

### 2026-03-05 — [codebase] Spotify IDs aren't always 22 characters
**Context**: ID validation regex used strict `{22}`, rejecting valid older IDs
**What happened**: Some tracks/artists failed validation
**Root cause**: Spotify's older/special IDs can be 15-25 chars
**Action**: Use regex `{15,25}` for Spotify ID validation

## Archive
Resolved or one-off entries. Not read by agents.

### 2026-03 — [codebase] globals.css path
Actual path is `frontend/src/styles/globals.css`, not `frontend/src/index.css`. Always Glob first.

### 2026-03 — [codebase] Circular import _get_or_fetch_features
Moved from router to `audio_analyzer.py`. Resolved.

### 2026-03 — [codebase] datetime.utcnow() deprecation
Replaced all with `datetime.now(timezone.utc)` across 6 files. Resolved.

### 2026-03 — [codebase] CI branch mismatch
Workflows triggered on `main`, actual branch is `master`. Fixed.

### 2026-03 — [codebase] Snapshot deduplication
`save_snapshot` created duplicates on every visit. Now upserts per user/period/day. Resolved.

### 2026-03 — [codebase] Rate limiter memory leak
Stale keys cleaned every 5 min, IP as key instead of full cookie. Resolved.

### 2026-03 — [codebase] X-Forwarded-For bypass
ProxyHeadersMiddleware handles it now. Never parse proxy headers in app code.

### 2026-03 — [codebase] get_or_fetch_features → pure cache lookup
Removed deprecated API fetch path. Function is now DB-only. Resolved.

### 2026-03 — [codebase] get_recommendations removed
Dead code — always failed and fell back. Removed entirely. Resolved.

### 2026-03 — [codebase] get_related_artists removed
403 in dev mode. discovery.py uses recent_discoveries, artist_network.py uses genre-based edges. Resolved.

### 2026-03 — [codebase] TrendTimeline gradient definitions
Only 3/7 areas had gradients, rest transparent. Fixed by adding all gradient defs.

### 2026-03 — [codebase] MoodScatter quadrant labels inverted
Grid positions didn't match axis positions. Fixed.

### 2026-03 — [codebase] PlaylistComparePage stale comparison
Reset comparison on selection change. Fixed.
