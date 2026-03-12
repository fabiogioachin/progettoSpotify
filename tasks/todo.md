# Spotify Listening Intelligence — Task List

## Completati
- [x] Docker Compose setup (backend uvicorn + frontend nginx porta 5173)
- [x] OAuth2 PKCE con Spotify
- [x] 7 route principali (Dashboard, Discovery, Evolution, Temporal, Artists, Playlist Analytics, Compare)
- [x] Accumulo RecentPlay nel DB
- [x] Token refresh automatico in spotify_client (proactive + retry-on-401)
- [x] Resilienza: SpotifyAuthError propagation, _safe_fetch, non-blocking snapshots
- [x] APScheduler: sync_recent_plays (hourly) + save_daily_snapshot
- [x] UserSnapshot: snapshot giornaliero top_artists/top_tracks JSON
- [x] "Cluster" → "Cerchia" rename
- [x] Health scan + auto-fix (2026-03-11): 3 orphan files rimossi, 3 export morti, 8 fix convenzioni empty-state, sezione generi duplicata in ArtistNetworkPage

## Bug Aperti
- [ ] Confronto playlist: endpoint migrato (`/items`, field `"item"`). Rate limit fix: cap `max_retry_after=30s`, global cooldown in SpotifyClient, dedup artisti cross-playlist (da ~70 a ~30 API calls per 4 playlist), Semaphore(2), cap 20 artisti globale. Aggiunto `retry_with_backoff` a `historical_tops.py` e `background_tasks.py`. **Da verificare live.**
- [ ] Dashboard: popolarità media 0/100 non coerente, genere top nullo
- [ ] Discovery: distribuzione popolarità e hidden gems da rivedere
- [ ] Evoluzione del Gusto: controllare verità dati del labels Fedeltà, Turnover, Artisti Fedeli, Tracce Persistenti, Distribuzione Artisti per Periodo
- [ ] Ecosistema Artisti: Controllare Verità dati del labels Artisti nel Grafo, Connessioni, Cluster, Artisti Top

## UX/UI da Fare
- [x] Tooltip info hover con delay 1s su tutti i KPICard (KPICard.jsx refactored con useRef/setTimeout)
- [x] Evoluzione del gusto: tooltip già presenti su tutti i KPI
- [x] Ecosistema artisti: tooltip aggiunti a tutti i KPI + fix "Cluster" → "Cerchie"
- [x] Pattern Temporali: tooltip aggiunti a tutti i KPI
- [x] Analisi Playlist: tooltip aggiunti a tutti i KPI
---

## PRIORITÀ 2 — UX/UI Polish ✓
- [x] Aggiungere Framer Motion alle dipendenze React
- [x] Implementare wrapper transizione pagina con AnimatePresence (AppLayout.jsx)
- [x] Animazione ingresso sfalsata per liste/griglie — StaggerContainer + StaggerItem su tutte le 7 pagine
- [x] Sostituire tutti gli spinner con skeleton loader (Skeleton.jsx: KPICard, TrackRow, Card, Grid)
- [x] Scroll-driven fade-in per KPI cards (motion.div whileInView in KPICard.jsx)
- [x] Animazione smooth per collapse sidebar mobile (AnimatePresence + motion.aside in Sidebar.jsx)

## PRIORITÀ 3 — Wrapped Export ✓
- [x] Nuova route /wrapped: report animato full-screen stories-style (8 slide: intro, top tracks, abitudini, peak hours, artisti, generi, cerchie, outro)
- [x] Backend endpoint aggregato `GET /api/wrapped` (5 servizi in parallelo con _safe_fetch, available_slides dinamiche)
- [x] Export come PNG via html2canvas (SlideOutro con pulsante Scarica)
- [x] Pulsante condivisione (Web Share API con fallback a download)

## PRIORITÀ 4 — CI/CD
- [ ] GitHub Actions workflow: lint (eslint + ruff) + build check su ogni PR
- [ ] Docker build test in CI
