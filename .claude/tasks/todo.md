# Todo

## Sessione corrente — completato

- [x] Fix onboarding: modal controllato solo da localStorage, non da `onboarding_completed` server-side
- [x] Fix timezone: `datetime.now().date()` → usa timezone dai dati (UTC) in `temporal_patterns.py`
- [x] Reset `onboarding_completed = false` nel DB

---

## Bug da fixare (prossima sessione, prima del refactoring)

### Sync ascolti recenti all'avvio backend

**Problema**: in dev mode il backend non gira 24/7. All'avvio del Docker, gli ultimi 50 brani ascoltati devono essere recuperati da Spotify API immediatamente (non aspettare login o timer hourly).

**Fix**:
- [ ] Aggiungere sync all'avvio in `main.py` lifespan (dopo APScheduler): per ogni utente attivo, chiama `_sync_user_recent_plays`
- [ ] Usare priorita' P1_BACKGROUND_SYNC per non bloccare le prime chiamate interattive
- [ ] Aggiungere delay staggerato tra utenti (5s) per non esaurire il budget
- [ ] Spotify API `/me/player/recently-played` restituisce max 50 items (hard limit API). Non e' possibile avere 100/150 in una singola chiamata. L'accumulo nel DB nel tempo e' l'unico modo per superare il limite.

**File**: `backend/app/main.py` (lifespan), `backend/app/services/background_tasks.py`

### Vista aggregata ascolti per il frontend

**Problema**: la tabella `recent_plays` ha 1 riga per ascolto (necessaria per heatmap/streak/temporale). Ma il frontend non deve mostrare duplicati — serve una vista aggregata.

**Design**: MANTENERE `recent_plays` (event log) + AGGIUNGERE vista aggregata computata.

**Fix**:
- [ ] Creare endpoint `GET /api/v1/library/recent-summary` che restituisce per ogni brano:
  - `track_spotify_id`, `track_name`, `artist_name`
  - `play_count`: numero totale riproduzioni (= COUNT righe per quel track)
  - `consecutive_days`: giorni consecutivi piu' recenti in cui e' stata ascoltata
  - `last_played_at`: ultima riproduzione
  - `first_played_at`: prima riproduzione registrata nell'app
- [ ] Il frontend deve mostrare un disclaimer: "Dati raccolti da quando usi Wrap (dal {first_play_date})"
- [ ] Query: `GROUP BY track_spotify_id` con aggregazioni, ordinato per `last_played_at DESC`
- [ ] Non creare una nuova tabella — computare on-the-fly dalla tabella eventi (624 righe e' trascurabile, anche 10K lo e')

**File**: `backend/app/routers/library.py` (nuovo endpoint), `frontend/src/pages/TemporalPage.jsx` o nuova sezione

---

## Refactoring API — Piano completo (sessione dedicata)

### Obiettivo
Tutte le pagine devono: (1) caricarsi immediatamente con skeleton, (2) popolare i dati progressivamente, (3) prioritizzare dati freschi da API Spotify, (4) aggiornare il DB come side-effect, (5) non fare chiamate duplicate.

### Principi architetturali

1. **API Spotify ha sempre priorita'**: il dato fresco viene dall'API, non dal DB
2. **DB = storico + statistiche avanzate**: non usare il DB come cache per dati che l'API restituisce inline (popularity, tracks, artists)
3. **Genre cache OK**: i generi NON sono inline nell'API tracks, quindi il cache DB 7d e' giustificato
4. **Request-scoped deduplication**: dentro una singola request, mai chiamare lo stesso endpoint Spotify 2+ volte
5. **Frontend rendering progressivo**: ogni sezione e' indipendente, carica con il suo skeleton

### Fase 1 — Backend: request-scoped data bundle (alta priorita')

#### 1.1 Creare `RequestDataBundle` in `spotify_client.py` o nuovo file

Pattern: fetch una volta, riusa ovunque nella stessa request.

```python
class RequestDataBundle:
    """Cache request-scoped per evitare chiamate Spotify duplicate."""
    def __init__(self, client):
        self.client = client
        self._top_tracks = {}    # {time_range: data}
        self._top_artists = {}   # {time_range: data}
        self._me = None

    async def get_top_tracks(self, time_range="medium_term"):
        if time_range not in self._top_tracks:
            self._top_tracks[time_range] = await retry_with_backoff(
                self.client.get_top_tracks, time_range=time_range
            )
        return self._top_tracks[time_range]

    async def get_top_artists(self, time_range="medium_term"):
        if time_range not in self._top_artists:
            self._top_artists[time_range] = await retry_with_backoff(
                self.client.get_top_artists, time_range=time_range
            )
        return self._top_artists[time_range]
```

**File da modificare**: `backend/app/services/spotify_client.py` o `backend/app/services/data_bundle.py` (nuovo)
**Impatto**: tutti i servizi che chiamano `get_top_tracks`/`get_top_artists`

#### 1.2 Refactor Wrapped endpoint (12-17 → 6-8 chiamate)

Attualmente `GET /api/v1/wrapped` fa:
- `compute_temporal_patterns`: 1 call (`get_recently_played`)
- `compute_taste_evolution`: 6 calls (3x artists + 3x tracks)
- `compute_profile`: 1 call (tracks) + genre cache
- `client.get_top_tracks`: 1 call (DUPLICATO)
- `build_artist_network`: 3 calls (3x artists, DUPLICATI di taste_evolution)

**Fix**: creare `RequestDataBundle`, pre-fetchare 3 periodi tracks + 3 periodi artists = 6 calls. Passare il bundle a tutti i compute functions.

**File**: `backend/app/routers/wrapped.py`, `backend/app/services/taste_evolution.py`, `backend/app/services/audio_analyzer.py`, `backend/app/services/artist_network.py`

#### 1.3 Refactor Profile endpoint (8-14 → 6-8 chiamate)

Attualmente `GET /api/v1/profile` fa:
- `get_me()`: 1 call
- `compute_profile_metrics`: 6 calls (3x artists + 3x tracks) + genre cache
- `compute_taste_map`: 1 call (artists, DUPLICATO)

**Fix**: pre-fetchare con bundle, passare a metrics + taste_map.

**File**: `backend/app/routers/profile.py`, `backend/app/services/profile_metrics.py`, `backend/app/services/taste_map.py`

#### 1.4 Refactor Trends endpoint (gia' efficiente, piccolo fix)

3 calls + genre cache. Solo verifica che non ci siano duplicazioni nascoste.

**File**: `backend/app/routers/analytics.py`, `backend/app/services/audio_analyzer.py`

### Fase 2 — Frontend: rendering progressivo per tutte le pagine

#### 2.1 Pattern generale

Ogni pagina diventa una griglia di sezioni indipendenti. Ogni sezione:
- Mostra skeleton immediatamente
- Fetcha il suo endpoint (o una porzione del risultato)
- Renderizza quando il dato arriva
- Le altre sezioni continuano a caricare indipendentemente

#### 2.2 DashboardPage (3 sezioni indipendenti)

Attualmente: `useSpotifyData('/api/v1/library/top')` + `useSpotifyData('/api/v1/analytics/trends')` + temporal

**Cambio**: gia' quasi corretto (hooks paralleli). Fix: non bloccare il render dei KPI aspettando i trends. Rendere ogni sezione in un `SectionErrorBoundary` con skeleton dedicato.

**File**: `frontend/src/pages/DashboardPage.jsx`

#### 2.3 ProfilePage (sezioni: info, metriche, GenreDNA, TasteMap, stats)

Attualmente: singolo `useSpotifyData('/api/v1/profile')` che blocca tutto.

**Opzione A**: split in 2-3 endpoint (`/profile/info`, `/profile/metrics`, `/profile/taste-map`)
**Opzione B**: singolo endpoint ma il frontend renderizza sezioni man mano che `data` diventa disponibile (il backend gia' ritorna tutto insieme, quindi B non aiuta)
**Scelta**: Opzione A e' piu' pulita ma aumenta le chiamate API. Per ora tenere B — il backend con il bundle sara' piu' veloce.

**File**: `frontend/src/pages/ProfilePage.jsx`

#### 2.4 WrappedPage

Attualmente: blocco totale (`useSpotifyData('/api/v1/wrapped')`), schermata di caricamento.

**Cambio**: convertire a POST/poll pattern come playlist compare. Il backend computa le slides progressivamente, il frontend mostra quelle disponibili.

**File**: `frontend/src/pages/WrappedPage.jsx`, `backend/app/routers/wrapped.py`

#### 2.5 Altre pagine (TasteEvolution, Temporal, ArtistNetwork, Discovery)

Sono gia' relativamente semplici (1-2 endpoint). Il rendering progressivo qui e' meno critico — basta skeleton e section-level rendering.

**File**: tutte le pagine in `frontend/src/pages/`

### Fase 3 — Priorita' API e cache strategy

#### 3.1 Gerarchia dati

```
1. API Spotify (dato fresco) → SEMPRE priorita'
2. Aggiorna DB come side-effect → non bloccare la response
3. Usa DB per storico (RecentPlay, DailyListeningStats, UserSnapshot)
4. Genre cache (7d TTL) → unica eccezione, i generi non sono inline
```

#### 3.2 Cosa NON cachare nel DB

- Top tracks/artists → cambiano frequentemente, l'API li da' direttamente
- Popularity → e' inline nella response API tracks
- Audio features → API deprecated, DB-only OK

#### 3.3 Cosa cachare nel DB

- Generi artisti → API richiede 1 call per artista, cache 7d giustificato
- Ascolti recenti → Spotify buffer 50 items, accumulo nel DB
- Snapshot giornalieri → per trend storici
- Daily stats → per pattern temporali

### Fase 4 — Aggiornamento skill e documentazione

- [ ] Aggiornare `spotify-api-budget` SKILL.md con i nuovi conteggi post-dedup
- [ ] Aggiornare `fastapi-spotify-patterns` SKILL.md rimuovendo ARTIST_GENRE_CAP riferimenti
- [ ] Aggiornare CLAUDE.md con il pattern RequestDataBundle

---

## Ordine di esecuzione raccomandato

```
Fase 1.1 (RequestDataBundle)     ████  fondamento — tutto dipende da questo
Fase 1.2 (Wrapped dedup)         ████  piu' impattante (12→6 calls)
Fase 1.3 (Profile dedup)         ████  secondo piu' impattante (14→6 calls)
Fase 1.4 (Trends verifica)       ██    quick check
Fase 2.2 (Dashboard progressive) ████  pagina principale
Fase 2.4 (Wrapped progressive)   ██████  architettura POST/poll
Fase 2.3 (Profile progressive)   ████
Fase 2.5 (Altre pagine)          ██    minor
Fase 3 (Cache strategy)          ██    documentazione + verifica
Fase 4 (Skills/docs)             ██    ultimo
```

**Stima**: ~25-30 task, eseguibili in 2-3 wave di agenti paralleli.
**Rischio principale**: i servizi (`taste_evolution.py`, `audio_analyzer.py`, `artist_network.py`) hanno firme che assumono un `client` diretto. Il refactoring della firma per accettare un `RequestDataBundle` tocca molti file.

---

## Previous Backlog (preserved)

### Bug aperti
- [ ] GenreDNA (ProfilePage): radar chart con dati finti → wirare frequenze genere reali da `genre_cache`
- [ ] TasteMap (ProfilePage): `audio_features` hardcoded a `None` → wirare da cache DB o rimuovere sezione
- [ ] Wrapped slides: verificare che immagini artista/traccia abbiano fallback funzionante dopo fix UI-3/UI-4

### Popolarita
- [ ] Chiarire con utente cosa ci si aspetta: ranking globale? trend temporale? confronto con media?

### Indagini / ottimizzazioni DB
- [ ] Compound index `(user_id, played_at)` su `recent_plays`
- [ ] N+1 in `sync_recent_plays` (50 SELECT per utente)
