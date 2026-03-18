# Spotify Listening Intelligence — Task List

## Bug Aperti

- [x] **Confronto playlist** — dati incompleti: ✅ FIXED
  - [x] Numero di brani presenti in ogni playlist assente prima del confronto → fallback `GET /playlists/{id}` metadata
  - [x] Popularity media = 0 → enrichment individuale con `GET /tracks/{id}` (cap 100)
  - [x] Genere = "—" → artist genre cap alzato da 20 a 50
- [x] **Dashboard**: genere top nullo → artist genre cap alzato da 20 a 50 (popularity non era un bug — `/me/top/tracks` restituisce popularity completa)
- [x] **Evoluzione del Gusto** — ❌ NON È UN BUG: formule verificate corrette (fedeltà, turnover, artisti fedeli, tracce persistenti)

---

## Known Gaps

- [ ] `taste_map.py` non legge audio features dal DB — gira sempre in modalita `genre_popularity`. Wiring con tabella `AudioFeatures` da implementare.

---

## Feature Roadmap

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

---

## Completato

- **Health Report Fixes** (2026-03-18) — Dead code: ReceiptCard.jsx (orphan), TIME_RANGES/TIME_RANGE_LABELS (unused). Wrapped slides: field mismatches (image→image_url, cluster_names object→array, album_image), SlidePeakHours weekend_pct derivation + empty guard, SlideListeningHabits zero guard, SlideOutro useCORS. GenreDNA rank-based decay instead of fake linear. StreakDisplay active_last_7 backend+frontend wiring. DEP: soundfile removed from requirements-dev.txt
- **Fix Bug Aperti** (2026-03-18) — Playlist comparison: popularity enrichment via individual `GET /tracks/{id}` (cap 100), track count fallback via `GET /playlists/{id}` metadata (cap 20), artist genre cap 20→50 in playlists.py + audio_analyzer.py (×3 locations). New `SpotifyClient.get_track()` method. Evoluzione del Gusto confermato non-bug. 25 nuovi test in test_playlists.py
- **Fix NaN JSON serialization** (2026-03-18) — sanitize_nans() utility in json_utils.py, applied su 5 router (profile, analytics×3, artist_network, wrapped), 21 test, PCA zero-variance guard + concurrent session fix in profile.py
- **ThrottleBanner proattivo** (2026-03-18) — Middleware X-RateLimit-Usage header, endpoint GET /api/rate-limit-status, ThrottleBanner 3 livelli (>60% ambra, >85% rosso, 429 countdown), badge compatto in Header con uso corrente
- **API Call Optimization** (2026-03-18) — Cache key fragmentation fix (limit=50 + slice), cross-user artist cache (_artist_cache_1h TTL 1h), genre dedup in compute_trends (60→20 calls), playlist items caching (get_playlist_items TTL 5min), export dedup (profile from trends), SpotifyAuthError+RateLimitError re-raise from gather_in_chunks
- **Rate Limit Hardening Refactor** (2026-03-18) — Global error handlers (main.py), TOCTOU fix (atomic sliding window), semaphore 6→3, gather_in_chunks burst control, budget caps (200/500 tracks, retry_after 30s), saved_tracks cache, skills update
- **Tier 2: Social Layer** (2026-03-15) — Friendship + FriendInviteLink models, social router (invite/accept/list/delete/compare/leaderboard), compatibility service (Jaccard generi, artist overlap, popularity cosine similarity), CompatibilityMeter + TasteComparison + Leaderboard + FriendCard + InviteModal components, FriendsPage, Sidebar + App.jsx wiring
- **Phase 1-3: scikit-learn + NetworkX** (2026-03-14) — genre_utils, artist_network refactor (Louvain/PageRank/betweenness), taste_clustering (DBSCAN/PCA/IsolationForest/cosine), taste_map, TasteMap.jsx, similarity badges, Top per Cerchia, tooltips fix
- **Tier 1: Foundation + Hardening** (2026-03-14) — Profile, metriche DB, ShareCard, daily aggregates, cachetools, librosa, rate limit hardening, discovery, deprecated API cleanup
