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

## Health Scan — March 2026

### Key Findings
- `/health` found 16 issues: 6 dead code, 0 dependency, 10 UI convention violations
- All dependencies clean — no unused, no circular imports, no duplicates
- Main theme: empty-state messages violating the "hide rather than show" convention
- One copy-paste bug: duplicate genre cloud section in ArtistNetworkPage

### Detection Signals
- `{x.length === 0 && null}` is dead code — JSX expressions that evaluate to nothing should be removed entirely, not replaced with `null`
- When `/health --fix` replaces `<EmptyState />` with `return null`, the now-unused `EmptyState` function must also be removed
- Unused icon imports (e.g. `ChevronDown`) survive health scans — a follow-up `/refactor` catches these

## Playlist Compare Migration — March 2026

### Root Cause
- `PlaylistComparePage` depended entirely on deprecated Audio Features API → showed empty data
- `get_or_fetch_features` catches the 403 silently → `analyzed_count: 0` → frontend hides everything

### Fix Pattern
- Enrich compare endpoint with always-available data: popularity stats, genre distribution, top tracks
- Keep audio features as optional bonus (shown only when `analyzed_count > 0`)
- Fetch playlist name from Spotify API instead of relying on frontend-side mapping
- Reuse `get_artists` batch pattern (same as `_extract_genres` in audio_analyzer) for genre extraction

### Key Lesson
- When building features, always have a primary data path that uses non-deprecated APIs
- Audio features should be a secondary enrichment, never the only data source
- `get_or_fetch_features` still calls the deprecated API for cache misses — future improvement: skip API call entirely, only use DB cache

### Failure Mode: Unhandled exceptions cause 500
- **Signal**: `except SpotifyAuthError` as only handler in outer try block — `RateLimitError` and `SpotifyServerError` from `retry_with_backoff` bubble up unhandled → FastAPI returns generic 500
- **Prevention**: every router endpoint that calls Spotify API must catch `SpotifyAuthError`, `RateLimitError`, `SpotifyServerError`, AND generic `Exception` (with `logger.exception` for debugging)
- **Rule**: when adding `retry_with_backoff` calls, remember it re-raises `RateLimitError`/`SpotifyServerError` after max retries — these MUST be caught at the router level
- **Pattern**:
  ```python
  except SpotifyAuthError:
      raise HTTPException(401, "Sessione scaduta")
  except RateLimitError as e:
      raise HTTPException(429, ..., headers={"Retry-After": ...})
  except SpotifyServerError:
      raise HTTPException(502, "Spotify non disponibile")
  except Exception as exc:
      logger.exception("...: %s", exc)
      raise HTTPException(500, "Errore durante ...")
  ```

### Failure Mode: Spotify Feb 2026 dev mode migration
- **Signal**: `GET /playlists/{id}` returns 200 but response lacks `tracks` field entirely. `GET /playlists/{id}/tracks` returns 403.
- **Root cause**: Spotify Feb 2026 migration renamed `/playlists/{id}/tracks` → `/playlists/{id}/items`. The full playlist endpoint (`GET /playlists/{id}`) no longer includes tracks in dev mode.
- **Fix**: use `GET /playlists/{pid}/items` (new endpoint) for playlist tracks. Within each item object, the track data field is renamed from `"track"` to `"item"` — use `item.get("item") or item.get("track")` for backwards compat.
- **Batch endpoints removed**: `GET /artists?ids=...`, `GET /tracks?ids=...`, `GET /albums?ids=...` are all removed in dev mode. Use individual endpoints (`GET /artists/{id}`) with semaphore + asyncio.gather.
- **Pagination**: `/playlists/{id}/items` has `limit` max 50 (not 100). Always paginate with `offset` loop + `next` check. All 3 consumers (`playlists.py`, `playlist_analytics.py`, `historical_tops.py`) now paginate.
- **Cap**: individual artist fetches capped to ~20 globally per endpoint (reduced from 30 due to dev mode rate limits).
- **Affected files**: `playlists.py`, `playlist_analytics.py`, `historical_tops.py`, `audio_analyzer.py`
- **Rule**: always check Spotify migration guide before assuming endpoint availability. Use `/items` not `/tracks`.
- **Reference**: https://developer.spotify.com/documentation/web-api/tutorials/february-2026-migration-guide

### Failure Mode: retry_with_backoff dorme per ore su 429 con retry_after enorme
- **Signal**: log mostra `Rate limited, retry in 75582.0s` → il request si blocca per ore/giorni. La pagina resta vuota perché il backend non risponde mai.
- **Root cause**: `retry_with_backoff` usava `e.retry_after` senza cap. Spotify dev mode restituisce `retry_after=75582s` (~21 ore). Il codice eseguiva `asyncio.sleep(75582)` per ogni tentativo × `max_retries=3` = potenzialmente 63 ore di attesa.
- **Fix**: aggiunto parametro `max_retry_after=30.0` a `retry_with_backoff`. Se `retry_after > max_retry_after`, fallisce immediatamente (raise `RateLimitError`). Ridotto Semaphore da 5→2 e cap artisti da 30→15 per artist fetches.
- **Rule**: mai fare `asyncio.sleep(retry_after)` senza un cap massimo. Un retry_after > 60s significa "non riprovare adesso" — fallire subito è meglio che bloccare il server.
- **Corollary**: Semaphore controlla la concorrenza ma non il rate nel tempo. 5 richieste simultanee che partono nello stesso istante sono un burst — in dev mode, usare Semaphore(2) max.

### Failure Mode: Task marcato completato senza verifica live
- **Signal**: task marcato `[x]` nel todo.md dopo aver applicato fix al codice, ma senza mai verificare che i dati reali arrivino correttamente al frontend
- **Prevention**: un fix non è completo finché non è verificato con dati reali. Il ciclo è: codice → test/lint → verifica live con dati reali → solo allora marcare completato
- **Rule**: mai marcare un bug fix come completato basandosi solo su "il codice è corretto". Serve conferma dall'utente o dal log che i dati fluiscono end-to-end

### Failure Mode: Audio Features 403 confonde la diagnosi
- **Signal**: log mostra `403 Forbidden` su `GET /audio-features` → sembra il bug, ma è un red herring. L'API è deprecata e il 403 è gestito. Il vero problema è altrove (es. tracks non parsate da `/items`)
- **Prevention**: distinguere errori attesi (API deprecate) da errori reali. Se audio features 403 è già gestito con try/except, il problema è nel data path primario (popularity, genres, top tracks)
- **Rule**: quando il tracelog mostra un errore, verificare prima se è già gestito nel codice prima di investigare

### Failure Mode: API call budget non controllato — burst triggera rate limit
- **Signal**: compare endpoint con 4 playlist generava ~70 chiamate API (4 metadata + 4 items + 60 artist fetches). Ogni playlist creava il proprio Semaphore e i propri artist IDs — artisti condivisi tra playlist venivano fetchati N volte.
- **Root cause**: genre fetch per artista era per-playlist (non deduplicato). Con 4 playlist da 100 brani ciascuna, ~15 artisti × 4 = 60 chiamate solo per i generi.
- **Fix**: ristrutturato compare in 3 fasi: (1) fetch tracks per tutte le playlist, (2) deduplica artisti globalmente + fetch generi una volta sola (cap 20 artisti totali), (3) costruisci risultati usando cache generi. Chiamate ridotte da ~70 a ~30.
- **Rule**: prima di ogni `asyncio.gather` con N chiamate API, calcolare il worst-case budget. Se > 30 chiamate, ristrutturare con dedup e caching in-memory.
- **Pattern**: per dati condivisi tra iterazioni (generi artista, metadata playlist), raccogliere IDs unici prima, fetchare una volta, usare da cache.

### Failure Mode: chiamate Spotify senza retry_with_backoff
- **Signal**: `historical_tops.py` e `background_tasks.py` chiamavano `client.get_playlists()`, `client.get_recently_played()`, `client.get_top_artists()` direttamente senza `retry_with_backoff` — un 429 o 5xx non veniva ritentato.
- **Fix**: wrappato tutte le chiamate in `retry_with_backoff`.
- **Rule**: ogni chiamata a SpotifyClient deve passare per `retry_with_backoff` — il 429 handling di `SpotifyClient._request` alza `RateLimitError`, che `retry_with_backoff` gestisce con backoff.

## UX/UI Polish — Framer Motion Integration (March 2026)

### What Worked
- `StaggerContainer` + `StaggerItem` as reusable wrapper pair kept page modifications minimal — just wrap existing elements
- framer-motion `whileInView` with `viewport={{ once: true }}` is cleaner than IntersectionObserver for scroll-driven animations
- Extracting `sidebarContent` as shared JSX between mobile (animated) and desktop (static) `<aside>` avoided code duplication
- Skeleton loaders matching real component shapes (accent bar + title + value for KPICard) feel much more polished than generic spinners

### Gotchas
- When applying `AnimatePresence` to `AppLayout`, `mode="wait"` is required — otherwise exit and enter animations overlap causing layout shift
- The `StaggerItem` component relies on parent `StaggerContainer` variants — it won't animate standalone (by design, but could confuse)
- KPICard had both CSS `animate-slide-up` and now framer-motion `whileInView` — the CSS animation must be removed when adding motion, or they compete
- ESLint config issue pre-existing: project uses ESLint 9 but has old `.eslintrc` format — `npm run lint` fails. Unrelated to motion changes.

### Architecture Decisions
- Kept `LoadingSpinner` with `fullScreen` for App.jsx auth/Suspense fallback — skeleton loaders only replace in-page loading states
- Page transitions are subtle (8px slide + fade) rather than dramatic — analytics app should feel snappy, not theatrical
- Sidebar desktop stays static (CSS `hidden lg:flex`) — only mobile gets AnimatePresence. No performance cost on desktop.
- `StaggerContainer` stagger interval set to 40ms — fast enough to feel fluid, slow enough to see the cascade

## Deferred Items Implementation — March 2026

### Security: X-Forwarded-For bypass
- **Signal**: rate limiter manually parsing `X-Forwarded-For` header allows any client to spoof IPs and bypass rate limits
- **Fix**: let `ProxyHeadersMiddleware` (gated behind `BEHIND_PROXY=true`) rewrite `request.client.host` — rate limiter just reads `request.client.host`, never touches headers directly
- **Rule**: never manually parse proxy headers in application code — use middleware that validates the trust chain

### Security: Dict eviction must not run on every request
- **Signal**: sorted eviction running outside the periodic cleanup block = O(n log n) per request under load
- **Fix**: moved eviction inside the 5-minute cleanup block
- **Rule**: expensive maintenance operations (sorting, GC) should be amortized on a timer, not triggered per-request

### Spotify ID validation
- **Signal**: Spotify IDs are typically 22 chars but not guaranteed — some older/special IDs differ
- **Fix**: regex `{15,25}` instead of strict `{22}`
- **Rule**: when validating third-party IDs that come from the same API's responses, be lenient — false rejections are worse than accepting a slightly malformed ID

### Data Integrity Checklist
- [ ] All displayed data comes from real API calls (no mocks, no hardcoded values)
- [ ] Missing data defaults to 0/null/empty, never to a plausible fake value
- [ ] Fallback data sources are explicitly labeled in the UI
- [ ] Each `asyncio.gather` call has per-coroutine error handling
- [ ] SpotifyAuthError is re-raised before generic Exception in every router/service
- [ ] Every router catches RateLimitError and SpotifyServerError (not just SpotifyAuthError)
- [ ] Never use `/playlists/{id}/tracks` — use `/playlists/{id}/items` instead
- [ ] Never use batch `GET /artists?ids=` — use individual `GET /artists/{id}` with semaphore
- [ ] All Semaphore values ≤ 2 for Spotify API calls (dev mode burst protection)
- [ ] Every SpotifyClient call wrapped in `retry_with_backoff` (no direct `client.get_*` without retry)
- [ ] Compare/analytics endpoints dedup shared data (artist IDs) across iterations before fetching
- [ ] Global artist fetch cap ≤ 20 per endpoint invocation
- [ ] No API calls to deprecated endpoints (audio-features, recommendations) — use DB cache only
- [ ] cache-then-fetch patterns for deprecated APIs removed (not just wrapped in try/except)

## Wrapped Export — Stories Feature (March 2026)

### What Worked
- Aggregated backend endpoint (`GET /api/wrapped`) calling 5 services in parallel via `_safe_fetch` — single request, clean loading state
- `available_slides` computed server-side avoids per-field null checking on frontend
- Full-screen overlay with `fixed inset-0 z-[100]` cleanly bypasses AppLayout without needing a separate layout component
- Route outside `ProtectedRoute` but inside `AppRoutes` (which has `useAuth()`) — no need for `ProtectedRouteNoLayout`
- Stories engine separated from slide content — adding/removing slides only requires editing the registry array
- `onPointerDown` instead of `onClick` for mobile responsiveness (no 300ms tap delay)

### Architecture Decisions
- Backend does NOT create new services — only aggregates existing ones. Zero duplication.
- html2canvas captures only the summary card ref, not the full screen — keeps export clean and fast
- Web Share API with `canShare` check before attempting — graceful fallback to download
- `min-h-[100dvh]` for mobile viewport (accounts for browser chrome)
- Sidebar entry uses `special: true` flag for accent styling — doesn't interfere with existing nav logic

### Gotchas
- `html2canvas` needs explicit `backgroundColor: '#121212'` because CSS variables aren't resolved by the library
- Slide z-index must be higher than click zone z-index, otherwise slide content (buttons, links) is unclickable
- framer-motion `AnimatePresence mode="wait"` with `custom` prop requires both `variants` AND `custom` on the child `motion.div`

## Health Report Fix — March 2026

### Pattern: _safe_fetch must re-raise SpotifyAuthError
- 5 locations had `except Exception` in inner helpers catching SpotifyAuthError
- The correct `_safe_fetch` pattern is in `wrapped.py:22-30` — always copy from there
- Rule: any new `_safe_fetch` or gather-wrapper function MUST include `except SpotifyAuthError: raise` before `except Exception`

### Pattern: ProtectedRoute `withLayout` prop
- `/wrapped` route needed auth protection but no AppLayout (full-screen stories)
- Added `withLayout` prop to `ProtectedRoute` instead of duplicating auth logic inline
- Rule: never use inline `user ? <Page /> : <Navigate />` — always use ProtectedRoute for consistent auth expiry handling

### Pattern: usePlaylistCompare needs AbortController
- Custom hooks that make API calls should always support cancellation via AbortController
- Without it, unmounting during a request causes stale state updates
- Reference: `useSpotifyData.js` already had this pattern — `usePlaylistCompare` was missing it

### Pattern: Stale closure in useCallback with JSON.stringify
- When `params` is a new object each render but `stableParams = JSON.stringify(params)` is the dep, parse stableParams inside the callback instead of closing over `params`
- This avoids the latent risk of the closure holding a stale `params` ref

## Verification Round — March 2026

### SpotifyAuthError in get_or_fetch_features
- The health scan found `except Exception` swallowing `SpotifyAuthError` at `audio_analyzer.py:285` — a pre-existing bug
- This was inside a batch loop for audio features, not a top-level handler, so previous health scans missed it
- **Rule**: when adding `_safe_compute` or `_safe_fetch` wrappers that re-raise `SpotifyAuthError`, verify that the functions they wrap ALSO propagate auth errors correctly — the wrapper only helps if the inner code doesn't swallow the error first
- **Rule**: `except SpotifyAuthError: raise` must be checked at EVERY level of the call chain, not just the outermost handler

### useMemo for simple arithmetic is overhead
- `useMemo(() => Math.min(x / 30 * 100, 100), [x])` — the memo cost (allocation, dep comparison) exceeds the computation cost
- **Rule**: only use `useMemo` when the computation is expensive (>1ms) or when the result is passed as a prop to a memoized child

### useEffect deps should match semantic identity
- `useEffect` with `[nodes, edges, nodeIndex, dataKey]` where `dataKey` already captures nodes+edges identity is misleading
- The effect had an early return guarded by `dataKey`, making the extra deps redundant but confusing
- **Rule**: useEffect deps should contain the minimal set that represents when the effect should re-run semantically

### preventDefault on keyboard scroll handlers
- Space key triggers browser scroll by default on interactive elements
- When `onKeyDown` handles Space to trigger a custom action (like scrollIntoView), always call `e.preventDefault()` to suppress the browser default

## Health Report Backend Suggestions — March 2026

### S-2: Removed deprecated get_recommendations
- `SpotifyClient.get_recommendations` called `/recommendations` which always fails (deprecated Feb 2026)
- `discovery.py` had a try/except that caught the failure and fell back to `new_discoveries` every time — wasting an API call
- Fix: removed the method entirely, discovery.py now goes straight to `new_discoveries[:20]` fallback
- Rule: when an API is deprecated and the fallback is always used, remove the dead code path entirely

### S-4: Aligned rate_limiter default RPM
- `APIRateLimiter.__init__` had `requests_per_minute=60` but `main.py` always passed `120`
- The mismatch was harmless (explicit param overrides default) but misleading for anyone reading rate_limiter.py in isolation
- Rule: defaults should match the app's actual configuration to reduce cognitive load

### S-5: Parallelized compute_trends with asyncio.gather
- `compute_trends` ran 3 `compute_profile` calls sequentially — each hitting Spotify API
- Refactored to `asyncio.gather` with `_safe_compute` wrapper (re-raises SpotifyAuthError, returns None on other failures)
- Profiles that fail are excluded from results (graceful degradation)
- Rule: when calling the same async function N times with different params and no data dependency, always parallelize

## Deprecated API Cleanup — March 2026

### get_or_fetch_features converted to pure cache lookup
- **Root cause**: `get_or_fetch_features` had a cache-then-fetch pattern. Cache miss → `client.get_audio_features(batch)` → `/v1/audio-features` → 403 (deprecated since Feb 2026). Every miss wasted a call against the rate limit budget.
- **Impact**: 6+ wasted 403 calls per page load, cascading into 429 Too Many Requests on legitimate endpoints (`/v1/artists/{id}`).
- **Fix**: removed the `if missing:` fetch block entirely, removed `client: SpotifyClient` parameter. Function now does pure DB lookup + logs cache misses at DEBUG level. Removed dead `SpotifyClient.get_audio_features()` method. Updated 5 call sites.
- **Rule**: when a Spotify API is deprecated (returns 403 permanently), remove the API call entirely — do NOT leave it behind a try/except. A "handled" 403 still counts against rate limits and causes cascading failures.
- **Rule**: cache-then-fetch patterns for deprecated APIs must be converted to cache-only. The fetch path is dead code that burns rate limit budget.
- **Rule**: after every code change that adds new Spotify API calls, audit the full request budget per page load. If total calls > 30, restructure.
