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
- **Deploy**: Docker Compose operativo (backend: uvicorn, frontend: nginx porta 5173)

## 4. Limitazioni API Spotify
- **Deprecati** (non usati): Audio Features, Audio Analysis, Recommendations
- **Sempre disponibili**: Artist genres/popularity/followers, Track popularity/preview_url, Top Artists/Tracks, Recently Played, Playlists, Related Artists
- **Time ranges fissi**: short_term (~4 settimane), medium_term (~6 mesi), long_term (storico completo)
- **Nessuna granularità custom via API**: Spotify non espone time ranges intermedi (es. 2 settimane, 3 mesi). L'unico modo è accumulare dati localmente e computare range personalizzati
- **Recently played**: max 50 items (hard limit API)
- **Workaround accumulo**: modello `RecentPlay` in DB — sync automatico ogni 60 minuti via APScheduler + salvataggio ad ogni visita pagina Temporal. Lo storico cresce nel tempo
- **Workaround range custom**: con sufficiente storico accumulato in `RecentPlay`, si possono computare range arbitrari (ultimi 7 giorni, 2 settimane, 3 mesi) filtrando per `played_at` nel DB anziché affidarsi ai time ranges API
- **Workaround storico**: playlist "Your Top Songs 20XX" per dati multi-anno
- **Workaround snapshot giornalieri**: modello `UserSnapshot` salva top_artists/top_tracks JSON una volta al giorno → confronto settimana-su-settimana e mese-su-mese senza dipendere dai time ranges API

## 5. Funzionalità

### 5.1 Dashboard (`/dashboard`)
- KPI: brani analizzati, popolarità media, artisti unici, artista top
- Top 50 brani con play overlay e mini barre (quando features disponibili)
- Radar audio features (con rilevamento all-zero → messaggio fallback), trend timeline (popularity fallback se features assenti), genre treemap
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
- Top 5 brani più ascoltati (da storico accumulato)
- Accumulo DB progressivo: ogni visita salva nuovi ascolti, indicatore "ascolti accumulati" vs "solo API"

### 5.4 Ecosistema Artisti (`/artists`)
- Grafo force-directed SVG relazioni artisti
- Cluster detection (BFS connected components)
- Bridge artists tra cluster (con generi e popolarità)
- Metriche diversità musicale
- Nodi arricchiti: generi, popolarità, followers, numero connessioni (tooltip dettagliato)
- Genre cloud: top 10 generi dominanti nell'ecosistema

### 5.5 Analisi Playlist (`/playlist-analytics`)
- Statistiche per-playlist: concentrazione, freshness, staleness
- Overlap matrix (Jaccard index)
- Size distribution histogram

### 5.6 Confronto Playlist (`/compare`)
- Confronto side-by-side tra playlist selezionate
- Metriche comparative (audio features se disponibili, altrimenti messaggio informativo)
- Rendering condizionale: mostra confronto features solo quando i dati audio sono disponibili

### 5.7 Scopri (`/discovery`)
- Distribuzione generi (treemap) — sempre disponibile via artist genres
- Distribuzione popolarità (istogramma a barre) — fallback quando MoodScatter non ha features
- Hidden gems: brani meno popolari tra i preferiti (fallback outlier basato su popolarità anziché distanza audio)
- Raccomandazioni: API Spotify se disponibile, altrimenti "Scoperte Recenti" (brani in short_term non presenti in medium_term)
- Flag trasparenza `recommendations_source`: il frontend etichetta chiaramente la sorgente dei suggerimenti

## 6. Stack Spotify API (Non Deprecato)
- `GET /me/top/artists` — top artists (3 time ranges, max 50)
- `GET /me/top/tracks` — top tracks (3 time ranges, max 50)
- `GET /me/player/recently-played` — ultimi 50 ascolti con timestamp
- `GET /me/playlists` — playlist utente (paginato)
- `GET /playlists/{id}/tracks` — tracks di una playlist
- `GET /artists/{id}/related-artists` — artisti correlati
- `GET /search` — ricerca contenuti

### API Deprecate (con fallback implementato)
- `GET /audio-features` → fallback: popolarità, generi artista, confronti tra periodi
- `GET /recommendations` → fallback: scoperte recenti (short_term − medium_term)

## 7. Design System
- Background: #121212 | Surface: #181818 | Hover: #282828
- Text: #FFFFFF / #b3b3b3 / #8a8a8a (WCAG AA)
- Accent: #6366f1 (indigo) | Brand: #1DB954 (Spotify green)
- Font: Space Grotesk (display) + Inter (body)
- Sidebar: 240px, always visible desktop, collapsible mobile

### 7.1 Animazioni e Transizioni Moderne
- **Scroll-driven animations**: fade-in e slide-up per KPI cards e sezioni al scroll (CSS `@scroll-timeline` o Framer Motion `useInView`)
- **View Transitions API**: transizioni animate tra route (fade/slide) per navigazione fluida tra pagine
- **Skeleton loaders**: placeholder che rispecchiano la forma del componente finale (card, lista, grafico) al posto degli spinner generici
- **Staggered list animations**: animazioni d'ingresso sfalsate per liste e griglie (TopTracks, ArtistCards) con Framer Motion `staggerChildren`

## 8. Decisioni Architetturali
- Nessuna dipendenza esterna per grafici complessi (force-directed = SVG puro)
- asyncio.Semaphore per rate limiting API calls parallele
- Export Claude: markdown con dati strutturati + prompt istruzioni
- Deploy Docker Compose: backend (uvicorn) + frontend (nginx su porta 5173), volume mount per live reload backend

### 8.1 Resilienza e Degradazione Graduale
- **SpotifyAuthError propagation**: ogni router ri-lancia `SpotifyAuthError` prima di `except Exception` generico → l'utente viene reindirizzato al login anziché vedere dati stalli
- **Non-blocking snapshots**: scritture DB non critiche wrappate in try/except con logger.warning → l'endpoint risponde anche se il salvataggio snapshot fallisce
- **_safe_fetch per gather**: `taste_evolution` wrappa ogni chiamata API individualmente → fallimenti parziali restituiscono dati vuoti anziché crashare l'intera pagina
- **InvalidToken handling**: `spotify_client` cattura Fernet InvalidToken e rilancia SpotifyAuthError → 401
- **Rendering condizionale frontend**: flag `has_audio_features` e `recommendations_source` dal backend → il frontend mostra alternative appropriate (popolarità, generi) quando le API deprecate falliscono
- **AudioRadar all-zero detection**: rileva features con tutti valori a 0 → mostra messaggio "dati non disponibili" anziché radar piatto
- **Nessun dato finto**: tutti i valori default sono 0/null/vuoto, mai valori plausibili che potrebbero fuorviare l'utente

### 8.2 Architettura Dati Storici
- **UserSnapshot giornaliero**: modello `UserSnapshot` salva una volta al giorno (al primo login) i top_artists e top_tracks come JSON serializzato + timestamp
- **Campi**: `id`, `user_id`, `captured_at` (date, unico per utente), `top_artists_json`, `top_tracks_json`, `recent_plays_count`
- **Confronti temporali**: con snapshot giornalieri si possono calcolare diff settimana-su-settimana e mese-su-mese senza dipendere dai 3 time ranges fissi di Spotify
- **Endpoint**: `GET /api/snapshots/diff?period=week` restituisce delta tra snapshot (artisti saliti/scesi, nuovi brani, brani usciti dalla top)
- **Vantaggio**: dati owned dall'utente, non soggetti a deprecazione API, granularità temporale arbitraria
