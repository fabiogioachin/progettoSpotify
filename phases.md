# phases.md — Card "I brani più ascoltati"

Piano sorgente: `.claude/tasks/plan-global-top-tracks/PLAN.md`.
Esito del gate d'ingresso di quel piano: `.claude/tasks/plan-global-top-tracks/GATE-1-RESULT.md`
(**Opzione A respinta da Spotify**, 03/09/2026).
Decisione utente del 03/09/2026: **fare sia l'Opzione D sia l'Opzione C**, due card distinte.

## Architectural Anchors

| Anchor | Valore | Rationale |
|---|---|---|
| Fonte D | `track_popularity` (cache DB già esistente) + `recent_plays` | Zero chiamate Spotify, zero credenziali |
| Fonte C | Last.fm `chart.getTopTracks` via nuovo `lastfm_client.py` | Unica classifica mondiale vera raggiungibile |
| Cache condivisa | Il chart mondiale è identico per tutti: **mai una chiave per-utente** | skill `spotify-api-budget` |
| Degradazione senza chiave | `settings.lastfm_api_key` vuota → il servizio ritorna `None`, la card si nasconde | Stesso pattern di `rapidapi_bridge.py` |
| Card vuota | **Nascosta**, mai "nessun dato disponibile" | Convenzione di progetto |
| Markup card | `glow-card bg-surface rounded-xl p-5` + `<h3>` + `<p>` sottotitolo + `TrackCard` in `StaggerContainer`/`StaggerItem`, dentro `SectionErrorBoundary` | Identico alle card esistenti |
| `TrackCard.jsx` | **NON si tocca** | Già generico |
| Errori Spotify/HTTP | `except SpotifyAuthError: raise` prima di ogni `except Exception` | Invariante 1 |
| Task in background | Sessione DB **propria** via `async_session()`, mai quella dell'handler | Invariante 4 |
| Default finti | Assenza → `None`/`[]`, mai numeri plausibili; flag `*_source` in risposta | Invariante 5 |
| Lingua UI | Italiano | Convenzione |
| Periodi | D segue il selettore (`7d/30d/90d/1y/all`); C non lo segue e lo dichiara | Vedi PLAN.md |
| OFF-LIMITS | `TrackCard.jsx`, `spotify_client.py` (non serve più `market`: l'Opzione A è morta), qualsiasi file fuori da § File impattati | Contenimento |

## Slices

### Slice 1 — Opzione D: "Popolari nel mondo, fra i tuoi"

**Goal**: card che mostra i brani che l'utente ascolta, riordinati per `popularity` globale di
Spotify. Segue il selettore di periodo. Solo DB, nessuna chiamata esterna.

**File Scope**: `backend/app/routers/library.py`, `backend/app/schemas.py`,
`backend/tests/test_top_global_popular.py` (nuovo), `frontend/src/pages/DashboardPage.jsx`.

**Demo criteria**: `pytest -q` verde; `npm run lint` e `npm run build` verdi; la card compare in
Dashboard accanto a quella personale, reagisce al selettore di periodo, e sparisce quando non ci
sono brani con popularity in cache.

**Exit gate**: test verdi + evidenza a schermo della card.
**Rollback**: `git restore` sui quattro file.
**Attempts**: slice=0 demo=1 fix_iters=1 recovery=0
**Status**: DONE — con una correzione di rotta: la fonte prevista (`popularity`
di Spotify) e' risultata anch'essa morta in dev mode a implementazione avviata
(vedi `GATE-2-RESULT.md`), e la card e' stata ribasata sul `playcount` mondiale
di Last.fm. Il significato della card non cambia, cambia il righello.

### Slice 2 — Opzione C: "I brani più ascoltati nel mondo" (Last.fm)

**Goal**: card con la classifica mondiale vera, da Last.fm, cache condivisa in DB con TTL, lock
Redis attorno al refresh, card nascosta finché la chiave non è configurata.

**File Scope**: `backend/app/services/lastfm_client.py` (nuovo),
`backend/app/services/global_chart_cache.py` (nuovo), `backend/app/models/track.py` (nuovo modello),
`backend/alembic/versions/` (migrazione), `backend/app/routers/library.py`,
`backend/app/routers/health.py` (campo età cache), `backend/app/config.py` (`lastfm_api_key`),
`backend/tests/test_top_global.py` (nuovo), `frontend/src/pages/DashboardPage.jsx`, `.env.example`.

**Demo criteria**: `pytest -q` verde; lint/build verdi; senza chiave la card è assente e nulla si
rompe; con chiave configurata la card mostra la classifica col suo "aggiornata al …".

**Exit gate**: test verdi + evidenza.
**Rollback**: `git restore` + `alembic downgrade -1`.
**Attempts**: slice=0 demo=1 fix_iters=0 recovery=0
**Status**: DONE nel codice, **demo visiva in attesa della chiave Last.fm**.
Verificato dal vivo che senza chiave entrambe le card si nascondono e nulla si
rompe (`configured: false`, 471 brani contati come "senza dato" e non azzerati).
Lo stato pieno delle due card non e' dimostrabile finche' `LASTFM_API_KEY` non
e' in `.env`: e' un gesto umano, la chiave e' gratuita.
