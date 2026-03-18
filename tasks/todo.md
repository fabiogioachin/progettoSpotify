# Spotify Listening Intelligence — Task List

## In Progress: API Call Optimization (5 slices)

### Slice 1 — Fix cache key fragmentation
- [ ] `wrapped.py:62` → remove `limit=10` from `get_top_tracks`, slice `[:10]` in-memory
- [ ] `artist_network.py:46-57` → remove `limit=max_seed_artists` from `get_top_artists`, slice `[:max_seed_artists]` in-memory
- Files: `backend/app/routers/wrapped.py`, `backend/app/services/artist_network.py`

### Slice 2 — Artist cache cross-user (most impactful)
- [ ] Add `_artist_cache_1h = TTLCache(maxsize=512, ttl=3600)` module-level in `spotify_client.py`
- [ ] `get_artist()` → cache key = `("artist", artist_id)` without `user_id` (artist data is identical for all users)
- Files: `backend/app/services/spotify_client.py`

### Slice 3 — Deduplicate _extract_genres in compute_trends
- [ ] `compute_trends` calls `compute_profile` 3x, each calling `_extract_genres(cap=20)` independently → up to 60 artist fetches
- [ ] Refactor: collect all unique artist IDs from all 3 periods' tracks, dedup, fetch once with global cap=20, pass pre-fetched genres to `compute_profile`
- [ ] Add `pre_genres` parameter to `compute_profile` to skip `_extract_genres` when provided
- Files: `backend/app/services/audio_analyzer.py`

### Slice 4 — Cache playlist items in SpotifyClient
- [ ] Add `get_playlist_items(playlist_id, limit=50, offset=0)` method with `_cache_5m` TTL
- [ ] Update `playlists.py:compare_playlists` to use the new cached method
- Files: `backend/app/services/spotify_client.py`, `backend/app/routers/playlists.py`

### Slice 5 — Eliminate duplicate compute_profile in export.py
- [ ] `export.py:70-71` calls `compute_profile(time_range)` then `compute_trends()` which re-calls `compute_profile` for the same range
- [ ] Pass already-computed profile into `compute_trends` via new `precomputed` parameter
- Files: `backend/app/routers/export.py`, `backend/app/services/audio_analyzer.py`

### Slice 6 — Verification + docs update
- [ ] `ruff check + format`
- [ ] `pytest`
- [ ] Update `spotify-api-budget` skill with new budget numbers
- [ ] Update CLAUDE.md if needed

---

## Bug Aperti

- [ ] **Confronto playlist** — dati incompleti:
  - [ ] Numero di brani presenti in ogni playlist assente prima del confronto
  - [ ] Popularity media = 0: track objects da `/items` senza campo `popularity` → enrichment individuale con `GET /tracks/{id}`
  - [ ] Genere = "—": conseguenza del fix popularity + verifica artist genre cap
- [ ] **Dashboard**: popolarita media 0/100 non coerente, genere top nullo
- [ ] **Evoluzione del Gusto**: controllare verita dati dei labels Fedelta, Turnover, Artisti Fedeli, Tracce Persistenti

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

- **API Call Optimization** (2026-03-18) — Cache key fragmentation, cross-user artist cache, genre dedup, playlist items cache, export dedup
- **Rate Limit Hardening Refactor** (2026-03-18) — Global error handlers, TOCTOU fix, burst control, budget caps, cache, skills update
- **Tier 2: Social Layer** (2026-03-15) — Friendship + FriendInviteLink models, social router (invite/accept/list/delete/compare/leaderboard), compatibility service (Jaccard generi, artist overlap, popularity cosine similarity), CompatibilityMeter + TasteComparison + Leaderboard + FriendCard + InviteModal components, FriendsPage, Sidebar + App.jsx wiring
- **Phase 1-3: scikit-learn + NetworkX** (2026-03-14) — genre_utils, artist_network refactor (Louvain/PageRank/betweenness), taste_clustering (DBSCAN/PCA/IsolationForest/cosine), taste_map, TasteMap.jsx, similarity badges, Top per Cerchia, tooltips fix
- **Tier 1: Foundation + Hardening** (2026-03-14) — Profile, metriche DB, ShareCard, daily aggregates, cachetools, librosa, rate limit hardening, discovery, deprecated API cleanup
