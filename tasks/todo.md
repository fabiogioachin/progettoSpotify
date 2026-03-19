# Spotify Listening Intelligence — Task List

## Bug Aperti (priorità alta)

### BUG-1: Popolarità brani ancora nulla ovunque
- Popolarità = null in Dashboard, Discovery ("distribuzione popolarità"), playlist singole
- Hidden Gems in Discovery vuote (dipendono da popolarità)
- La cache `TrackPopularity` non sta funzionando o non viene popolata correttamente
- **Impatto**: Dashboard, Discovery, Playlist Analytics

### BUG-2: Conteggio brani playlist buggato
- **Confronto**: quasi ok, ma ancora sbagliato per playlist con molti brani e una playlist con 23 brani
- **Analisi**: tutte le playlist risultano vuote nel grafico "distribuzione dimensioni" (regressione)
- **Root cause da investigare**: il fallback via `/items?limit=1` o il campo `total` non funziona

### BUG-3: Diversità artisti supera 100%
- In schede playlist singole (Analisi), `artist_concentration` > 1.0 nonostante il cap
- Il cap a 1.0 introdotto nel fix precedente non è applicato correttamente

### BUG-4: Dashboard spreca chiamate API senza valore
- Troppe chiamate API senza portare dati utili alla pagina
- Popolarità mancante nella dashboard
- Il grafico "trend temporale" non ha senso — da rivedere o rimuovere

### BUG-5: Discovery — dati nulli e dato mock sospetto
- Grafico "distribuzione popolarità" vuoto (dipende da BUG-1)
- "Scoperte recenti" vuote
- Il dato "50% affine" nelle scoperte recenti sembra mock/inventato — verificare provenienza
- Se il dato non è reale, rimuoverlo

### BUG-6: Cerchie artisti non funzionano correttamente
- In "Ecosistema Artisti" e nel Wrapped, le cerchie non sono interconnesse
- I nomi delle cerchie non sono significativi (nomi generici invece di descrittivi)
- Il clustering/naming va rivisto

### BUG-7: Orizzonte temporale limitato
- Il grafico "tempo di ascolto" in Dashboard ha un orizzonte troppo corto
- Aggiungere finestre temporali più ampie (1 settimana, 1 mese, 3 mesi, tutto)
- Stessa funzionalità richiesta per il grafico a griglia in "Pattern Temporali"

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

## Completato (recente)

- **Bug Fix Sprint v2** (2026-03-19) — Centralized `TrackPopularity` DB cache (24h TTL) replaces 4 duplicate enrichment blocks. Playlist analytics: `sizes` updated from actual fetched counts (fix empty histogram), `artist_concentration` capped at 1.0. Track count fallback cap 20→50 with logging. Dashboard: `PopularityTrend` replaced with "Tempo di Ascolto" area chart (daily_minutes from DailyListeningStats/RecentPlay, zero API calls). 168 tests pass.
- **Bug Fix Sprint** (2026-03-19) — Popularity enrichment via `GET /tracks/{id}` in library/audio_analyzer/discovery (cap 50), playlist track count fallback via `/items?limit=1`, ThrottleBanner rolling countdown con `X-RateLimit-Reset` header. 9 nuovi test (168 totali).
- **API Efficiency + Bug Fixes** (2026-03-18) — Trends budget 53->23 calls, taste_map AudioFeatures DB wiring, dead endpoints removed, React.StrictMode removed, useSpotifyData stale-while-revalidate cache, playlists.py null-safe fixes. Skills updated.
- **Health Report Fixes** (2026-03-18) — Dead code cleanup (ReceiptCard, TIME_RANGES), Wrapped slides field mismatches, GenreDNA rank-based decay, StreakDisplay wiring, soundfile removed.
- **Fix Bug Aperti (parziale)** (2026-03-18) — Playlist comparison: popularity enrichment via `GET /tracks/{id}` (cap 100), track count fallback via `GET /playlists/{id}` metadata (cap 20), artist genre cap 20->50. 25 nuovi test.
- **ThrottleBanner proattivo** (2026-03-18) — Middleware X-RateLimit-Usage header, endpoint GET /api/rate-limit-status, ThrottleBanner 3 livelli, badge compatto in Header.
- **Rate Limit Hardening** (2026-03-18) — Global error handlers, TOCTOU fix, semaphore 6->3, gather_in_chunks burst control, budget caps.
- **Phase 1-3: scikit-learn + NetworkX** (2026-03-14) — genre_utils, artist_network (Louvain/PageRank), taste_clustering (DBSCAN/PCA), taste_map, TasteMap.jsx.
