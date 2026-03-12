# Spotify Listening Intelligence — Task List

## Bug Aperti
- [ ] Confronto playlist: endpoint migrato (`/items`, field `"item"`). Rate limit fix: cap `max_retry_after=30s`, global cooldown in SpotifyClient, dedup artisti cross-playlist (da ~70 a ~30 API calls per 4 playlist), Semaphore(2), cap 20 artisti globale. Aggiunto `retry_with_backoff` a `historical_tops.py` e `background_tasks.py`. **Da verificare live.**
- [ ] Dashboard: popolarità media 0/100 non coerente, genere top nullo
- [ ] Discovery: distribuzione popolarità e hidden gems da rivedere
- [ ] Evoluzione del Gusto: controllare verità dati del labels Fedeltà, Turnover, Artisti Fedeli, Tracce Persistenti, Distribuzione Artisti per Periodo
- [ ] Ecosistema Artisti: Controllare Verità dati del labels Artisti nel Grafo, Connessioni, Cerchie, Artisti Top

## CI/CD
- [x] GitHub Actions workflow: lint (eslint + ruff) + build check su ogni PR
- [x] Docker build test in CI

## Suggestion (Health Report) — ✅ Tutte risolte

### Backend — ✅
- [x] `get_recommendations` chiama endpoint deprecato, spreca una API call (S-2)
- [x] Default RPM=60 in `rate_limiter.py` ma app configura 120 — default fuorviante (S-4)
- [x] `compute_trends` esegue 3 profili sequenzialmente — parallelizzabile con `asyncio.gather` (S-5)
- [x] `get_or_fetch_features:285` — `SpotifyAuthError` inghiottito da `except Exception` (trovato in verifica)

### Frontend — ✅
- [x] `KPICard.jsx`: `value % 1` applicato a stringhe — innocuo ma poco chiaro (S-1)
- [x] `ArtistNetwork.jsx`: simulazione si riavvia su nuovi ref array anche se dati invariati (S-2)
- [x] `ArtistNetwork.jsx`: niente keyboard focus/aria-label su nodi SVG interattivi (S-3)
- [x] `ListeningHeatmap.jsx` + `StreakDisplay.jsx`: inline `<style>` — spostare in globals.css (S-4/S-5)
- [x] `DashboardPage.jsx`: loading combinato blocca sulla richiesta più lenta — progressive rendering possibile (S-6)
- [x] `PlaylistStatCard.jsx` + `SessionStats.jsx` + `StreakDisplay.jsx`: CSS `animate-slide-up` invece di framer-motion (S-7/S-8)
- [x] `DashboardPage.jsx`: indentazione inconsistente (S-9)
- [x] `ClaudeExportPanel.jsx`: naming `border-border-hover` confuso (S-10)
- [x] `SlideOutro.jsx`: html2canvas canvas si accumulano su click ripetuti (S-11)

## Deferred — ✅ Tutte risolte

### Securi limiter: `X-Forwarded-For` + `ProxyHeadersMiddleware` (attivo conty Hardening — ✅
- [x] Rate `BEHIND_PROXY=true`)
- [x] Rate limiter: cap `MAX_TRACKED_IPS=10_000` con eviction oldest entries
- [x] Spotify ID validation: regex `^[a-zA-Z0-9]{22}$` su `get_artist`/`get_related_artists`
- [x] Error messages: già gestiti — tutti i router usano messaggi italiani user-friendly

### Code Simplification — ✅
- [x] `audio_analyzer.py`: dedup campi `save_snapshot` in dizionario condiviso `fields`
- [x] `discovery.py`: estratto helper `_album_image(track)`
- [x] `SessionStats.jsx`: sostituito `mounted` state + useEffect con framer-motion `initial`/`animate`

---

## Feature Roadmap

### Tier 1 — Foundation (Database & Profilo)

#### 1A. DB Accumulation Layer
- [ ] feat: nuovo modello `DailyListeningStats` (user_id, date, total_plays, unique_tracks/artists, top_genre, avg_popularity, new_artists/tracks_count)
- [ ] feat: nuovo modello `UserProfileMetrics` (obscurity_score, genre_diversity_index, artist_loyalty_score, listening_consistency, lifetime stats, top_genres_json, decade_distribution_json)
- [ ] feat: arricchire `RecentPlay` con colonna `artist_spotify_id` (nullable)
- [ ] feat: servizio `profile_metrics.py` (compute_daily_stats, compute_profile_metrics, compute_obscurity_score, compute_genre_diversity)
- [ ] feat: nuovo job `compute_daily_aggregates` in background_tasks.py

#### 1B. Pagina Profilo Personale
- [ ] feat: router `profile.py` — `GET /api/profile`
- [ ] feat: servizio `personality.py` — archetipo musicale (Esploratore, Fedelissimo, Mainstream Maven, Cercatore di Nicchia)
- [ ] feat: `ProfilePage.jsx` con ObscurityGauge, GenreDNA (radar), DecadeChart, PersonalityBadge, lifetime stats
- [ ] feat: aggiornare Sidebar + App.jsx per route `/profile`

#### 1C. Card Condivisibili
- [ ] feat: `ShareCardRenderer.jsx` + `ReceiptCard.jsx` + `ProfileShareCard.jsx` (html2canvas, Web Share API)

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
