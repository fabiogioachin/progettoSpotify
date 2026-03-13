# Spotify Listening Intelligence — Task List

## Bug Aperti

- [ ] Confronto playlist (piano: `lively-spinning-giraffe.md`):
  - [x] Endpoint migrato (`/items`, field `"item"`)
  - [x] Rate limit fix: cap `max_retry_after=30s`, dedup artisti cross-playlist (da ~70 a ~30 API calls), Semaphore(2), cap 20 artisti globale
  - [x] Aggiunto `retry_with_backoff` a `historical_tops.py` e `background_tasks.py`
  - [x] Rimossa chiamata deprecata `get_audio_features()` — `get_or_fetch_features()` ora pure cache lookup (piano: `cheerful-fluttering-lecun.md`)
  - [ ] Grid pre-confronto: tutte le playlist mostrano "0 brani" (`tracks.total` non restituito da `/me/playlists` in dev mode)
  - [ ] Compare 403: playlist non di proprietà inaccessibili in dev mode → flag `accessible` + mostrare "N/D"
  - [ ] Popularity media = 0: track objects da `/items` senza campo `popularity` → enrichment individuale con `GET /tracks/{id}`
  - [ ] Genere = "—": conseguenza del fix popularity + verifica artist genre cap
  - [ ] Frontend: dividere grid in "Le tue playlist" / "Playlist seguite", tooltip per playlist inaccessibili
- [ ] Dashboard: popolarità media 0/100 non coerente, genere top nullo
- [ ] Discovery: distribuzione popolarità e hidden gems da rivedere
- [ ] Evoluzione del Gusto: controllare verità dati del labels Fedeltà, Turnover, Artisti Fedeli, Tracce Persistenti, Distribuzione Artisti per Periodo
- [ ] Ecosistema Artisti: Controllare Verità dati del labels Artisti nel Grafo, Connessioni, Cerchie, Artisti Top

## Prossima Feature — Audio Features Recovery via librosa (piano: `indexed-foraging-fog.md`)

Recupero audio features da preview MP3 (librosa) + recommendations migliorate. Sblocca: AudioRadar, MoodScatter, TrendTimeline, TrackCard E/V bars.

- [ ] `audio_feature_extractor.py` — estrazione features da `preview_url` con librosa (energy, danceability, valence, ecc.)
- [ ] `routers/analysis.py` — POST/GET polling endpoints per analisi asincrona progressiva
- [ ] `rapidapi_bridge.py` — fallback opzionale per brani senza preview (solo se `RAPIDAPI_KEY` configurato)
- [ ] `discovery.py` — recommendations migliorate con related artists + genre search
- [ ] `useAudioAnalysis.js` — hook polling frontend (POST → task_id → GET ogni 2s → partial results)
- [ ] DashboardPage + DiscoveryPage — integrazione hook, skeleton/progress durante analisi
- [ ] `requirements.txt` — aggiungere librosa, soundfile
- [ ] `main.py` — registrare analysis router

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
