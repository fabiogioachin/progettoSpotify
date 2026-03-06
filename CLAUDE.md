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
docker-compose up --build         # Backend :8001 + Frontend :5173
```

## Architecture

Monorepo: `backend/` (FastAPI async) + `frontend/` (React/Vite). SQLite database in `data/` (gitignored). Vite dev server proxies `/api` and `/auth` to backend at :8001.

### Backend request flow

`main.py` registers 10 routers (all behind `require_auth` dependency) + APScheduler lifespan + middleware stack (rate limiter → CORS).

Each request: `require_auth` extracts user_id from signed session cookie → router creates `SpotifyClient(db, user_id)` → calls service methods → closes client in `finally` block.

**Auth**: OAuth2 PKCE with stateless HMAC-signed state parameter. Session = signed cookie (itsdangerous URLSafeSerializer). Spotify tokens encrypted with Fernet (key derived via PBKDF2 from `SESSION_SECRET` + `ENCRYPTION_SALT`).

**Token refresh**: proactive (5-min buffer before expiry) + reactive retry-on-401 with forced refresh. Lock prevents concurrent refreshes.

**Rate limiting**: Two layers — API middleware (120 req/min per IP) + Spotify 429 propagation with Retry-After header to frontend.

**Background jobs** (APScheduler): `sync_recent_plays` hourly (accumulates beyond Spotify's 50-item hard limit), `save_daily_snapshot` on first daily login via `UserSnapshot` model.

### Frontend flow

`App.jsx` → `AuthProvider` → `BrowserRouter` → lazy-loaded pages inside `ProtectedRoute` + `AppLayout` (Sidebar + Header).

Data fetching: `useSpotifyData(endpoint)` hook → Axios client with 429 retry interceptor (Retry-After ≤ 30s, max 2 retries) + 401 → dispatches `auth:expired` event → AuthContext triggers logout.

## Critical Invariants

1. **SpotifyAuthError propagation**: every `except Exception` block in router/service code that calls SpotifyClient MUST be preceded by `except SpotifyAuthError: raise`. Swallowed auth errors show stale data instead of redirecting to login.

2. **asyncio.gather with 3+ calls**: always wrap each coroutine in `_safe_fetch()` or use `return_exceptions=True`. One Spotify API failure must not crash the entire page.

3. **Non-critical DB writes never block responses**: wrap snapshot saves and similar writes in inner `try/except` with `logger.warning`. Analytics endpoints must never 500 because a logging write failed.

4. **No plausible fake defaults**: missing data defaults to `None`/`0`/`[]`, never magic numbers like `default=180000` that look like real measurements. Backend returns `has_*` / `*_source` flags; frontend uses them for conditional rendering instead of showing silent empty cards.

## Spotify API Constraints

- **Audio Features** and **Recommendations** endpoints are **DEPRECATED** — do not use for new features
- Time ranges: only `short_term` (~4w), `medium_term` (~6m), `long_term` (all) — no custom ranges
- Recently played: max 50 items — workaround is DB accumulation via `RecentPlay` model
- Always available: popularity, genres, track/artist metadata, related artists, artist top tracks

## Conventions

- UI text: **Italian** (labels, error messages, tooltips, export prompts)
- Period labels: `1M / 6M / All` (not "Ultimo mese / 6 mesi / Sempre")
- "Cluster" renamed to **"Cerchia"** throughout (more meaningful in Italian)
- Accent color: `#6366f1` (indigo), not Spotify green — to differentiate the app
- Commits: conventional style (`fix:`, `feat:`, `chore:`)
- Default branch: `master`
- Task tracking: `tasks/todo.md` + `tasks/lessons.md` (update lessons after every correction)
- Styling: Tailwind + CSS variables in `frontend/src/styles/globals.css`. Fonts: Space Grotesk (display), Inter (body)
- Empty sections: hide rather than showing "nessun dato disponibile"
