# Piano di Ristrutturazione: Spotify Intelligence → Multi-User Beta

## Context

L'app è un tool personale single-user con architettura solida (stateless auth, async-first, 3-tier rate limiting, 7 tabelle DB). L'obiettivo è trasformarla in una beta multi-utente (5-20 amici), preparata per un lancio pubblico futuro.

**Decisioni prese:**
- Auth: solo Spotify login, accesso gated via invite link
- DB: PostgreSQL subito (no SQLite → migrate later)
- Mobile: PWA (installabile su iOS/Android senza App Store)
- Hosting: VPS (Hetzner ~5-10€/mese) + Docker Compose
- Budget: ~10-20€/mese, soluzione riusabile

---

## Session Planning (Claude Code Opus 4.6 — 1M token)

Overhead base per sessione: ~30k token (system prompt, tools, skill, memory).
Token per phase: esplorazione (~30k) + planning (~40k) + implementazione (~60-100k) + review (~40k) + test (~20k).

| Sessione | Phase | Razionale | Token stimati |
|----------|-------|-----------|---------------|
| **1** | 0 + 1 | Infrastruttura: directory + Docker + PostgreSQL. Contesto condiviso (paths, DB, config). | ~350k |
| **2** | 2 | Backend multi-user: Redis, rate budget, invite auth, job staggering. Fase più complessa, serve sessione dedicata. | ~300k |
| **3** | 3 + 4 | Frontend: PWA, empty states, bug fixes UI. Contesto condiviso (componenti, pagine, Recharts). | ~300k |
| **4** | 5 + 7 + 8 | Polish: observability, production readiness, PRD/skill update. Fasi più leggere, si combinano. | ~350k |

**4 sessioni totali.** Ogni sessione ha margine (~300-400k token liberi) per fix imprevisti, re-dispatch di agent, e debugging.

### Come aprire ogni sessione
```
Sessione 1: /feature Phase 0 + Phase 1 del piano in docs/RESTRUCTURING-PLAN.md
Sessione 2: /feature Phase 2 del piano in docs/RESTRUCTURING-PLAN.md
Sessione 3: /feature Phase 3 + Phase 4 del piano in docs/RESTRUCTURING-PLAN.md
Sessione 4: /feature Phase 5 + Phase 7 + Phase 8 del piano in docs/RESTRUCTURING-PLAN.md
```

---

## Dependency Graph

```
Phase 0 (Restructuring)
    │
    ▼
Phase 1 (PostgreSQL) ─────────────────────────────┐
    │                                               │
    ▼                                               ▼
Phase 2 (Backend Multi-User)              Phase 3 (Frontend + PWA)
    │                                               │
    ├───────────────► Phase 4 (Bug Fixes) ◄────────┘
    │                       │
    ▼                       ▼
Phase 5 (Observability + Privacy)
    │
    ▼
Phase 7 (Production Readiness)
    │
    ▼
Phase 8 (PRD + Skills Update)

─── todo.md (post-piano) ───
Phase 6 (Deploy Pipeline) ──► BETA LAUNCH 🚀
Phase 7.7 (Spotify Extended Quota) ──► PUBLIC LAUNCH prep
```

**Parallelizzabili:** Phase 2 ∥ Phase 3 (backend vs frontend, nessuno stato condiviso).

---

## Phase 0: Project Restructuring

### 0.1 Riorganizzazione directory
- `backend/Dockerfile` → `docker/backend.Dockerfile`
- `frontend/Dockerfile` → `docker/frontend.Dockerfile`
- `tasks/` → `.claude/tasks/` (update .gitignore per tracciare)
- `HEALTH-REPORT.md` → `.claude/tasks/HEALTH-REPORT.md`
- Creare `docker/caddy/Caddyfile` (placeholder per Phase 6)

### 0.2 Modernizzare docker-compose.yml
- Aggiungere servizi: PostgreSQL 16, Redis 7 (pronti per Phase 1-2)
- Healthchecks su tutti i servizi
- `depends_on` con `condition: service_healthy`
- Network esplicito `app-network`
- Separare `docker-compose.yml` (dev) e `docker-compose.prod.yml`

### 0.3 Environment management
- `.env.development` e `.env.production` templates
- Aggiornare `.env.example` con `DATABASE_URL` (PostgreSQL), `REDIS_URL`
- Aggiungere `ENVIRONMENT=development|production`

**Files:** `docker-compose.yml`, `docker/*.Dockerfile`, `.gitignore`, `CLAUDE.md`, `.env.example`

---

## Phase 1: Database Migration SQLite → PostgreSQL

### 1.1 Dipendenze
- `aiosqlite` → `asyncpg` + `psycopg2-binary`
- Aggiungere `alembic`

### 1.2 database.py — riscrittura
- Connection string: `postgresql+asyncpg://...`
- Connection pool: `pool_size=10, max_overflow=20, pool_pre_ping=True`
- Rimuovere `init_db()` (no more manual ALTER TABLE)
- Mantenere interfaccia: `Base`, `get_db()`, `async_session`

### 1.3 Alembic setup
- `alembic init backend/alembic`
- Configurare `env.py` per async engine
- Generare initial migration da modelli esistenti

### 1.4 Fix codice SQLite-specifico (CRITICO)
| File | Problema | Fix |
|------|----------|-----|
| `services/background_tasks.py:11` | `sqlite_insert` | → `postgresql.insert` |
| `services/spotify_client.py:101,134,137` | `replace(tzinfo=None)` | → datetime timezone-aware |
| `services/temporal_patterns.py:214` | `replace(tzinfo=None)` | → datetime timezone-aware |
| `services/profile_metrics.py:109,111,361,363` | `func.date()` + naive dt | → `cast(col, Date)` |
| `services/audio_analyzer.py:225` | `func.date()` | → `cast(col, Date)` |
| Tutti i modelli | `DateTime` naive | → `DateTime(timezone=True)` |

### 1.5 Script migrazione dati
- `scripts/migrate_sqlite_to_pg.py` — one-time: legge da SQLite, inserisce in PostgreSQL
- Gestire: conversione datetime naive → UTC-aware, reset sequenze PK

### 1.6 Verifica
- Eseguire tutti i test con PostgreSQL
- Verificare che le query complesse (aggregazioni daily_stats, heatmap) funzionino

**Files:** `database.py`, `config.py`, `requirements.txt`, tutti i `services/*.py` con datetime, tutti i `models/*.py`, nuovo `alembic/`

---

## Phase 2: Backend Hardening Multi-User

### 2.1 Rate limit budget system
Con 20 utenti che condividono 25 calls/30s:

**Priority queue (`services/api_budget.py`):**
- P0 (Interactive): page loads utente → 70% budget
- P1 (Background-interactive): login sync → 20% budget
- P2 (Batch): hourly sync all users → 10% budget
- Fair sharing: nessun utente >30% del budget del suo tier
- Degradazione: se budget esaurito → estendi cache TTL, poi pausa P2, poi queue P1, infine serve dati cached con header "stale"

### 2.2 Redis integration
- Nuovo `services/redis_client.py` — async singleton
- Migrare cache da in-memory a Redis:
  - `cache:user:{uid}:top_tracks:{range}` (TTL 5m)
  - `cache:artist:{aid}` (TTL 1h, globale)
  - `cache:user:{uid}:recent` (TTL 2m)
- Migrare rate limit state a Redis:
  - Sorted set per sliding window
  - Key con TTL per cooldown

### 2.3 Background jobs multi-utente
- Staggerare sync: distribuire 20 utenti nell'ora (User 1 a :00, User 2 a :03, ...)
- Jitter random 0-60s al restart per evitare thundering herd
- Tracciare utenti saltati per rate limit → retry nel ciclo successivo

### 2.4 Invite-gated registration
- Nuovo modello `InviteCode(code, created_by, max_uses, uses, expires_at)`
- Flusso: `/auth/spotify/login?invite=CODE` → code nel state HMAC → validazione in callback
- Utente nuovo senza invite valido = redirect con errore "Accesso solo su invito"
- Utenti esistenti: login normale (no invite)
- Primo utente (tu) = admin automatico

### 2.5 Data isolation audit
- Grep tutte le `select(` → verificare `.where(user_id == ...)` presente
- Cache artist/track sono correttamente user-independent (dati pubblici)

**Files:** nuovo `services/api_budget.py`, nuovo `services/redis_client.py`, `spotify_client.py`, `background_tasks.py`, `main.py`, `rate_limiter.py`, `routers/auth.py`, `models/user.py`, `requirements.txt`, `docker-compose.yml`

---

## Phase 3: Frontend Hardening + PWA (PARALLELA a Phase 2)

### 3.1 PWA Setup
- `frontend/public/manifest.json` — nome, tema `#6366f1`, icone 192/512px
- Service worker via `vite-plugin-pwa` (cache-first per static, network-first per API)
- Meta tags Apple per iOS installability
- Test installabilità su Chrome DevTools

### 3.2 Empty state handling (TUTTI i grafici)
Creare `components/ui/EmptyState.jsx` — riusabile con icona, messaggio, azione opzionale.

Grafici che scompaiono con dati null:
| Componente | Condizione attuale | Fix |
|------------|-------------------|-----|
| MoodScatter | `!hasMoodData` → sparisce | EmptyState "Analisi audio non disponibile" |
| AudioRadar | centroid vuoto → sparisce | EmptyState + messaggio |
| GenreTreemap | genres vuoto → sparisce | EmptyState "Generi in fase di analisi" |
| PopularityDistribution | nessun bucket → sparisce | EmptyState |
| TrendTimeline | no trends → return null | EmptyState "Dati insufficienti" |
| ArtistNetwork | nodes vuoto → SVG vuoto | EmptyState "Ascolta più artisti" |
| ListeningHeatmap | no data → griglia vuota | EmptyState |

### 3.3 Error boundaries per sezione
- `components/ui/SectionErrorBoundary.jsx` — "Errore nel caricamento" + retry
- Wrappare ogni sezione/card nelle pagine
- Mantenere ErrorBoundary top-level come fallback

### 3.4 Mobile responsive
- Audit 11 pagine su 375px/390px/768px
- `ResponsiveContainer` su tutti i Recharts
- Grid layouts con breakpoints Tailwind

### 3.5 Cache utente nel frontend
- `useSpotifyData` hook: aggiungere user context alla cache key
- Evitare che login switch mostri dati del precedente utente

**Files:** nuovo `manifest.json`, nuovo `EmptyState.jsx`, nuovo `SectionErrorBoundary.jsx`, `vite.config.js`, `package.json`, `index.html`, tutte le pagine e componenti chart

---

## Phase 4: Bug Fixes

### 4.1 Artist diversity 100%
- **Root cause**: probabilmente `unique_artists / total_plays` con pochi ascolti → 100%
- **Fix**: usare Shannon entropy (più nuanced), soglia minima 20+ plays, tooltip esplicativo
- **File**: `services/profile_metrics.py`

### 4.2 Cerchie → genere-based con stile KG
- Estrarre generi dominanti per cluster (DBSCAN/Louvain già li calcola)
- Nome: genere dominante ("Cerchia Hip-Hop", "Cerchia Indie Rock")
- Contenuto: artisti del cluster con connessioni visuali
- Stile: knowledge graph — nodi genere grandi, nodi artista piccoli connessi
- **Files**: `services/taste_clustering.py`, `pages/ArtistNetworkPage.jsx`

### 4.3 Discover Weekly / Release Radar
- Filtrare playlist per `owner.id === 'spotify'` + name matching
- Mostrare in sezione dedicata su DiscoveryPage
- **Files**: `routers/playlists.py` o `services/discovery.py`, `pages/DiscoveryPage.jsx`

### 4.4 Charts null data (coperto da Phase 3.2)
- Recharts: `connectNulls` sui Line charts
- Dati mancanti = gap nel grafico, non crash

---

## Phase 5: Observability + Privacy

### 5.1 Logging strutturato
- `python-json-logger` — JSON per ogni log line
- Middleware: inject `user_id` + `request_id` (UUID) nel context
- Log levels: DEBUG (dev), INFO (prod)

### 5.2 Privacy
- Pagina `/privacy` nel frontend (static)
- `DELETE /api/me/data` — cancella tutti i dati utente (GDPR)
- `GET /api/me/data/export` — esporta dati utente in JSON

### 5.3 Health endpoint
- `/health` (semplice, per load balancer): DB + Redis ping
- `/health/detailed` (admin): utenti attivi, stato job, Spotify reachability

### 5.4 Error tracking
- Sentry free tier (5k events/mese)
- Backend: `sentry-sdk[fastapi]`
- Frontend: `@sentry/react`

**Files:** `main.py`, nuovo `middleware/logging.py`, nuovo `routers/gdpr.py`, nuovo `pages/PrivacyPage.jsx`, `requirements.txt`, `package.json`

---

## Phase 7: Production Readiness (predisposizione lancio pubblico)

Prepara le fondamenta perché il passaggio beta → pubblico sia incrementale, non una riscrittura.

### 7.1 API Versioning
- Tutti gli endpoint sotto `/api/v1/` (ora sono `/api/`)
- Redirect `/api/*` → `/api/v1/*` per backward compatibility
- **Files**: tutti i router, `main.py`, `vite.config.js` proxy

### 7.2 Admin dashboard (minimale)
- Pagina `/admin` protetta (solo utenti con `is_admin=True`)
- Viste: lista utenti, gestione inviti, utilizzo API per utente, stato background jobs
- Azioni: genera inviti, sospendi utente, forza sync
- **Files**: nuovo `routers/admin.py`, nuovo `pages/AdminPage.jsx`

### 7.3 Onboarding flow (prima esperienza utente)
- Dopo primo login: splash "Benvenuto" → spiega cosa fa l'app → "I tuoi dati arriveranno nelle prossime ore"
- Flag `User.onboarding_completed` — mostra onboarding solo una volta
- Placeholder intelligenti nei grafici per nuovi utenti
- **Files**: `models/user.py`, nuovo `components/onboarding/`, tutte le pagine

### 7.4 i18n readiness (non tradurre ora, ma preparare)
- Estrarre tutte le stringhe UI in file di traduzione (`frontend/src/i18n/it.json`)
- Usare una funzione `t('key')` wrapper (react-i18next o semplice lookup)
- Per la beta: solo italiano. Per il lancio: aggiungere `en.json`
- **Files**: nuovo `frontend/src/i18n/`, tutti i componenti con stringhe hardcoded

### 7.5 Data retention policy
- `recent_plays`: forever | `daily_listening_stats`: forever | `user_snapshots`: 1 anno | `track_popularity`: 90 giorni | `audio_features`: forever
- Cleanup job mensile per dati scaduti
- Documentare nella privacy policy

### 7.6 User quotas e throttling per utente
- `User.tier` (free/premium/admin) — per ora tutti "free"
- Rate limit per utente: max N page loads/minuto
- Prep per monetizzazione futura
- **Files**: `models/user.py`, `middleware/`, `api_budget.py`

### 7.8 Job runner abstraction
- Estrarre logica APScheduler in service functions con interfaccia swappable
- Oggi: APScheduler in-process. Domani: Celery/ARQ senza cambiare i service
- **Files**: nuovo `services/job_runner.py`, `main.py` lifespan

---

## Phase 8: PRD + Skills + CLAUDE.md Update

- Aggiornare `CLAUDE.md`: nuovi comandi Docker, architettura PostgreSQL/Redis/Caddy, API v1
- Aggiornare `docs/PRD.md`: visione multi-user beta → pubblico, invite system, privacy, tiers
- Aggiornare skill `spotify-api-budget`: priority queue system
- Nuove skill: `postgresql-patterns`, `redis-cache`, `pwa-patterns`

---

## Concetti deprecati risolti da questo piano

| Pattern attuale | Problema | Risolto in |
|----------------|----------|------------|
| `init_db()` con ALTER TABLE manuali | Fragile, non reversibile | Phase 1 → Alembic |
| In-memory cache (`TTLCache`) | Perso al restart, non condivisibile | Phase 2 → Redis |
| `asyncio.Semaphore(3)` globale | Single-process only | Phase 2 → Redis distributed lock |
| `replace(tzinfo=None)` ovunque | SQLite hack, sbagliato con PostgreSQL | Phase 1 → timezone-aware |
| `sqlite_insert` dialect import | DB-specifico | Phase 1 → PostgreSQL dialect |
| Health endpoint minimale | Non dice nulla sullo stato reale | Phase 5 → health dettagliato |
| Grafici che scompaiono con dati null | UX rotta | Phase 3 → EmptyState |
| Stringhe UI hardcoded in italiano | Non scalabile per i18n | Phase 7 → extraction |
| No API versioning (`/api/`) | Breaking changes inevitabili | Phase 7 → `/api/v1/` |
| APScheduler in lifespan | Single-process, non swappable | Phase 7 → job runner abstraction |
| No onboarding per nuovi utenti | UX pessima al primo login | Phase 7 → onboarding flow |

---

## Summary

| Phase | Rischio | Parallelizzabile? |
|-------|---------|-------------------|
| 0: Restructuring | Basso | Primo (sequenziale) |
| 1: PostgreSQL | **Alto** | Sequenziale dopo 0 |
| 2: Backend Multi-User | **Alto** | ∥ con 3 |
| 3: Frontend + PWA | Medio | ∥ con 2 |
| 4: Bug Fixes | Basso | Dopo 1+3 |
| 5: Observability + Privacy | Basso | Sequenziale |
| 7: Production Readiness | Medio | Sequenziale dopo 5 |
| 8: PRD + Skills | Nessuno | Ultimo |

Tutto sviluppato e testato in locale (Docker Compose, 0€).
Phase 6 (deploy) e 7.7 (Extended Quota) vanno in `todo.md` — richiedono hosting/spesa.

**Rischi principali:**
1. Migrazione datetime SQLite → PostgreSQL (naive vs aware in tutto il codebase)
2. Rate limit budget system (design sbagliato = app inutilizzabile o ban Spotify)
3. Invite-gated auth (deve essere bulletproof)

**Skill da aggiornare prima dell'implementazione:**
- `fastapi-spotify-patterns` — aggiungere PostgreSQL, Redis, Alembic
- `react-spotify-patterns` — aggiungere PWA, EmptyState, SectionErrorBoundary
- `spotify-api-budget` — aggiungere priority queue multi-user
- Nuove: `postgresql-patterns`, `redis-cache`, `pwa-patterns`

---

## Verification Plan

Per ogni phase:
1. `cd backend && ruff check app/ && ruff format app/ --check` — lint
2. `cd backend && pytest` — test
3. `cd frontend && npm run lint && npm run build` — frontend
4. `docker compose up --build` — integrazione
5. Login manuale → verifica ogni pagina con dati
6. Test con 2+ utenti simultanei (dopo Phase 2)

---

## Post-ristrutturazione → todo.md

Le seguenti voci NON fanno parte di questo piano. Saranno scritte in `tasks/todo.md` al termine della Phase 5:

### Deploy Pipeline → BETA LAUNCH 🚀
- Production Docker Compose (Caddy HTTPS, gunicorn workers)
- CI/CD GitHub Actions (lint → test → build → deploy)
- Hosting: Hetzner CX22 (~5€/mese) + dominio
- Backup PostgreSQL (pg_dump daily, rotazione 7d+4w)

### Spotify Extended Quota Mode
- Creare `docs/spotify-submission/` con screenshot app, descrizione scope, privacy policy URL, redirect URI produzione
- Submit su developer.spotify.com → review 2-4 settimane
- Con Extended Quota: rimuovere whitelist manuale, tutti possono loggarsi
