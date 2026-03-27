# Wrap

Dashboard di analisi musicale personale che va oltre Spotify Wrapped. Collega il tuo account Spotify, esplora insight avanzati sui tuoi ascolti, e genera report per Claude AI.

## Funzionalita'

- **Dashboard**: KPI animati, profilo audio radar, trend temporali, distribuzione generi (treemap)
- **Profilo**: obscurity score, genere DNA, decade distribution, taste map
- **Confronto Playlist**: confronta fino a 4 playlist con grafici comparativi (popolarita', generi, audio features)
- **Analisi Playlist**: statistiche aggregate, distribuzione dimensioni, concentrazione artisti
- **Rete Artisti**: grafo interattivo con cerchie (Louvain communities), PageRank, betweenness centrality
- **Discovery**: mappa mood, brani outlier, distribuzione popolarita'
- **Evoluzione Gusto**: confronto temporale (1M / 6M / All) con metriche di cambiamento
- **Analisi Temporale**: heatmap orari, pattern giornalieri, streak di ascolto
- **Wrapped**: storia interattiva stile Spotify Wrapped con i tuoi dati reali
- **Social**: confronto con amici, compatibility meter
- **Export per Claude**: genera un prompt strutturato per analisi narrativa con Claude AI
- **Admin**: gestione utenti, inviti, monitoraggio API e job
- **Privacy/GDPR**: export dati, cancellazione account

## Stack Tecnologico

| Layer | Tecnologia |
|-------|------------|
| Backend | FastAPI (Python 3.12, async) |
| Frontend | React 18 + Vite + Tailwind CSS |
| Charts | Recharts + D3 (rete artisti) |
| Database | PostgreSQL 16 (Alembic migrations) |
| Cache | Redis 7 (rate limiting, caching) |
| Auth | OAuth 2.0 PKCE (Spotify) |
| Container | Docker Compose |
| PWA | vite-plugin-pwa (installabile) |

## Setup Locale

### Prerequisiti

- Python 3.12+
- Node.js 20+
- Docker (per PostgreSQL e Redis)
- Un'app Spotify Developer

### 1. Configura le variabili d'ambiente

```bash
cp .env.example .env
# Modifica .env con le tue credenziali Spotify
```

### 2. Avvia infrastruttura

```bash
docker-compose -f docker/docker-compose.yml up postgres redis -d
```

### 3. Backend

```bash
cd backend
python -m venv .venv
source .venv/bin/activate   # Linux/Mac
# .venv\Scripts\activate    # Windows
pip install -r requirements.txt
python -m alembic upgrade head   # Applica migrazioni DB
uvicorn app.main:app --reload --port 8001
```

### 4. Frontend

```bash
cd frontend
npm install
npm run dev
```

Apri http://127.0.0.1:5173

## Setup con Docker (tutto-in-uno)

```bash
cp .env.example .env
# Modifica .env con le tue credenziali Spotify

docker-compose -f docker/docker-compose.yml up --build
```

- Frontend: http://127.0.0.1:5173
- Backend API: http://127.0.0.1:8001
- Health check: http://127.0.0.1:8001/health

## Struttura Progetto

```
progettoWrap/
├── backend/              # FastAPI app
│   ├── app/
│   │   ├── main.py               # Entry point + middleware + exception handlers
│   │   ├── config.py             # Settings
│   │   ├── database.py           # SQLAlchemy async setup (PostgreSQL)
│   │   ├── dependencies.py       # Auth dependency (require_auth, require_admin)
│   │   ├── constants.py          # Global constants
│   │   ├── models/               # SQLAlchemy models
│   │   ├── routers/              # API endpoints (16 routers)
│   │   ├── services/             # Business logic + genre_cache + spotify_client
│   │   ├── middleware/           # Rate limiting, request context, user quota
│   │   └── utils/                # Rate limiter, JSON sanitizer
│   ├── alembic/                  # Database migrations
│   ├── scripts/                  # One-time scripts (migration, backfill)
│   ├── tests/                    # pytest test suite
│   └── requirements.txt
├── frontend/             # React app
│   ├── src/
│   │   ├── pages/                # 13 lazy-loaded pages
│   │   ├── components/           # UI components (charts, layout, onboarding, wrapped)
│   │   ├── contexts/             # AuthContext
│   │   ├── hooks/                # useSpotifyData, useAudioAnalysis, usePlaylistCompare
│   │   ├── lib/                  # API client, chart config
│   │   └── styles/               # globals.css (Tailwind + CSS variables)
│   └── package.json
├── docker/               # Dockerfiles, Caddy config, docker-compose
├── docs/                 # PRD, LAUNCH-PLAN
├── .claude/              # Claude Code config, tasks, skills
└── .env.example
```

## API Endpoints (v1)

| Endpoint | Descrizione |
|----------|------------|
| `GET /auth/spotify/login` | Avvia OAuth PKCE flow |
| `GET /auth/spotify/callback` | Callback OAuth |
| `GET /auth/me` | Profilo utente + sync recenti |
| `POST /auth/logout` | Logout |
| `GET /api/v1/library/top` | Top brani/artisti per periodo |
| `GET /api/v1/library/recent` | Brani recenti |
| `GET /api/v1/playlists` | Lista playlist |
| `GET /api/v1/playlists/compare` | Confronto playlist (2-4) |
| `GET /api/v1/playlist-analytics` | Analisi aggregata playlist |
| `GET /api/v1/analytics/trends` | Trend temporali + generi |
| `GET /api/v1/analytics/discovery` | Discovery + outlier |
| `GET /api/v1/profile` | Profilo completo + metriche |
| `GET /api/v1/artist-network` | Grafo rete artisti |
| `GET /api/v1/taste-evolution` | Evoluzione gusto musicale |
| `GET /api/v1/temporal-patterns` | Pattern temporali ascolto |
| `GET /api/v1/wrapped` | Dati per Wrapped story |
| `POST /api/v1/analyze-tracks` | Avvia analisi audio (librosa) |
| `GET /api/v1/export/claude-prompt` | Export strutturato per Claude |
| `GET /api/v1/admin/*` | Gestione utenti, inviti, API stats |
| `GET /api/v1/me/data/export` | Export GDPR dati personali |
| `DELETE /api/v1/me/data` | Cancellazione account GDPR |
| `GET /health` | Health check |
| `GET /health/detailed` | Health dettagliato (admin) |
