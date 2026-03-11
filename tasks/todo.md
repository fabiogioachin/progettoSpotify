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

## UX/UI da Fare
- [ ] **UI-9**: StreakDisplay in TemporalPage non riceve `activeDays` — il mini-calendario 7 giorni mostra sempre tutti i giorni inattivi. Serve: investigare dati backend `/api/temporal` → passare `streak.active_days` come prop
- [ ] **UI-7**: TasteEvolutionPage — le colonne artisti vuote mostrano "Nessun nuovo artista" / "Nessun artista fedele" / "Nessun artista in calo". Valutare se nascondere colonne vuote o l'intera riga (attenzione al layout 3-colonne). Controllare verità dati labels. inconsistenza tra labels e distribuzione artisti per periodo.
- [ ] Evoluzione del gusto: info hover sui primi 4 label
- [ ] Ecosistema artisti: info label al hover. controlalre verità dati.

---

## PRIORITÀ 2 — UX/UI Polish
- [ ] Aggiungere Framer Motion alle dipendenze React
- [ ] Implementare wrapper transizione pagina con AnimatePresence
- [ ] Animazione ingresso sfalsata per liste/griglie (TopTracks, ArtistCards)
- [ ] Sostituire tutti gli spinner con skeleton loader che rispecchiano la forma del componente
- [ ] Scroll-driven fade-in per KPI cards in dashboard
- [ ] Animazione smooth per collapse sidebar (mobile)

## PRIORITÀ 3 — Wrapped Export
- [ ] Nuova route /wrapped: report animato full-screen (miglior mese, top artist, streak)
- [ ] Export come PNG via html2canvas
- [ ] Pulsante condivisione (Web Share API)

## PRIORITÀ 4 — CI/CD
- [ ] GitHub Actions workflow: lint (eslint + ruff) + build check su ogni PR
- [ ] Docker build test in CI
