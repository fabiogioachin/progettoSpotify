# Spotify Listening Intelligence — Product Requirements Document

## 1. Visione
Dashboard di analytics personale che analizza i dati di ascolto Spotify dell'utente, visualizzando pattern, evoluzione del gusto e ecosistema musicale con una UI ispirata a Spotify.

## 2. Utenti Target
- Ascoltatori Spotify curiosi del proprio profilo musicale
- Music enthusiast che vogliono insight sul proprio gusto
- Utenti che cercano nuove scoperte basate sui propri pattern

## 3. Architettura Tecnica
- **Backend**: FastAPI (async) + SQLAlchemy async + SQLite
- **Frontend**: React 18 + Vite + Tailwind CSS + Recharts
- **Auth**: OAuth2 PKCE con Spotify
- **Deploy**: locale (dev), predisposto per Docker

## 4. Limitazioni API Spotify
- **Deprecati** (non usati): Audio Features, Audio Analysis, Artist genres/popularity/followers, Track popularity/preview_url
- **Time ranges fissi**: short_term (~4 settimane), medium_term (~6 mesi), long_term (storico completo)
- **Recently played**: max 50 items (hard limit API)
- **Workaround storico**: playlist "Your Top Songs 20XX" per dati multi-anno

## 5. Funzionalità

### 5.1 Dashboard (`/dashboard`)
- KPI: brani analizzati, energia media, genere top, mood score
- Top 50 brani con play overlay e mini barre energia/valence
- Radar audio features, trend timeline, genre treemap
- Export Claude AI per analisi personalizzata

### 5.2 Evoluzione del Gusto (`/evolution`)
- Confronto artisti/brani tra 3 periodi temporali
- Classificazione: rising, loyal, falling
- Metriche: loyalty score, turnover rate
- Storico annuale via playlist "Your Top Songs"

### 5.3 Pattern Temporali (`/temporal`)
- Heatmap 7x24 stile Spotify Wrapped (gradiente multi-colore)
- Streak di ascolto stile Duolingo (fiamma animata, progress ring, milestone)
- Statistiche sessioni con gamification
- Peak hours e pattern weekday/weekend

### 5.4 Ecosistema Artisti (`/artists`)
- Grafo force-directed SVG relazioni artisti
- Cluster detection (BFS connected components)
- Bridge artists tra cluster
- Metriche diversita musicale

### 5.5 Analisi Playlist (`/playlist-analytics`)
- Statistiche per-playlist: concentrazione, freshness, staleness
- Overlap matrix (Jaccard index)
- Size distribution histogram

### 5.6 Confronto Playlist (`/compare`)
- Confronto side-by-side tra playlist selezionate
- Metriche comparative

### 5.7 Scopri (`/discovery`)
- Raccomandazioni personalizzate
- Suggerimenti basati su profilo

## 6. Stack Spotify API (Non Deprecato)
- `GET /me/top/artists` — top artists (3 time ranges, max 50)
- `GET /me/top/tracks` — top tracks (3 time ranges, max 50)
- `GET /me/player/recently-played` — ultimi 50 ascolti con timestamp
- `GET /me/playlists` — playlist utente (paginato)
- `GET /playlists/{id}/tracks` — tracks di una playlist
- `GET /artists/{id}/related-artists` — artisti correlati
- `GET /recommendations` — raccomandazioni personalizzate
- `GET /search` — ricerca contenuti

## 7. Design System
- Background: #121212 | Surface: #181818 | Hover: #282828
- Text: #FFFFFF / #b3b3b3 / #6a6a6a
- Accent: #6366f1 (indigo) | Brand: #1DB954 (Spotify green)
- Font: Space Grotesk (display) + Inter (body)
- Sidebar: 240px, always visible desktop, collapsible mobile

## 8. Decisioni Architetturali
- Nessuna dipendenza esterna per grafici complessi (force-directed = SVG puro)
- asyncio.Semaphore per rate limiting API calls parallele
- Graceful degradation: se un dato non e disponibile, la UI mostra stato vuoto
- Export Claude: markdown con dati strutturati + prompt istruzioni
