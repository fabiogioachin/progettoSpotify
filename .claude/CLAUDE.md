# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

### Backend (Python 3.12, FastAPI)

```bash
# Dev server
cd backend && uvicorn app.main:app --reload --port 8001

# Lint & format
cd backend && ruff check app/
cd backend && ruff format app/ --check
cd backend && ruff check app/ --fix && ruff format app/

# Tests
cd backend && pytest
cd backend && pytest tests/test_file.py::test_name -v

# Health check
curl -s http://127.0.0.1:8001/health
curl -s http://127.0.0.1:8001/health/detailed  # Admin-only: DB, Redis, users, jobs, Spotify reachability
```

### Frontend (Node 20, React 18, Vite)

```bash
cd frontend && npm install
cd frontend && npm run dev        # Dev server on :5173
cd frontend && npm run lint       # ESLint
cd frontend && npm run build      # Production build
```

### Docker

```bash
docker-compose -f docker/docker-compose.yml up --build         # PG + Redis + Backend :8001 + Frontend :5173
docker-compose -f docker/docker-compose.yml up postgres redis -d  # Only infra (for local dev without Docker backend)
```

### Database (PostgreSQL + Alembic)

```bash
cd backend && python -m alembic upgrade head     # Apply migrations
cd backend && python -m alembic revision --autogenerate -m "description"  # Generate migration
cd backend && python -m scripts.migrate_sqlite_to_pg  # One-time SQLite→PG data migration
cd backend && python -m scripts.backfill_artist_genres  # One-time: populate artist_genres cache from existing data
```

## Architecture

Monorepo: `backend/` (FastAPI async) + `frontend/` (React/Vite). PostgreSQL 16 + Redis 7 via Docker Compose. Alembic manages schema migrations. Vite dev server proxies `/api` and `/auth` to backend at :8001.

### API Versioning

All API endpoints live under `/api/v1/`. Legacy `/api/*` paths redirect to `/api/v1/*` via 308 middleware. Auth routes (`/auth/*`) and health routes (`/health`, `/health/detailed`) stay at root — not versioned.

### Backend request flow

`main.py` registers 16 routers (all behind `require_auth` dependency, except analysis polling endpoint; admin router behind `require_admin`) + APScheduler lifespan + middleware stack.

**Middleware stack** (execution order, outermost first): ProxyHeaders (optional) → APIRateLimiter (120 req/min per IP) → CORS → RateLimitHeaderMiddleware → RequestContextMiddleware (request_id + user_id via contextvars) → UserQuotaMiddleware (per-user tier-based rate limit) → api_version_redirect (308 legacy paths).

Each request: `require_auth` extracts user_id from signed session cookie → router creates `SpotifyClient(db, user_id)` → wraps in `RequestDataBundle(client)` → calls service methods with `bundle=bundle` → closes client in `finally` block.

**RequestDataBundle** (`data_bundle.py`): Request-scoped in-memory cache wrapping SpotifyClient. Caches `get_top_tracks`, `get_top_artists`, `get_recently_played`, `get_me` per (time_range, limit) key. `prefetch()` fetches all 3 time_ranges in parallel via `asyncio.gather`. Services accept `bundle=None` (backward compatible) — when provided, use bundle instead of direct client calls. Result: `/wrapped` 13→7 calls, `/profile` 5→4, `/trends` 6→3.

**Auth**: OAuth2 PKCE with stateless HMAC-signed state parameter. Session = signed cookie (itsdangerous URLSafeSerializer). Spotify tokens encrypted with Fernet (key derived via PBKDF2 from `SESSION_SECRET` + `ENCRYPTION_SALT`). Invite-gated registration: new users need a valid `InviteCode`; first user auto-promoted to admin. Existing users login normally without invite.

**Token refresh**: proactive (5-min buffer before expiry) + reactive retry-on-401 with forced refresh. Lock prevents concurrent refreshes.

**Rate limiting**: Four layers — API middleware (120 req/min per IP, Redis sorted set) + per-user quota (free=30/min, premium=60/min, admin=unlimited, Redis sorted set) + Spotify sliding window throttle (25 calls/30s, Redis sorted set) + API budget priority system (P0 interactive 70%, P1 login sync 20%, P2 batch 10%). All state in Redis for multi-worker support. Global semaphore(3) for in-process concurrency. Fail-open on Redis errors. **Atomic Lua script**: `_check_and_register()` consolidates cooldown + budget + throttle into a single `EVALSHA` call (1 Redis round-trip per Spotify API call, was 3).

**Error handling**: Centralized via 3 global exception handlers in `main.py` — `SpotifyAuthError` → 401, `RateLimitError`/`ThrottleError` → 429, `SpotifyServerError` → 502. Routers only catch `(SpotifyAuthError, RateLimitError, SpotifyServerError): raise` + `except Exception` for logging. New API endpoints get error handling for free.

**Structured logging**: `python-json-logger` in production (JSON with request_id, user_id, timestamp, level, logger, message). Human-readable in development. Request context propagated via `contextvars.ContextVar`.

**Background jobs** (APScheduler): `sync_recent_plays` hourly with staggering (users distributed across 55min, jitter=120s) + Redis skip tracking for rate-limited users + opportunistic genre cache population via `get_artist_genres_cached`. `save_daily_snapshot` on first daily login via `UserSnapshot` model. `compute_daily_aggregates` at 02:00 daily (jitter=300s) — computes `DailyListeningStats` including `top_genre` from `artist_genres` DB cache (DB-only, no API calls). `cleanup_expired_data` monthly (1st of month, 03:00) — prunes user_snapshots >365d, track_popularity >90d. Background jobs use P1/P2 priority via `api_budget.py`.

**Genre cache** (`genre_cache.py`): Three-tier cache for artist genres — DB `artist_genres` table (7-day TTL, shared across all users) → Redis artist cache (1h TTL) → Spotify API on miss. `get_artist_genres_cached(db, client, artist_ids)` centralizes all genre fetching. No artificial caps on artist count — the cache naturally bounds API calls. When `client=None` (background job context), returns DB-only data without API calls. `build_genre_distribution()` computes genre frequency from tracks. **Note**: Spotify dev mode returns empty genres for ALL artists — MusicBrainz is the primary genre source.

**Genre warmup** (startup, 3 phases): Phase 1: Spotify `get_artist()` for top_artists (returns empty in dev mode but caches the row). Phase 2: MusicBrainz fallback (`musicbrainz_client.py`) — search by name + MBID lookup, 1 req/s, tag blocklist filters non-genre tags. Phase 3: Playlist-inferred genres — maps genre-like playlist names to artists in those playlists. Only fills empty-genre artists, never overwrites.

**Playlist metadata** (`playlist_metadata` table): Permanent DB cache for playlist track counts, names, images, ownership. `GET /api/v1/playlists` reads DB cache first, launches background task for remaining zeros (sequential, 2s delay, retry on throttle). `GET /api/v1/playlists/counts` is DB-only for frontend polling.

**Audio analysis** (on-demand): `POST /api/v1/analyze-tracks` launches async librosa extraction from preview MP3s. Frontend polls `GET /api/v1/analyze-tracks/{task_id}` for progressive results. Background task uses dedicated DB session (not request-scoped). Results cached in `AudioFeatures` table.

**Privacy/GDPR**: `DELETE /api/v1/me/data` (full account deletion), `GET /api/v1/me/data/export` (JSON data export). Privacy page in frontend.

**Admin**: `/api/v1/admin/*` — user management, invite management, API usage stats, job monitoring, force-sync, user suspension. Protected by `require_admin` dependency.

**User model**: `is_admin` (Boolean), `onboarding_completed` (Boolean), `tier` (String: free/premium/admin).

### Data model

| Table | Purpose | TTL/Cleanup |
|-------|---------|-------------|
| `users` | User identity, auth, tier | Permanent |
| `spotify_tokens` | Encrypted OAuth tokens | Permanent |
| `artist_genres` | Genre cache per artist (JSON) | 7 days (TTL in queries) |
| `audio_features` | Librosa-extracted features per track | Permanent (on-demand) |
| `track_popularity` | Cached popularity per track | 90 days (monthly cleanup) |
| `recent_plays` | Accumulated listening history | Permanent |
| `user_snapshots` | Daily top artists/tracks snapshots | 365 days (monthly cleanup) |
| `daily_listening_stats` | Aggregated daily metrics (incl. top_genre) | Permanent |
| `user_profile_metrics` | Persistent profile scores | 1 row per user (upsert) |
| `invite_codes` | Registration gate | Permanent |
| `friendships` / `friend_invite_links` | Social connections | Permanent |

### Frontend flow

`App.jsx` → `AuthProvider` → `BrowserRouter` → lazy-loaded pages (13 pages) inside `ProtectedRoute` + `AppLayout` (Sidebar + Header).

Data fetching: `useSpotifyData(endpoint)` hook → Axios client with 429 retry interceptor (Retry-After ≤ 30s, max 2 retries) + 401 → dispatches `auth:expired` event → AuthContext triggers logout. Cache keys include user_id to prevent cross-user data leakage on login switch. PWA: installable via `vite-plugin-pwa` (cache-first static, network-only API). EmptyState component for charts with no data. SectionErrorBoundary wraps each chart section (max 2 retries).

**Onboarding**: 3-step modal shown on first login (`user.onboarding_completed === false`). "Non mostrare più" checkbox saves to `localStorage('wrap_onboarding_dismissed')` — per-device dismissal, independent from server-side `onboarding_completed`. Calls `POST /auth/onboarding-complete` on completion.

**Admin page**: Tabbed dashboard (Utenti, Inviti, Utilizzo API, Jobs). Conditionally visible in sidebar for admin users only.

**Privacy page**: Data usage explanation (Italian), export/download, account deletion with confirmation.

**Animations** (framer-motion): Page transitions via `AnimatePresence` in AppLayout (fade+slide). KPICards use `whileInView` for scroll-driven fade-in. Lists/grids use `StaggerContainer` + `StaggerItem` (40ms stagger). Mobile sidebar slides in/out via `motion.aside`. Loading states use skeleton loaders (`Skeleton.jsx`) matching component shapes.

## Critical Invariants

1. **SpotifyAuthError propagation**: every `except Exception` block in router/service code that calls SpotifyClient MUST be preceded by `except SpotifyAuthError: raise`. Swallowed auth errors show stale data instead of redirecting to login.

2. **asyncio.gather with 3+ calls**: always wrap each coroutine in `_safe_fetch()` or use `return_exceptions=True`. One Spotify API failure must not crash the entire page.

3. **Non-critical DB writes never block responses**: wrap snapshot saves and similar writes in inner `try/except` with `logger.warning`. Analytics endpoints must never 500 because a logging write failed.

4. **Background tasks need dedicated DB sessions**: `asyncio.create_task()` outlives the request handler — the `get_db()` session is closed when the handler returns. Background tasks must create their own session via `async_session()`.

5. **No plausible fake defaults**: missing data defaults to `None`/`0`/`[]`, never magic numbers like `default=180000` that look like real measurements. Backend returns `has_*` / `*_source` flags; frontend uses them for conditional rendering instead of showing silent empty cards.

6. **Pure-compute services never call Spotify API**: Services like `taste_clustering.py` and `genre_utils.py` work exclusively on local data (DB cache, in-memory structures). They must never import `SpotifyClient` or make HTTP calls. Note: `taste_map.py` is an orchestrator that fetches data via SpotifyClient then delegates to pure-compute modules.

7. **Genre fetching goes through `genre_cache.py`**: All genre lookups use `get_artist_genres_cached()`. Never fetch genres inline in routers or services. The cache handles DB lookup, API fetch on miss, and upsert. No artificial caps on artist count.

## Spotify API Constraints

- **Deprecated/removed in dev mode** (do not use): Audio Features, Recommendations, Related Artists (`/artists/{id}/related-artists`), Artist Top Tracks (`/artists/{id}/top-tracks`), batch endpoints (`/artists?ids=`, `/tracks?ids=`, `/albums?ids=`)
- **Feb 2026 dev mode migration**: `/playlists/{id}/tracks` → **`/playlists/{id}/items`** (old returns 403). `GET /playlists/{id}` no longer includes tracks.
- Individual endpoints with semaphore + asyncio.gather replace all batch endpoints
- Time ranges: only `short_term` (~4w), `medium_term` (~6m), `long_term` (all) — no custom ranges
- Recently played: max 50 items — workaround is DB accumulation via `RecentPlay` model
- **Always available**: popularity, genres, track/artist metadata, user profile

## File Organization

Root must stay clean — only essential project config (`.gitignore`, `.env.example`, `README.md`). Before creating any new file, evaluate where it belongs:

- `backend/app/` — all backend source code
- `backend/alembic/` — database migrations (Alembic)
- `backend/scripts/` — one-time scripts (data migration, backfill)
- `frontend/src/` — all frontend source code
- `docker/` — Dockerfiles, Caddy config, docker-compose files
- `.claude/CLAUDE.md` — project instructions for Claude Code
- `.claude/tasks/` — operational tracking: `todo.md`, `lessons.md`, generated reports (`HEALTH-REPORT.md`)
- `docs/` — project documentation (`PRD.md`, `LAUNCH-PLAN.md`)

Never drop files in root. If a new category emerges, create a subdirectory.

## Conventions

- UI text: **Italian** (labels, error messages, tooltips, export prompts)
- Period labels: `1M / 6M / All` (not "Ultimo mese / 6 mesi / Sempre")
- "Cluster" renamed to **"Cerchia"** throughout (more meaningful in Italian)
- Accent color: `#6366f1` (indigo), not Spotify green — to differentiate the app
- Commits: conventional style (`fix:`, `feat:`, `chore:`)
- Default branch: `master`
- Task tracking: `.claude/tasks/todo.md` + `.claude/tasks/lessons.md` (update lessons after every correction)
- Styling: Tailwind + CSS variables in `frontend/src/styles/globals.css`. Fonts: Space Grotesk (display), Inter (body)
- Animations: framer-motion for page transitions, stagger, scroll-reveal, sidebar. Skeleton loaders for loading states.
- Empty sections: hide rather than showing "nessun dato disponibile"
