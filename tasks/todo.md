# Spotify Listening Intelligence — Task List

## Feature: scikit-learn + NetworkX Integration

Piano di riferimento: `.claude/plans/indexed-bubbling-crown.md`

Obiettivo: Sostituire BFS con Louvain communities (NetworkX), aggiungere PageRank/betweenness, fuzzy genre matching, sklearn clustering/PCA/cosine similarity, TasteMap in ProfilePage.

---

## Domain Analysis

| Domain | Files | Agent | Dependencies |
|--------|-------|-------|-------------|
| Genre utils (new module) | `backend/app/services/genre_utils.py` | backend-specialist | None |
| Artist network (backend) | `backend/app/services/artist_network.py` | backend-specialist | genre_utils |
| Taste clustering (new module) | `backend/app/services/taste_clustering.py` | backend-specialist | genre_utils |
| Taste map (new module) | `backend/app/services/taste_map.py` | backend-specialist | taste_clustering |
| Discovery (backend) | `backend/app/services/discovery.py` | backend-specialist | taste_clustering |
| Profile router | `backend/app/routers/profile.py` | backend-specialist | taste_map |
| Artist network (frontend) | `frontend/src/pages/ArtistNetworkPage.jsx`, `frontend/src/components/charts/ArtistNetwork.jsx` | frontend-specialist | Artist network backend |
| TasteMap (frontend) | `frontend/src/components/profile/TasteMap.jsx`, `frontend/src/pages/ProfilePage.jsx` | frontend-specialist | Profile router |
| Discovery (frontend) | `frontend/src/pages/DiscoveryPage.jsx` | frontend-specialist | Discovery backend |

---

## Execution Waves

```
Wave 1 (sequential): B1.1 → B1.2
  B1.1: requirements.txt + genre_utils.py (foundation)
  B1.2: artist_network.py NetworkX refactor (depends on genre_utils)

Wave 2 (parallel after Wave 1):
  B2.1: taste_clustering.py (depends on genre_utils only)
  F1.1: ArtistNetworkPage.jsx + ArtistNetwork.jsx (depends on backend artist_network changes)

Wave 3 (parallel after B2.1):
  B2.2: artist_network.py sklearn integration (depends on taste_clustering)
  B2.3: discovery.py sklearn integration (depends on taste_clustering)
  B2.4: taste_map.py + profile.py router (depends on taste_clustering)

Wave 4 (parallel after Wave 3):
  F3.1: TasteMap.jsx + ProfilePage.jsx (depends on profile router)
  F3.2: DiscoveryPage.jsx similarity badge (depends on discovery backend)
  F3.3: ArtistNetworkPage.jsx cluster rankings (depends on B2.2)

Wave 5 (sequential):
  V1: Backend lint + tests
  V2: Frontend lint + build
  V3: Live verification
```

---

## Phase 1 — Data Foundation + NetworkX

### Backend

- [x] **B1.1** — Add networkx + scikit-learn dependencies and create genre_utils.py
  - Files: `backend/requirements.txt`, `backend/app/services/genre_utils.py` (NEW)
  - Agent: backend-specialist
  - Depends on: none
  - Details:
    - Add `networkx>=3.2` and `scikit-learn>=1.4` to requirements.txt
    - Create `genre_utils.py` with: `normalize_genre()`, `genres_are_related()`, `compute_genre_similarity()`, `build_genre_vocabulary()`
    - Pure-compute module, no API calls, no SpotifyClient import
    - Token overlap threshold for fuzzy matching (e.g., "indie rock" ~ "indie pop")

- [x] **B1.2** — Refactor artist_network.py with NetworkX + fuzzy genre matching
  - Files: `backend/app/services/artist_network.py`
  - Agent: backend-specialist
  - Depends on: B1.1
  - Details:
    - Add `short_term` fetch (parallel with medium/long) for ~45 artists
    - Replace exact genre set intersection with `compute_genre_similarity()` from genre_utils
    - Edge weight = float 0-1 (genre similarity) instead of int (shared genre count)
    - Replace `_detect_clusters()` BFS with `louvain_communities(G, weight="weight", resolution=1.0, seed=42)`
    - Replace `_find_bridges()` with `betweenness_centrality(G, weight="weight")`
    - Add `pagerank(G, weight="weight")` per node
    - Tuning: if `cluster_count < 3` and `node_count > 15`, retry with `resolution=1.5`
    - Add `data_quality` field: `{artists_without_genres: int, warning: str|None}`
    - Add `pagerank` and `betweenness` to each node dict
    - Add `density` to metrics
    - DELETE `_detect_clusters()` and `_find_bridges()` functions entirely

### Frontend

- [x] **F1.1** — Update ArtistNetworkPage KPIs/tooltips and ArtistNetwork chart
  - Files: `frontend/src/pages/ArtistNetworkPage.jsx`, `frontend/src/components/charts/ArtistNetwork.jsx`
  - Agent: frontend-specialist
  - Depends on: B1.2
  - Details:
    - **ArtistNetworkPage.jsx:**
      - Fix lying tooltips: remove all "Related Artists API" references
      - "Artisti nel Grafo" tooltip → "I tuoi artisti piu ascoltati da 3 periodi, collegati per generi musicali condivisi"
      - "Connessioni" tooltip → "Ogni connessione indica generi musicali condivisi. Piu generi in comune, connessione piu forte"
      - Replace "Artisti Top" KPI with "Densita Rete" (`metrics.density` as %)
      - Add amber warning banner below KPIs when `data_quality.warning` is present
    - **ArtistNetwork.jsx:**
      - Node size from PageRank: `r = Math.max(4, Math.min(18, 5 + node.pagerank * 200))`
      - Tooltip: add "Influenza: X%" from pagerank
      - Edge opacity from weight: `strokeOpacity = 0.04 + edge.weight * 0.12`

---

## Phase 2 — scikit-learn Clustering + Scoring + TasteMap

### Backend

- [x] **B2.1** — Create taste_clustering.py with sklearn functions
  - Files: `backend/app/services/taste_clustering.py` (NEW)
  - Agent: backend-specialist
  - Depends on: B1.1 (genre_utils)
  - Details:
    - Pure-compute module, no SpotifyClient, no API calls
    - `build_feature_matrix(artists, audio_features=None, genre_vocab=None)` — genre one-hot (20 cols) + popularity/100 + log10(followers)/8, optional audio (7 cols), StandardScaler
    - `name_clusters(labels, artists)` — TF-IDF-like dominant+distinctive genre per cluster
    - `rank_within_cluster(labels, artists, pagerank)` — 40% PageRank + 30% popularity + 30% genre diversity
    - `compute_taste_pca(matrix, ids, n_components=2)` — PCA 2D, check variance_explained > 30%
    - `compute_cosine_similarities(matrix, ids)` — cosine similarity to user centroid
    - `detect_outliers_isolation_forest(matrix, ids, contamination=0.1)` — replaces euclidean distance

- [x] **B2.2** — Integrate sklearn naming/ranking into artist_network.py
  - Files: `backend/app/services/artist_network.py`
  - Agent: backend-specialist
  - Depends on: B2.1
  - Details:
    - Import `build_feature_matrix`, `name_clusters`, `rank_within_cluster` from taste_clustering
    - Replace simple genre-counting cluster naming with `name_clusters()` (TF-IDF-like)
    - Add `cluster_rankings` to response (top artist per cluster)
    - Verify key names between service return and response dict (lessons.md: dict.get() failures are silent)

- [x] **B2.3** — Integrate sklearn into discovery.py (Isolation Forest + cosine similarity)
  - Files: `backend/app/services/discovery.py`
  - Agent: backend-specialist
  - Depends on: B2.1
  - Details:
    - When `has_features=True`: use `detect_outliers_isolation_forest()` instead of euclidean distance
    - Fallback to genre+popularity matrix when features absent
    - Add `similarity_score` (cosine similarity to centroid) on each recommendation — additive field, not breaking
    - Keep existing popularity-based hidden gems as ultimate fallback

- [x] **B2.4** — Create taste_map.py and add to profile router
  - Files: `backend/app/services/taste_map.py` (NEW), `backend/app/routers/profile.py`
  - Agent: backend-specialist
  - Depends on: B2.1
  - Details:
    - **taste_map.py:** `compute_taste_map(db, client, user_id)` — fetch top artists (medium_term, limit=50), get audio features from DB cache (optional), build feature matrix, PCA 2D, return `{points, variance_explained, feature_mode, genre_groups}`
    - `feature_mode`: `"audio"` | `"genre_popularity"` | `"insufficient"`
    - Pure-compute on local data after initial fetch
    - **profile.py:** Add `_safe_fetch("taste_map", compute_taste_map(db, client, user_id))` to `asyncio.gather`
    - Add `taste_map` to response dict

---

## Phase 3 — Frontend Integration

- [x] **F3.1** — Create TasteMap.jsx component and add to ProfilePage
  - Files: `frontend/src/components/profile/TasteMap.jsx` (NEW), `frontend/src/pages/ProfilePage.jsx`
  - Agent: frontend-specialist
  - Depends on: B2.4
  - Details:
    - **TasteMap.jsx:** Recharts ScatterChart
      - Each point = artist at (PC1, PC2)
      - Color by `primary_genre` (top 6 genres → 6 colors from palette, rest = gray)
      - Point size by popularity (4-12px)
      - Tooltip: artist name, genre, popularity
      - Axes: "Componente 1 (X%)" / "Componente 2 (Y%)"
      - Info text when `featureMode === "genre_popularity"`: "Basato su generi e popolarita. Analizza i brani per una mappa piu precisa."
      - Hide section when `featureMode === "insufficient"` or `points.length < 3`
      - Title: "Mappa del tuo gusto"
    - **ProfilePage.jsx:** Add TasteMap after DecadeChart, `lg:col-span-2`
      - Conditional: only render if `data.taste_map` exists and not insufficient

- [x] **F3.2** — Add similarity badge to DiscoveryPage recommendations
  - Files: `frontend/src/pages/DiscoveryPage.jsx`
  - Agent: frontend-specialist
  - Depends on: B2.3
  - Details:
    - When `similarity_score` present on a recommendation: show badge "X% affine" instead of "Pop. X"
    - Keep "Pop. X" as fallback when similarity_score absent
    - Accent color badge style, consistent with existing badges

- [x] **F3.3** — Add "Top per Cerchia" section to ArtistNetworkPage
  - Files: `frontend/src/pages/ArtistNetworkPage.jsx`
  - Agent: frontend-specialist
  - Depends on: B2.2
  - Details:
    - New section below "Artisti Ponte": "Top per Cerchia"
    - Show #1 artist per cluster with image, name, cluster name
    - Uses `cluster_rankings` from response
    - StaggerContainer with cards matching existing bridge artist style

---

## Verification

- [x] **V1** — Backend lint, format, tests
  - Commands:
    - `cd backend && pip install networkx scikit-learn`
    - `cd backend && ruff check app/ && ruff format app/ --check`
    - `cd backend && pytest`
  - Agent: orchestrator
  - Depends on: B2.2, B2.3, B2.4

- [x] **V2** — Frontend lint + build
  - Commands:
    - `cd frontend && npm run lint`
    - `cd frontend && npm run build`
  - Agent: orchestrator
  - Depends on: F3.1, F3.2, F3.3

- [x] **V3** — Live verification (manual)
  - Agent: orchestrator
  - Depends on: V1, V2
  - Checks:
    - `GET /api/artist-network` → response has `pagerank`, `betweenness`, `data_quality`, `cluster_rankings`
    - No "Related Artists API" in any tooltip
    - Node sizes vary by PageRank in network graph
    - `GET /api/profile` → response has `taste_map` with `points`, `feature_mode`
    - ProfilePage shows "Mappa del tuo gusto" scatter plot (or hides if insufficient)
    - `GET /api/analytics/discovery` → recommendations have `similarity_score`
    - Zero 403/429 errors from new code (sklearn/networkx never call Spotify API)
    - Backend logs: no new Spotify API calls from pure-compute services

---

## Bug Aperti (separati da questa feature)

- [ ] **Confronto playlist** — dati incompleti:
  - [ ] Numero di brani presenti in ogni playlist assente prima del confronto
  - [ ] Popularity media = 0: track objects da `/items` senza campo `popularity` → enrichment individuale con `GET /tracks/{id}`
  - [ ] Genere = "—": conseguenza del fix popularity + verifica artist genre cap
- [ ] **Dashboard**: popolarita media 0/100 non coerente, genere top nullo
- [ ] **Evoluzione del Gusto**: controllare verita dati dei labels Fedelta, Turnover, Artisti Fedeli, Tracce Persistenti

---

## Completato

### Tier 1 — Foundation + Hardening (2026-03-14)
- Profile: metrics, personality (4 archetipi), ProfilePage, ShareCardRenderer, daily aggregates
- cachetools TTL su SpotifyClient (5m/2m)
- Audio features recovery: librosa extraction + polling endpoint + RapidAPI fallback
- Rate limit hardening: early break, Semaphore(2), GenreDNA CSS vars fix
- Discovery: hidden gems, playlist compare migration, deprecated API cleanup

---

## Feature Roadmap

### Tier 2 — Social Layer (multi-utente stesso deploy)

#### 2A. Infrastruttura Amici
- [ ] feat: modelli `Friendship` + `FriendInviteLink` in `models/social.py`
- [ ] feat: router `social.py` — invite, accept, list, delete, compare
- [ ] feat: servizio `social.py` — compute_compatibility (Jaccard generi, overlap artisti, similarita popularity)

#### 2B. Compatibilita e Confronto
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
