# Spotify Listening Intelligence — Task List

## Completati
- [x] Docker Compose setup (backend uvicorn + frontend nginx porta 5173)
- [x] OAuth2 PKCE con Spotify
- [x] 6 route principali scaffoldate (Dashboard, Evolution, Temporal, Artists, Playlist Analytics, Compare)
- [x] Pagina Discovery (7ª route)
- [x] Accumulo RecentPlay nel DB
- [x] Token refresh automatico in spotify_client
- [x] Resilienza: SpotifyAuthError propagation, _safe_fetch, non-blocking snapshots

## Bug Aperti
- [ ] Confronto e analisi playlist: dati vuoti — root cause analysis necessaria
- [ ] Dashboard: popolarità media 0/100 non coerente, genere top nullo
- [ ] Discovery: distribuzione popolarità e hidden gems da rivedere

## UX/Label Aperti
- [ ] Evoluzione del gusto: info hover sui primi 4 label
- [ ] Sostituire "1 periodo/2 periodi/3 periodi" con nomi significativi
- [ ] Ecosistema artisti: info label al hover, "cluster" poco significativo
- [ ] Eliminare label "nessun dato disponibile" residui

---

## PRIORITÀ 1 — Data Foundation
- [ ] Aggiungere APScheduler a FastAPI per sync RecentPlay ogni 60 minuti (refresh_token già in DB)
- [ ] Implementare retry-on-401 in spotify_client._request (refresh + retry una volta)
- [ ] Creare modello UserSnapshot: snapshot giornaliero top_artists/top_tracks JSON + timestamp
- [ ] Background task: salvare snapshot giornaliero al primo login del giorno
- [ ] Nuovo endpoint: GET /api/snapshots/diff?period=week — delta tra snapshot

## PRIORITÀ 2 — UX/UI Polish
- [ ] Aggiungere Framer Motion alle dipendenze React
- [ ] Implementare wrapper transizione pagina con AnimatePresence
- [ ] Animazione ingresso sfalsata per liste/griglie (TopTracks, ArtistCards)
- [ ] Sostituire tutti gli spinner con skeleton loader che rispecchiano la forma del componente
- [ ] Scroll-driven fade-in per KPI cards in dashboard
- [ ] Animazione smooth per collapse sidebar (mobile)

## PRIORITÀ 3 — Wrapped Export (dipende da Priorità 1)
- [ ] Nuova route /wrapped: report animato full-screen (miglior mese, top artist, streak)
- [ ] Export come PNG via html2canvas
- [ ] Pulsante condivisione (Web Share API)

## PRIORITÀ 4 — CI/CD (no migrazione PostgreSQL)
- [ ] GitHub Actions workflow: lint (eslint + ruff) + build check su ogni PR
- [ ] Docker build test in CI
- [ ] Nessuna migrazione PostgreSQL — SQLite sufficiente per utente singolo
