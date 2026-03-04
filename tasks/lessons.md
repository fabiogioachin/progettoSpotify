# Lessons Learned

## Batch 1 — 4 Feature + UI/UX Spotify-Style

### What Worked
- Parallel subagents for independent backend services saved significant time
- Pure SVG force-directed graph avoided heavy d3 dependency
- BFS cluster detection was simple and effective for artist network
- asyncio.Semaphore prevented Spotify rate limiting issues
- AppLayout pattern cleanly separated nav from page content

### Gotchas
- `frontend/src/index.css` didn't exist — actual path was `frontend/src/styles/globals.css`. Always use Glob to find CSS files
- Audio Features API is deprecated — never rely on it for new features
- Spotify API only has 3 fixed time ranges — can't be extended programmatically
- Recently played hard limit is 50 items — clearly communicate this in UI

### Architecture Decisions
- Kept accent color as indigo (#6366f1) rather than Spotify green to differentiate the app
- Used CSS grid (not SVG) for heatmap — simpler, more responsive
- Used Recharts only for standard charts, custom SVG for complex visualizations
- Italian localization throughout — all UI labels, error messages, export prompts

## Quality Sweep — March 2026

### Bugs Fixed
- **prompt_builder key mismatches**: `build_artist_network` returns flat `clusters` list and `bridges` (not `bridge_artists`), `compute_temporal_patterns` returns nested `peak_hours` objects and `streak.max_streak`. prompt_builder was accessing wrong keys → silent empty output in Claude export
- **Circular import**: `_get_or_fetch_features` lived in router but was imported by 2 services → moved to `audio_analyzer.py` as `get_or_fetch_features`
- **TrendTimeline `.slice(0, 3)`**: Only 3 of 7 audio feature areas had gradient definitions → 4 areas rendered transparent
- **MoodScatter quadrant labels inverted**: Label grid positions didn't match chart axis positions
- **Snapshot deduplication**: `save_snapshot` created duplicate rows on every dashboard visit → now upserts per user/period/day
- **datetime.utcnow() deprecation**: Replaced all occurrences across 6 files with `datetime.now(timezone.utc)`
- **CI branch mismatch**: Workflows triggered on `main` but actual branch is `master`

### Security Fixes
- Added startup warning when default `session_secret` or `encryption_salt` are in use
- Fixed rate limiter memory leak — stale keys now cleaned every 5 minutes, use IP instead of full session cookie as key

### UX/UI Improvements
- Improved `text-muted` contrast from `#6a6a6a` to `#8a8a8a` (WCAG AA compliant)
- Added `focus-visible` outline styles for keyboard accessibility
- Standardized page padding (`py-8`) and subtitle color (`text-text-secondary`)
- Removed redundant `min-h-screen bg-background` wrappers from 3 pages
- Added page transition animation via `animate-fade-in` keyed on pathname
- Fixed `useAnimatedValue` to animate from previous value (not always from 0)
- Hidden TrackCard MiniBar when features are undefined (prevents misleading 0% bars)
- Fixed PlaylistComparePage to reset stale comparison on selection change
- Translated remaining English strings (Tracks→Brani, Bridge Artists→Artisti Ponte, Top Artists→Artisti Top)
- Used `GRID_COLOR` constant from chartTheme instead of hardcoded values

### Detection Signals
- Always verify key names between service return values and consumer code — Python won't error on dict.get() misses
- `datetime.utcnow` deprecation warnings are silent in many setups — grep for it proactively
- `.slice()` on gradient definitions is a subtle bug — rendered areas reference missing gradients silently
- Rate limiter dicts using raw cookie values as keys will grow unbounded

## Deprecated API Resilience — March 2026

### Failure Mode: Hardcoded fallback values look like real data
- **Signal**: any `default=180000` or similar magic number in model/service code
- **Prevention**: default to `0` or `None` for missing data, never a plausible value (e.g. "3 min" duration is believable but wrong)
- **Rule**: grep for hardcoded numeric defaults in models and services — if the number looks like a real measurement, it's a bug

### Failure Mode: SpotifyAuthError swallowed by generic except
- **Signal**: `except Exception` in router/service catches SpotifyAuthError too → user gets stale data instead of redirect to login
- **Prevention**: always add `except SpotifyAuthError: raise` before `except Exception` in any Spotify API calling code
- **Rule**: every new endpoint touching SpotifyClient must have explicit SpotifyAuthError re-raise

### Failure Mode: Deprecated API fails silently, shows nothing
- **Signal**: page shows empty cards/charts with no explanation
- **Prevention**: always return a `has_*` or `*_source` flag from backend so frontend can show alternatives
- **Rule**: when adding a data source, add a fallback path AND a transparency flag (never silent empty)

### Failure Mode: Taste evolution crashes when 1 of 6 API calls fails
- **Signal**: `asyncio.gather` with 6 calls — one failure kills entire page
- **Prevention**: wrap each coroutine in `_safe_fetch()` that returns `{"items": []}` on failure
- **Rule**: for `asyncio.gather` with 3+ calls, always use individual error handling per call

### Failure Mode: save_snapshot DB error kills profile endpoint
- **Signal**: snapshot write fails → entire `/api/analytics/features` returns 500
- **Prevention**: wrap non-critical writes in inner try/except with logger.warning
- **Rule**: distinguish critical vs non-critical DB operations — non-critical must never block the response

### Data Integrity Checklist
- [ ] All displayed data comes from real API calls (no mocks, no hardcoded values)
- [ ] Missing data defaults to 0/null/empty, never to a plausible fake value
- [ ] Fallback data sources are explicitly labeled in the UI
- [ ] Each `asyncio.gather` call has per-coroutine error handling
- [ ] SpotifyAuthError is re-raised before generic Exception in every router/service
