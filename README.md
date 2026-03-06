# Spotify Listening Intelligence

Dashboard di analisi musicale personale che va oltre Spotify Wrapped. Collega il tuo account Spotify, esplora insight avanzati sui tuoi ascolti, e genera report per Claude AI.

## Funzionalita'

- **Dashboard**: KPI reali animati, profilo audio radar, trend temporali, distribuzione generi
- **Confronto Playlist**: confronta fino a 4 playlist con grafici comparativi
- **Discovery**: mappa mood, brani outlier, suggerimenti personalizzati
- **Export per Claude**: genera un prompt strutturato con i tuoi dati per analisi narrativa con Claude AI

## Stack Tecnologico

| Layer | Tecnologia |
|-------|------------|
| Backend | FastAPI (Python 3.12) |
| Frontend | React 18 + Vite + Tailwind CSS |
| Charts | Recharts |
| Database | SQLite (SQLAlchemy async + aiosqlite) |
| Auth | OAuth 2.0 (Spotify) |
| Container | Docker + docker-compose |

## Setup Locale (senza Docker)

### Prerequisiti

- Python 3.12+
- Node.js 20+
- Un'app Spotify Developer (vedi [docs/SPOTIFY_SETUP.md](./docs/SPOTIFY_SETUP.md))

### 1. Configura le variabili d'ambiente

```bash
cp .env.example .env
# Modifica .env con le tue credenziali Spotify
```

### 2. Backend

```bash
cd backend
python -m venv .venv
source .venv/bin/activate   # Linux/Mac
# .venv\Scripts\activate    # Windows
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8001
```

### 3. Frontend

```bash
cd frontend
npm install
npm run dev
```

Apri http://127.0.0.1:5173

## Setup con Docker

```bash
cp .env.example .env
# Modifica .env con le tue credenziali Spotify

docker-compose up --build
```

- Frontend: http://127.0.0.1:5173
- Backend API: http://127.0.0.1:8001
- Health check: http://127.0.0.1:8001/health

## Struttura Progetto

```
spotify-intelligence/
├── backend/          # FastAPI app
│   ├── app/
│   │   ├── main.py           # Entry point
│   │   ├── config.py         # Settings
│   │   ├── database.py       # SQLAlchemy setup
│   │   ├── models/           # DB models
│   │   ├── routers/          # API endpoints
│   │   ├── services/         # Business logic
│   │   └── utils/            # Token manager, rate limiter
│   ├── requirements.txt
│   └── Dockerfile
├── frontend/         # React app
│   ├── src/
│   │   ├── pages/            # Route pages
│   │   ├── components/       # UI components
│   │   ├── contexts/         # Auth context
│   │   ├── hooks/            # Custom hooks
│   │   └── lib/              # API client, chart config
│   ├── package.json
│   └── Dockerfile
├── docs/
│   ├── PRD.md                   # Product Requirements
│   └── SPOTIFY_SETUP.md         # Guida setup Spotify Developer
├── tasks/
│   ├── todo.md                  # Task list
│   └── lessons.md               # Lessons learned
├── docker-compose.yml
└── .env.example
```

## API Endpoints

| Endpoint | Descrizione |
|----------|------------|
| `GET /auth/spotify/login` | Avvia OAuth flow |
| `GET /auth/spotify/callback` | Callback OAuth |
| `GET /auth/me` | Profilo utente corrente |
| `POST /auth/logout` | Logout |
| `GET /api/library/top` | Top brani |
| `GET /api/library/recent` | Brani recenti |
| `GET /api/library/saved` | Brani salvati |
| `GET /api/playlists` | Lista playlist |
| `GET /api/playlists/compare` | Confronto playlist |
| `GET /api/analytics/features` | Profilo audio |
| `GET /api/analytics/trends` | Trend temporali |
| `GET /api/analytics/discovery` | Discovery |
| `GET /api/export/claude-prompt` | Export per Claude |
