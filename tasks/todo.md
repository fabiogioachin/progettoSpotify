# Spotify Listening Intelligence — Task List

## Bug Aperti

- [ ] **Confronto playlist** — dati incompleti:
  - [ ] Numero di brani presenti in ogni playlist assente prima del confronto
  - [ ] Popularity media = 0: track objects da `/items` senza campo `popularity` → enrichment individuale con `GET /tracks/{id}`
  - [ ] Genere = "—": conseguenza del fix popularity + verifica artist genre cap
- [ ] **Dashboard**: popolarità media 0/100 non coerente, genere top nullo (genre cap alzato da 15 a 20)
- [ ] **Evoluzione del Gusto**: controllare verità dati dei labels Fedeltà, Turnover, Artisti Fedeli, Tracce Persistenti, Distribuzione Artisti per Periodo
- [ ] **Ecosistema Artisti**: controllare verità dati dei labels Artisti nel Grafo, Connessioni, Cerchie, Artisti Top

## Prossime task (priorità)

1. **Bug fix dati** — i bug aperti sopra producono dati visivamente sbagliati nelle pagine esistenti
2. **Hardening UI profilo** — colori hardcoded in ObscurityGauge/DecadeChart, Escape key su ShareCardRenderer, ReceiptCard orfano
3. **Tier 2** — Social Layer (richiede Tier 1 ✅)

---

## Completato di recente

### Tier 1 — Foundation (2026-03-14)
- `DailyListeningStats` + `UserProfileMetrics` models, `artist_spotify_id` su RecentPlay
- `profile_metrics.py`: obscurity, genre diversity, artist loyalty, listening consistency, decade distribution
- `personality.py`: 4 archetipi musicali (Esploratore, Fedelissimo, Mainstream Maven, Cercatore di Nicchia)
- `GET /api/profile` router + job `compute_daily_aggregates` (02:00 daily)
- `ProfilePage.jsx` con ObscurityGauge, GenreDNA, DecadeChart, PersonalityBadge, LifetimeStats
- `ShareCardRenderer.jsx` + `ProfileShareCard.jsx` + `ReceiptCard.jsx` (html2canvas, Web Share API)
- Route `/profile` + voce "Profilo" in Sidebar
- cachetools TTL su SpotifyClient (5m/2m/10m per metodo) + `get_me()` cached

### Hardening post-Tier 1 (2026-03-14)
- fix: `sync_recent_plays` — early `break` su `RateLimitError` (API-5)
- fix: `Semaphore(2)` su 3 chiamate parallele in `profile_metrics.py` (API-2)
- fix: null guard su `canvas.toBlob()` in ShareCardRenderer (UI-1)
- fix: colori hardcoded in GenreDNA → `GRID_COLOR` + CSS vars `var(--accent)`, `var(--text-secondary)`

### Skill aggiornate (2026-03-14)
- Nuova `spotify-api-budget`: rolling 30s window, budget per endpoint, defensive patterns (Semaphore, retry cap, global cooldown, background early break)
- `fastapi-spotify-patterns`: aggiunto router completo (4 except), retry_with_backoff obbligatorio, _safe_fetch, budget API, background tasks
- `spotify-api-audit`: aggiunto dev mode checklist, Semaphore(2), dedup artisti, deprecated API cleanup

### Audio Features Recovery via librosa (2026-03-13)
- Backend: `audio_feature_extractor.py` (librosa in `asyncio.to_thread`), `rapidapi_bridge.py` (fallback opzionale), `routers/analysis.py` (POST start + GET polling)
- Frontend: `useAudioAnalysis.js` (POST-then-poll hook), integrato in DashboardPage e DiscoveryPage
- Discovery: related artists recommendations via `get_related_artists` + `get_artist_top_tracks`

### Fix precedenti (2026-03-12)
- Discovery: hidden gems sorting corretto (filtro pop < avg, ordine crescente, label "Pop. X")
- Playlist compare: endpoint migrato (`/items`), rate limit fix (cap `max_retry_after=30s`, dedup artisti, Semaphore(2)), grid "Le tue / Seguite"
- Deprecated API cleanup: `get_or_fetch_features` convertito a pure cache lookup, rimosso `get_audio_features()` da SpotifyClient

---

## Feature Roadmap

### Tier 2 — Social Layer (multi-utente stesso deploy)

#### 2A. Infrastruttura Amici
- [ ] feat: modelli `Friendship` + `FriendInviteLink` in `models/social.py`
- [ ] feat: router `social.py` — invite, accept, list, delete, compare
- [ ] feat: servizio `social.py` — compute_compatibility (Jaccard generi, overlap artisti, similarita' popularity)

#### 2B. Compatibilita' e Confronto
- [ ] feat: `CompatibilityMeter.jsx` + `TasteComparison.jsx` — "Vi unisce/Vi distingue"

#### 2C. Classifiche tra Amici
- [ ] feat: `Leaderboard.jsx` — rankings obscurity, plays, streak, nuovi artisti

#### 2D. Pagina Amici
- [ ] feat: `FriendsPage.jsx` — lista amici, genera invito, confronto, classifiche
- [ ] feat: aggiornare Sidebar + App.jsx per route `/friends`

### Tier 3 — Analytics Avanzati & Engagement

#### 3A. Milestones & Achievements
- [ ] feat: modello `Achievement` + servizio `achievements.py` (streak, esploratore generi, fan fedele, night owl, cacciatore gemme, maratoneta)
- [ ] feat: `AchievementGrid.jsx` integrato in ProfilePage + notifica toast

#### 3B. Digest Settimanale/Mensile
- [ ] feat: servizio `digest.py` — confronto settimana/mese corrente vs precedente
- [ ] feat: `DigestCard.jsx` in cima alla Dashboard

#### 3C. Wrapped Personalizzato
- [ ] feat: endpoint `GET /api/wrapped/custom?start_date&end_date` + servizio `custom_wrapped.py`
- [ ] feat: `DateRangePicker.jsx` in WrappedPage

#### 3D. Mood Timeline
- [ ] feat: servizio `mood_proxy.py` — genre-mood mapping statico (~100 generi), popularity trajectory
- [ ] feat: `MoodTimeline.jsx` (area chart ultimi 30/90gg) in TemporalPage o ProfilePage
