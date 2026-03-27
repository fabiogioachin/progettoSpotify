# Wrap — Product Requirements Document

## 1. Visione
Dashboard di analytics personale che analizza i dati di ascolto Spotify dell'utente, visualizzando pattern, evoluzione del gusto e ecosistema musicale con una UI dark-theme ispirata a Spotify.

## 2. Utenti Target
- Ascoltatori Spotify curiosi del proprio profilo musicale
- Music enthusiast che vogliono insight sul proprio gusto
- Utenti che cercano nuove scoperte basate sui propri pattern
- **Beta**: 5-20 amici, accesso tramite invite link
- **Vincolo**: max 5 utenti in dev mode Spotify (Premium only). Extended Quota rimuoverà il limite.

## 3. Architettura Tecnica
- **Backend**: FastAPI (async) + SQLAlchemy async + PostgreSQL 16 + Redis 7
- **Frontend**: React 18 + Vite + Tailwind CSS + Recharts + framer-motion (PWA installabile)
- **Auth**: OAuth2 PKCE con state HMAC-signed, session cookie (itsdangerous), token Fernet-encrypted. Invite-gated registration.
- **ML/Analytics**: scikit-learn (PCA, DBSCAN, Isolation Forest, cosine similarity), NetworkX (Louvain, PageRank, betweenness)
- **Audio**: librosa per analisi on-demand da preview MP3 (zero chiamate API Spotify)
- **Deploy**: Docker Compose (PostgreSQL, Redis, backend: uvicorn :8001, frontend: Vite :5173)
- **Migrations**: Alembic per schema PostgreSQL
- **API Versioning**: tutti gli endpoint sotto `/api/v1/`, redirect 308 per backward compat

## 4. Limitazioni API Spotify (Dev Mode Feb 2026+)

### Endpoint rimossi (403 permanente — non usare)
- Audio Features (`GET /audio-features`)
- Recommendations (`GET /recommendations`)
- Related Artists (`GET /artists/{id}/related-artists`)
- Artist Top Tracks (`GET /artists/{id}/top-tracks`)
- Batch endpoints (`GET /artists?ids=`, `GET /tracks?ids=`, `GET /albums?ids=`)

### Cambiamenti breaking
- `/playlists/{id}/tracks` → **`/playlists/{id}/items`** (vecchio ritorna 403)
- `GET /playlists/{id}` non include più `tracks` nella risposta
- Campo dati: `item.get("item") or item.get("track")` per backwards compat
- `GET /me/top/tracks` **non restituisce `popularity`** nel track object in dev mode
- `/playlists/{id}/items` ha `limit` max 50, non 100

### Sempre disponibili
- Artist genres, followers, images
- Track metadata (name, album, artists, duration_ms, preview_url)
- User profile (`GET /me`)
- Top Artists/Tracks (3 time ranges, max 50 per range)
- Recently Played (max 50 items — hard limit)
- Playlists + playlist items (paginato, max 50 per pagina)
- Individual track/artist (`GET /tracks/{id}`, `GET /artists/{id}`)

### Rate Limiting
- **Rolling window 30 secondi** (non "X calls al minuto")
- Limite esatto non pubblicato — community reports ~30-50 calls/30s
- 429 con `Retry-After` — valori estremi in dev mode (fino a 75000s+)
- **Budget app**: sliding window throttle 25 calls/30s + global semaphore(3) + cooldown globale su 429

### Workaround implementati
- **Accumulo storico**: modello `RecentPlay` in DB — sync ogni 60 min via APScheduler + salvataggio ad ogni visita
- **Snapshot giornalieri**: modello `UserSnapshot` salva top_artists/top_tracks JSON 1x/giorno
- **Aggregati**: `DailyListeningStats` computati alle 02:00 — minuti e ascolti per giorno
- **Popularity**: non disponibile in dev mode (non restituita da API). Cache DB `TrackPopularity` per eventuale enrichment futuro. Nessuna chiamata API inline per popolarità — le feature dipendenti sono nascoste quando i dati non sono disponibili
- **Generi artista**: `genre_cache.py` — DB `artist_genres` (7d TTL, cross-user) → Redis 1h → Spotify API on miss. Nessun cap artificiale — la cache limita naturalmente le chiamate API
- **Audio features**: librosa su preview MP3 (CDN, non API Spotify) — analisi on-demand

## 5. Funzionalità

### 5.1 Dashboard (`/dashboard`)
- **KPI**: brani analizzati, streak di ascolto, genere top (con %), artisti unici
- **Tempo di Ascolto**: area chart minuti/giorno con selettore temporale (7gg / 30gg / 3M / Tutto). Dati da `DailyListeningStats` pre-aggregati o fallback da `RecentPlay`
- **Trend features**: se audio features disponibili (da librosa), mostra trend 3 periodi. Altrimenti mostra Tempo di Ascolto
- **Audio Radar**: radar chart 7 feature audio (da cache DB o analisi librosa on-demand con progress bar)
- **Top 50 brani**: lista scrollabile con TrackCard
- **Genre Treemap**: visualizzazione generi dominanti
- **Export Claude AI**: prompt strutturato con dati per analisi personalizzata

### 5.2 Evoluzione del Gusto (`/evolution`)
- Confronto artisti/brani tra 3 periodi temporali
- Classificazione: rising, loyal, falling
- Metriche: loyalty score, turnover rate
- Storico annuale via playlist "Your Top Songs"

### 5.3 Pattern Temporali (`/temporal`)
- **Selettore temporale**: 7gg / 30gg / 3M / Tutto (filtra heatmap, sessioni, statistiche)
- Heatmap 7×24 (gradiente multi-colore)
- Streak di ascolto stile Duolingo (fiamma animata, progress ring)
- Statistiche sessioni (media, massima, tracks per sessione)
- Peak hours e pattern weekday/weekend
- Top 5 brani più ascoltati (da storico accumulato)
- Minuti di ascolto giornalieri (da DailyListeningStats o fallback in-memory)
- Indicatore accumulo dati: "X ascolti accumulati" vs "solo API"

### 5.4 Ecosistema Artisti (`/artists`)
- **Grafo force-directed SVG** relazioni artisti (3 time ranges merged, ~45 artisti unici)
- **Edges**: similarità generi (fuzzy matching, soglia 0.15) + fallback popolarità per artisti senza generi
- **Cluster detection**: Louvain communities (NetworkX) con resolution adattiva
- **Cluster naming**: TF-IDF-like scoring sul genere più distintivo. Fallback: "Cerchia di {artista più popolare}"
- **Metriche nodo**: PageRank, betweenness centrality, connessioni, popolarità, followers
- **Bridge artists**: top 5 per betweenness centrality (connettori tra cluster)
- **Ranking intra-cluster**: score composito (40% PageRank + 30% popularity + 30% genre diversity)
- Genre cloud: top 10 generi dominanti

### 5.5 Analisi Playlist (`/playlist-analytics`)
- Statistiche per-playlist: diversità artisti (cappata a 100%), freshness (anno medio release), staleness (giorni dall'ultimo aggiornamento)
- Track count: fetch reale via `/items?limit=1` per playlist con `total=0` in dev mode
- Overlap matrix (Jaccard index) tra top 20 playlist
- Size distribution histogram (bucket: vuote, 1-10, 11-30, ..., 200+)

### 5.6 Confronto Playlist (`/compare`)
- Confronto side-by-side 2-4 playlist
- Track count: usa `total` dall'API (include local files), nessun cap (gestito dal budget system)
- Popularity stats, top tracks, genre distribution
- Audio features (da cache DB, rendering condizionale)
- Dedup globale artisti per generi via `genre_cache` (DB 7d TTL, nessun cap)

### 5.7 Discovery (`/discovery`)
- **Distribuzione generi** (treemap) — sempre disponibile
- **Distribuzione popolarità**: istogramma — nascosto quando popularity non disponibile (tutti i valori a 0)
- **MoodScatter**: scatter plot energy×valence — visibile quando audio features disponibili (da librosa)
- **Outliers/Hidden Gems**: 3 livelli di fallback:
  1. Isolation Forest (sklearn) — se ≥5 tracce con features
  2. Distanza euclidea dal centroide — se features disponibili
  3. Popolarità sotto media — fallback finale
  - Sezione nascosta quando vuota
- **Scoperte Recenti**: brani in short_term assenti da medium_term, con badge "Nuovo artista"
- **Centroid audio**: radar del profilo medio (calcolato da features disponibili)

### 5.8 Profilo (`/profile`)
- TasteMap: PCA 2D (scikit-learn) degli artisti top — visualizzazione spaziale del gusto
- Profilo audio aggregato
- Evoluzione gusto sintetica

### 5.9 Wrapped Personalizzato (`/wrapped`)
- Slide-based presentation del profilo musicale
- Taste evolution (3 periodi)
- Temporal patterns
- Artist network
- Range temporale selezionabile

### 5.10 Social (`/friends`)
- Amicizie con inviti (codice univoco)
- Taste compatibility scoring
- Confronto profili musicali

## 6. Stack Spotify API (Usato)

| Endpoint | Uso | Cache | Budget |
|----------|-----|-------|--------|
| `GET /me` | Profilo utente | 5 min | 1 |
| `GET /me/top/tracks` | Top brani (3 ranges) | 5 min | 1-3 |
| `GET /me/top/artists` | Top artisti (3 ranges) | 5 min | 1-3 |
| `GET /me/player/recently-played` | Ultimi 50 ascolti | 2 min | 1 |
| `GET /me/playlists` | Lista playlist | 5 min | 1 |
| `GET /playlists/{id}/items` | Tracks playlist | 5 min | 1-N |
| `GET /playlists/{id}` | Metadata playlist | none | 1 |
| `GET /artists/{id}` | Generi/popolarità artista | **1h cross-user** | 0-20 |
| `GET /tracks/{id}` | Dettaglio brano | 5 min | 0-N |

### Budget per pagina (worst-case, cache fredda)
- **Dashboard**: ~7 calls (top tracks ×3, top artists ×3, recently played)
- **Trends**: ~23 calls (top tracks ×3 + artists ×20)
- **Discovery**: ~3 calls (top tracks ×2, top artists ×1 — tutto in cache da dashboard)
- **Artist Network**: ~3 calls (top artists ×3 — in cache)
- **Wrapped**: ~11 calls
- **Playlist Compare**: ~4-194 calls (dipende dal numero e dimensione playlist)
- **Fresh user total**: ~10-25 unique calls (cache deduplicates)

## 7. Design System
- **Background**: #121212 | **Surface**: #181818 | **Hover**: #282828
- **Text**: #FFFFFF / #b3b3b3 / #8a8a8a (WCAG AA)
- **Accent**: #6366f1 (indigo) — differenzia l'app da Spotify
- **Brand**: #1DB954 (Spotify green — usato solo per badge/indicatori Spotify-specifici)
- **Font**: Space Grotesk (display) + Inter (body)
- **Sidebar**: 240px desktop, collapsible mobile con slide animation
- **UI text**: italiano. Period labels: 1M / 6M / All
- **Cluster label**: "Cerchia" (non "Cluster")
- **Sezioni vuote**: nascoste, mai "nessun dato disponibile"

### 7.1 Animazioni (framer-motion)
- Page transitions: `AnimatePresence mode="wait"` (fade + slide)
- KPI cards: `whileInView` scroll-driven fade-in
- Liste/griglie: `StaggerContainer` + `StaggerItem` (40ms stagger)
- Sidebar mobile: `motion.aside` slide in/out
- Loading states: skeleton loaders che rispecchiano la forma del componente
- Audio analysis: progress bar con conteggio brani analizzati

## 8. Decisioni Architetturali

### 8.1 Rate Limiting (3 livelli)
1. **API middleware**: 120 req/min per IP (protezione frontend abuse)
2. **Sliding window throttle**: 25 calls/30s con lock atomico — preventivo, evita di colpire Spotify
3. **Global cooldown**: attivato su ogni 429 — tutte le richieste pending falliscono immediatamente

### 8.2 Cache Architecture (4 tier)
- `_cache_5m` (TTL 300s): user-scoped data (top tracks, playlists, etc.)
- `_cache_2m` (TTL 120s): recently played
- `_artist_cache_1h` (TTL 3600s): cross-user artist data (no user_id nella key)
- `artist_genres` DB table (TTL 7d): generi per artista, cross-user, persistente. Via `genre_cache.py`
- **Regola**: sempre `limit=50` per top tracks/artists. Slice in-memory se servono meno items

### 8.3 Popularity
- Spotify dev mode non restituisce `popularity` in `GET /me/top/tracks`
- Enrichment via `GET /tracks/{id}` **non è sostenibile** nel budget (50 chiamate per page load esauriscono il window)
- Approccio: `read_popularity_cache()` legge solo dal DB (zero API calls). Le feature dipendenti da popularity sono nascoste quando i dati non sono disponibili
- Cache DB: tabella `TrackPopularity` con TTL 90 giorni (cleanup mensile)

### 8.4 Resilienza e Degradazione Graduale
- **SpotifyAuthError propagation**: ogni `except Exception` è preceduto da `except SpotifyAuthError: raise`
- **Error handling centralizzato**: 3 global exception handler in `main.py` (401, 429, 502)
- **Non-blocking snapshots**: scritture DB non critiche in try/except con warning
- **`_safe_fetch` per gather**: fallimenti parziali → dati vuoti, non crash
- **Rendering condizionale**: flag `has_audio_features`, `recommendations_source` → frontend mostra alternative
- **Nessun dato finto**: default 0/null/vuoto, mai valori plausibili

### 8.5 Background Jobs (APScheduler)
| Job | Frequenza | Calls/user | Descrizione |
|-----|-----------|------------|-------------|
| `sync_recent_plays` | Ogni 60 min | 1 + 0-N genre cache | Accumula ascolti + popola genre cache per artisti nuovi |
| `save_daily_snapshot` | 1x/giorno (primo login) | 2 | Snapshot top artists + top tracks |
| `compute_daily_aggregates` | 02:00 daily | 0 (DB only) | Statistiche giornaliere per charts |
| `cleanup_expired_data` | 1x/mese (1° del mese) | 0 (DB only) | Prune snapshots >365d, popularity >90d |

### 8.6 Audio Analysis (On-Demand)
- `POST /api/analyze-tracks`: frontend invia track objects nel body (no re-fetch API)
- Backend scarica preview MP3 da CDN Spotify (non conta nel rate limit API)
- librosa estrae: energy, danceability, valence, acousticness, instrumentalness, speechiness, liveness, tempo
- Risultati in cache DB (`AudioFeatures` table)
- Frontend poll asincrono con progress bar

### 8.7 Dati Storici
- **RecentPlay**: accumulo progressivo ascolti (supera il limite API di 50)
- **UserSnapshot**: top artists/tracks JSON giornaliero → confronti temporali arbitrari
- **DailyListeningStats**: minuti e ascolti aggregati per giorno → charts "Tempo di Ascolto"
- Granularità temporale arbitraria filtrando per date nel DB

### 8.8 Privacy / GDPR
- `DELETE /api/v1/me/data`: cancellazione completa account e dati utente (hard delete)
- `GET /api/v1/me/data/export`: esportazione dati in JSON
- Pagina privacy nel frontend con spiegazione raccolta dati, conservazione, diritti
- **Data retention policy**: plays e stats = forever, snapshots = 1 anno, popularity cache = 90 giorni

### 8.9 Admin Dashboard
- Pagina `/admin` protetta (solo `is_admin`)
- Gestione utenti: lista, sospensione (revoca token), force-sync
- Gestione inviti: generazione codici, monitoraggio utilizzo
- Monitoraggio: utilizzo API per utente, stato background jobs

### 8.10 Onboarding
- Modal 3 step al primo login: benvenuto → come funziona → placeholder dati
- Flag `User.onboarding_completed` server-side — mostrato solo una volta
- Checkbox "Non mostrare più" salva in `localStorage('wrap_onboarding_dismissed')` — dismissione per-device, indipendente dal flag server-side
- Dopo onboarding: i dati arrivano gradualmente nelle ore successive

### 8.11 User Tiers
- `User.tier`: free / premium / admin
- Rate limit per utente: free = 30 req/min, premium = 60 req/min, admin = illimitato
- Preparazione per monetizzazione futura (tutti "free" in beta)

### 8.12 Observability
- Structured JSON logging in produzione (python-json-logger)
- Request context: `request_id` (UUID) + `user_id` in ogni log line via contextvars
- Health endpoints: `/health` (load balancer) + `/health/detailed` (admin diagnostics)
- Per-user rate limit via Redis sorted set (sliding 1-min window)
