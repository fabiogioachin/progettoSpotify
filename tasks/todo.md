# Spotify Listening Intelligence — Task List

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

- **Tier 2: Social Layer** (2026-03-15) — Friendship + FriendInviteLink models, social router (invite/accept/list/delete/compare/leaderboard), compatibility service (Jaccard generi, artist overlap, popularity cosine similarity), CompatibilityMeter + TasteComparison + Leaderboard + FriendCard + InviteModal components, FriendsPage, Sidebar + App.jsx wiring
- **Phase 1-3: scikit-learn + NetworkX** (2026-03-14) — genre_utils, artist_network refactor (Louvain/PageRank/betweenness), taste_clustering (DBSCAN/PCA/IsolationForest/cosine), taste_map, TasteMap.jsx, similarity badges, Top per Cerchia, tooltips fix
- **Tier 1: Foundation + Hardening** (2026-03-14) — Profile, metriche DB, ShareCard, daily aggregates, cachetools, librosa, rate limit hardening, discovery, deprecated API cleanup
