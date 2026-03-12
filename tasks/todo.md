# Spotify Listening Intelligence — Task List

## Bug Aperti
- [ ] Confronto playlist: endpoint migrato (`/items`, field `"item"`). Rate limit fix: cap `max_retry_after=30s`, global cooldown in SpotifyClient, dedup artisti cross-playlist (da ~70 a ~30 API calls per 4 playlist), Semaphore(2), cap 20 artisti globale. Aggiunto `retry_with_backoff` a `historical_tops.py` e `background_tasks.py`. **Da verificare live.**
- [ ] Dashboard: popolarità media 0/100 non coerente, genere top nullo
- [ ] Discovery: distribuzione popolarità e hidden gems da rivedere
- [ ] Evoluzione del Gusto: controllare verità dati del labels Fedeltà, Turnover, Artisti Fedeli, Tracce Persistenti, Distribuzione Artisti per Periodo
- [ ] Ecosistema Artisti: Controllare Verità dati del labels Artisti nel Grafo, Connessioni, Cerchie, Artisti Top

## CI/CD
- [ ] GitHub Actions workflow: lint (eslint + ruff) + build check su ogni PR
- [ ] Docker build test in CI

## Suggestion (Health Report — bassa priorità)

### Backend
- [ ] `get_recommendations` chiama endpoint deprecato, spreca una API call (S-2)
- [ ] Default RPM=60 in `rate_limiter.py` ma app configura 120 — default fuorviante (S-4)
- [ ] `compute_trends` esegue 3 profili sequenzialmente — parallelizzabile con `asyncio.gather` (S-5)

### Frontend
- [ ] `KPICard.jsx`: `value % 1` applicato a stringhe — innocuo ma poco chiaro (S-1)
- [ ] `ArtistNetwork.jsx`: simulazione si riavvia su nuovi ref array anche se dati invariati (S-2)
- [ ] `ArtistNetwork.jsx`: niente keyboard focus/aria-label su nodi SVG interattivi (S-3)
- [ ] `ListeningHeatmap.jsx` + `StreakDisplay.jsx`: inline `<style>` — spostare in globals.css (S-4/S-5)
- [ ] `DashboardPage.jsx`: loading combinato blocca sulla richiesta più lenta — progressive rendering possibile (S-6)
- [ ] `PlaylistStatCard.jsx` + `SessionStats.jsx` + `StreakDisplay.jsx`: CSS `animate-slide-up` invece di framer-motion (S-7/S-8)
- [ ] `DashboardPage.jsx`: indentazione inconsistente (S-9)
- [ ] `ClaudeExportPanel.jsx`: naming `border-border-hover` confuso (S-10)
- [ ] `SlideOutro.jsx`: html2canvas canvas si accumulano su click ripetuti (S-11)
