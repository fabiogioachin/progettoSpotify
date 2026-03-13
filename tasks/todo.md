# Spotify Listening Intelligence — Task List

## Bug Aperti

- [ ] Confronto playlist (piano: `lively-spinning-giraffe.md`):
  - [x] Endpoint migrato (`/items`, field `"item"`)
  - [x] Rate limit fix: cap `max_retry_after=30s`, dedup artisti cross-playlist (da ~70 a ~30 API calls), Semaphore(2), cap 20 artisti globale
  - [x] Aggiunto `retry_with_backoff` a `historical_tops.py` e `background_tasks.py`
  - [x] Rimossa chiamata deprecata `get_audio_features()` — `get_or_fetch_features()` ora pure cache lookup (piano: `cheerful-fluttering-lecun.md`)
  - [x] Grid pre-confronto: "? brani" quando `tracks.total` non disponibile (fix interim, piano: `jolly-toasting-adleman.md`)
  - [x] Compare 403: playlist non di proprietà escluse dalla selezione con `is_owner` flag + grid split "Le tue playlist" / "Playlist seguite"
  - [ ] Popularity media = 0: track objects da `/items` senza campo `popularity` → enrichment individuale con `GET /tracks/{id}`
  - [ ] Genere = "—": conseguenza del fix popularity + verifica artist genre cap
  - [x] Frontend: griglia divisa in "Le tue playlist" / "Playlist seguite", tooltip per playlist inaccessibili
  - [x] Genre cap alzato da 20 a 25 artisti globali nel compare
- [ ] Dashboard: popolarità media 0/100 non coerente, genere top nullo (genre cap alzato da 15 a 20)
- [x] Discovery: hidden gems sorting corretto (filtro pop < avg, ordine crescente, label "Pop. X")
- [ ] Evoluzione del Gusto: controllare verità dati del labels Fedeltà, Turnover, Artisti Fedeli, Tracce Persistenti, Distribuzione Artisti per Periodo
- [ ] Ecosistema Artisti: Controllare Verità dati del labels Artisti nel Grafo, Connessioni, Cerchie, Artisti Top

## Completato — Audio Features Recovery via librosa (2026-03-13)

Recupero audio features da preview MP3 (librosa) + recommendations migliorate con related artists.
Sblocca: AudioRadar, MoodScatter, TrendTimeline, TrackCard E/V bars.

### Domain Analysis

| Domain | Files | Agent | Execution |
|--------|-------|-------|-----------|
| Backend: Extractor + API | `audio_feature_extractor.py`, `rapidapi_bridge.py`, `routers/analysis.py`, `main.py`, `config.py`, `requirements.txt` | backend-specialist | Sequential (Phase 1) |
| Backend: Discovery | `discovery.py` | backend-specialist | Sequential (Phase 1, after extractor) |
| Frontend: Hook + Pages | `useAudioAnalysis.js`, `DashboardPage.jsx`, `DiscoveryPage.jsx` | frontend-specialist | Sequential (Phase 2, after backend) |
| Verification | all | test-writer + code-reviewer | Sequential (Phase 3) |

### Phase 1 — Backend (backend-specialist)

#### 1A. Core extraction service
- [x] Task 1: Create `audio_feature_extractor.py`
  - File: `backend/app/services/audio_feature_extractor.py` (NEW)
  - Depends on: none
  - Details:
    - `extract_features_from_url(preview_url: str) -> dict` — download preview MP3 via httpx, load with librosa in `asyncio.to_thread()`, extract:
      - energy: RMS energy average, normalized 0-1
      - danceability: onset strength * tempo regularity, normalized 0-1
      - valence: spectral brightness + chroma major/minor mode, normalized 0-1
      - acousticness: 1 - spectral_centroid_norm, 0-1
      - instrumentalness: spectral flatness, 0-1
      - speechiness: ZCR high + short-time energy variance, 0-1
      - liveness: spectral flux variance, 0-1
      - tempo: beat_track() BPM, 60-200
    - `analyze_tracks(db, track_items: list[dict], task_id: str, results_store: dict)` — orchestrates batch analysis:
      - Checks DB cache first (existing `AudioFeatures` table via `get_or_fetch_features`)
      - For uncached tracks with `preview_url`: extract via librosa
      - For uncached tracks without `preview_url`: try RapidAPI if configured, else skip
      - Saves results to `AudioFeatures` table (same schema, same columns)
      - Updates `results_store[task_id]` progressively (total, completed, results dict)
    - Error handling: per-track try/except, never crash entire batch. Log warnings for failed tracks.
    - Must NOT block the event loop — all librosa calls in `asyncio.to_thread()`

- [x] Task 2: Create `rapidapi_bridge.py`
  - File: `backend/app/services/rapidapi_bridge.py` (NEW)
  - Depends on: none (parallel with Task 1)
  - Details:
    - `fetch_features_rapidapi(track_id: str, track_name: str, artist_name: str) -> dict | None`
    - Only called if `settings.rapidapi_key` is set (optional)
    - Uses httpx to call RapidAPI audio analysis endpoint
    - Returns normalized features dict matching our schema, or None on failure
    - Semaphore(2) for rate limiting
    - Entire module is a no-op if key not configured

- [x] Task 3: Add config + dependencies
  - Files:
    - `backend/app/config.py` — add `rapidapi_key: str = ""` to Settings
    - `backend/requirements.txt` — add `librosa==0.10.2` and `soundfile==0.12.1`
  - Depends on: none (parallel with Tasks 1-2)

#### 1B. API endpoints
- [x] Task 4: Create `routers/analysis.py`
  - File: `backend/app/routers/analysis.py` (NEW)
  - Depends on: Task 1
  - Details:
    - In-memory `_analysis_tasks: dict[str, dict]` store (task_id -> {status, total, completed, results, error})
    - `POST /api/analyze-tracks` — accepts `{"track_ids": [...], "time_range": "medium_term"}`:
      - `require_auth` dependency
      - Creates SpotifyClient, fetches track details (need `preview_url` from Spotify)
      - Generates UUID task_id
      - Launches `asyncio.create_task(analyze_tracks(db, tracks, task_id, _analysis_tasks))`
      - Returns `{"task_id": "..."}`
      - SpotifyAuthError/RateLimitError/SpotifyServerError/Exception handler chain (skill pattern)
    - `GET /api/analyze-tracks/{task_id}` — returns current state from `_analysis_tasks`:
      - `{"status": "processing|completed|error", "total": N, "completed": M, "results": {...}}`
      - No auth needed (task_id is unguessable UUID)
    - Cleanup: tasks older than 30 minutes auto-evicted (check on each GET)
    - Follow router pattern from `fastapi-spotify-patterns` skill exactly

- [x] Task 5: Register analysis router in `main.py`
  - File: `backend/app/main.py`
  - Depends on: Task 4
  - Details:
    - Add `analysis` to imports from `app.routers`
    - Add `app.include_router(analysis.router)`

#### 1C. Discovery improvements
- [x] Task 6: Add related artists recommendations to `discovery.py`
  - File: `backend/app/services/discovery.py`
  - Depends on: none (independent of extractor)
  - Details:
    - After existing step 5 (new_discoveries), add step 5b:
    - Take top 5 artists from `top_artists` → `client.get_related_artists(artist_id)` for each (via retry_with_backoff, Semaphore(2))
    - Filter out artists already in user's top_artists (by ID)
    - For each new related artist, get one top track via `client.get_artist_top_tracks(artist_id)` (already exists in SpotifyClient)
    - Merge with `new_discoveries` — related artist tracks get `is_new_artist: True`, `source: "related_artists"`
    - Update `recommendations_source` to `"related_artists"` when related artist tracks are included
    - Cap total recommendations at 20
    - Use `_safe_fetch` pattern for each `get_related_artists` call (one failure must not crash discovery)
    - Respect existing error handling: SpotifyAuthError re-raised, other errors logged and skipped

### Phase 2 — Frontend (frontend-specialist)

#### 2A. Polling hook
- [x] Task 7: Create `useAudioAnalysis.js` hook
  - File: `frontend/src/hooks/useAudioAnalysis.js` (NEW)
  - Depends on: Tasks 4-5 (backend API must exist)
  - Details:
    - `useAudioAnalysis(trackIds: string[])` — returns `{ analyzing, progress, results, error, analyze }`
    - `analyze()`: POST to `/api/analyze-tracks` with track_ids → get task_id
    - Poll `GET /api/analyze-tracks/{task_id}` every 2-3 seconds
    - Update `progress` = `{total, completed, percent}` on each poll
    - When status=completed: set `results` (features map), stop polling
    - When status=error: set `error`, stop polling
    - Cleanup: AbortController on unmount, clear interval on unmount
    - Use `api` from `lib/api.js` (same axios instance with 429 retry interceptor)
    - Do NOT use `useSpotifyData` — this is a different pattern (POST + polling vs simple GET)

#### 2B. Page integration
- [x] Task 8: Integrate analysis into `DashboardPage.jsx`
  - File: `frontend/src/pages/DashboardPage.jsx`
  - Depends on: Task 7
  - Details:
    - Import `useAudioAnalysis`
    - When `featuresData` returns empty features (no cached audio features):
      - Extract track IDs from `tracks`
      - Call `useAudioAnalysis(trackIds)` → auto-trigger `analyze()`
      - While analyzing: show progress bar/text inside AudioRadar skeleton area ("Analisi audio in corso... X/Y brani")
      - When complete: merge results into features state, AudioRadar + TrendTimeline render with real data
    - When features already cached: no change (current behavior works)
    - Progress indicator: simple text + percentage bar inside the existing skeleton card area

- [x] Task 9: Integrate analysis into `DiscoveryPage.jsx`
  - File: `frontend/src/pages/DiscoveryPage.jsx`
  - Depends on: Task 7
  - Details:
    - Import `useAudioAnalysis`
    - When `hasAudioFeatures` is false and tracks are loaded:
      - Extract track IDs from `tracks`
      - Trigger analysis
      - While analyzing: show progress in MoodScatter area (replace PopularityDistribution with progress indicator)
      - When complete: update track features → MoodScatter renders instead of PopularityDistribution
    - Update recommendations section to show `"Artisti Correlati"` label when `recommendationsSource === "related_artists"`

### Phase 3 — Verification

- [x] Task 10: Backend tests
  - Files: `backend/tests/test_audio_extractor.py`, `backend/tests/test_analysis_router.py` (NEW)
  - Agent: test-writer
  - Depends on: Tasks 1-6
  - Details:
    - Test `extract_features_from_url` with a mock MP3 (patch httpx + librosa)
    - Test `analyze_tracks` progress reporting
    - Test POST/GET polling endpoints (mock the analysis task)
    - Test RapidAPI bridge fallback (with and without key configured)
    - Test discovery related artists integration
    - Verify SpotifyAuthError propagation in analysis router

- [x] Task 11: Lint + build verification
  - Agent: test-writer
  - Depends on: Tasks 1-9
  - Details:
    - `cd backend && ruff check app/ && ruff format app/ --check`
    - `cd frontend && npm run build`
    - `cd backend && pytest`
    - Fix any errors before marking done

- [x] Task 12: Code review
  - Agent: code-reviewer
  - Depends on: Tasks 10-11
  - Details:
    - Verify SpotifyAuthError propagation in all new code paths
    - Verify asyncio.gather safety (Semaphore(2), _safe_fetch for 3+ calls)
    - Verify no blocking calls on event loop (all librosa in to_thread)
    - Verify DB writes are non-blocking where appropriate
    - Verify no deprecated API calls introduced
    - Verify retry_with_backoff on all SpotifyClient calls
    - Verify error hierarchy: SpotifyAuthError → RateLimitError → SpotifyServerError → Exception
    - Verify Italian UI text, empty section hiding, skeleton loaders

### Risks

| Risk | Mitigation |
|------|-----------|
| librosa import time is slow (~2-3s) | Import lazily inside `asyncio.to_thread` wrapper, not at module level |
| Preview URLs may be null for many tracks | RapidAPI fallback + graceful skip. Frontend shows "X/Y brani analizzati" |
| In-memory task store lost on server restart | Acceptable for MVP — tasks are short-lived (< 5 min). Document for future Redis upgrade |
| librosa on Windows may need numba/llvmlite | Test `pip install librosa soundfile` on dev machine before implementing |
| Related artists API calls add to rate limit budget | Capped at 5 artists * 2 calls each = 10 max. Within budget with Semaphore(2) |

### Open Tensions

| Tension | Options | Resolve When |
|---------|---------|-------------|
| Task store persistence | A: in-memory dict (simple, MVP) / B: DB table (survives restarts) / C: Redis (scalable) | Start with A, upgrade if needed |
| Analysis trigger | A: auto-trigger on page load when no features / B: user clicks "Analizza" button | Implementer chooses — A is smoother UX, B gives user control |
| librosa accuracy vs Spotify original | librosa estimates differ from Spotify's ML model — values are approximate | Document in UI tooltip, never claim exact match |

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
