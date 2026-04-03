# Todo

## Pre-refactoring — COMPLETATO (verificato 12/12 nel codice)

- [x] GenreDNA radar: backend manda `{genre, count}`, frontend normalizza su maxCount
- [x] Popularity cache: `items`→`all_items` in upsert + genre cache + rimosso filtro `==0`
- [x] Wrapped slides: `useState` + conditional rendering (no DOM manipulation)
- [x] recent-summary: wirato a ProfilePage con retry 8s
- [x] AdminPage: error feedback handleSuspend/handleCreate + badge `=== true`
- [x] FriendsPage: error feedback handleInvite/handleRemove con auto-clear 5s
- [x] TrendTimeline zero-filter, PlaylistCompare eslint fix, TasteComparison dead prop
- [x] vite-plugin-pwa→deps, psycopg2→dev, html2canvas dynamic import
- [x] Compound index `(user_id, played_at)` + N+1 fix (50 SELECT→1)
- [x] first_play_date consolidato in `get_first_play_date()` (temporal_patterns.py)
- [x] Artist network: genre enrichment via `genre_cache.py` + threshold 15→20
- [x] Login/startup sync: P0_INTERACTIVE + `skip_cache=True` + `raise_on_throttle` + retry 3x
- [x] TasteMap audio_features: non e' un bug, pipeline librosa funzionante
- [x] Playlist analytics polling: rimandato al refactoring (Fase 2.4)

---

## Refactoring API — Piano completo

### Obiettivo

Tutte le pagine devono: (1) caricarsi con skeleton, (2) popolare progressivamente, (3) prioritizzare dati freschi API, (4) aggiornare DB come side-effect, (5) zero chiamate duplicate.

---

### CONTESTO CRITICO: stato attuale misurato

#### Chiamate API per endpoint (audit 2026-04-02)

| Endpoint | Chiamate Spotify | Duplicati | Budget (su 25/30s) |
|----------|-----------------|-----------|---------------------|
| `GET /wrapped` | 13 | 7 (top_artists 3x dup, top_tracks 2x dup) | 52% |
| `GET /profile` | 5 | 1 (top_artists medium dup con taste_map) | 20% |
| `GET /analytics/trends` | 3 + N genre | 0 | 12% + genre |
| `GET /artist-network` | 3 + genre enrichment | 0 | 12% + genre |
| `GET /temporal` | 1 | 0 | 4% |

**Rischio**: `/wrapped` + `/profile` nella stessa sessione = 18 call = 72% del budget in 2 request.

#### Matrice duplicazioni — chi chiama cosa

```
                        top_artists             top_tracks          recently_played
                   short  medium  long     short  medium  long
taste_evolution      X      X      X        X      X      X
profile_metrics      X             X                      X
taste_map                   X
artist_network       X      X      X
compute_trends                               X      X      X
temporal_patterns                                                         X
wrapped router                                      X (direct)
profile router                                                    + get_me()
```

**In `/wrapped`**: taste_evolution(6) + artist_network(3) + temporal(1) + compute_profile(1) + direct(1) + genre = 13 call.
**Con RequestDataBundle**: 3 top_artists + 3 top_tracks + 1 recently_played = **7 call** (-46%).

#### Firme servizi attuali (tutte prendono `client` diretto)

```python
compute_taste_evolution(client: SpotifyClient) -> dict                    # 6 API calls
compute_profile_metrics(db, client: SpotifyClient, user_id) -> dict      # 3 API calls
compute_taste_map(db, client: SpotifyClient, user_id) -> dict            # 1 API call
build_artist_network(client: SpotifyClient, db=None) -> dict             # 3 API calls
compute_temporal_patterns(client: SpotifyClient, db=None, ...) -> dict   # 1 API call
```

#### Cache Redis attuale

| Metodo | TTL | skip_cache |
|--------|-----|-----------|
| `get_top_tracks` | 300s | NO |
| `get_top_artists` | 300s | NO |
| `get_recently_played` | 120s | SI (aggiunto per sync fix) |
| `get_me` | 300s | NO |

**Nota**: la cache 300s su top_tracks/top_artists significa che il RequestDataBundle puo' sfruttarla — la prima chiamata cacha, le successive nella stessa request ottengono il dato cached. MA il bundle e' comunque necessario perche' la cache e' in Redis (round-trip network), mentre il bundle e' in-memory (zero latency).

#### Bottleneck concorrenza

- `asyncio.Semaphore(3)` globale: max 3 chiamate Spotify in-flight contemporaneamente
- `/wrapped` con 13 call: le call si accodano, ~4-5 batch sequenziali da 3
- Con bundle a 7 call: ~2-3 batch — miglioramento ~40% latenza

#### Test coverage GAPS (rischio regressione)

| Servizio | Test | Rischio refactoring |
|----------|------|---------------------|
| taste_evolution | **ZERO** test | ALTO — 6 API call, firma cambia |
| temporal_patterns | **ZERO** test | MEDIO — 1 call, ma logica complessa |
| audio_analyzer | **ZERO** test diretto | MEDIO — usato da trends |
| profile_metrics | 13 test | BASSO |
| taste_map | 10 test | BASSO |
| artist_network | 21 test | BASSO |
| taste_clustering | 34 test | BASSO (pure-compute, non tocca API) |
| background_tasks | 18 test | BASSO |

---

### Prerequisiti — COMPLETATO

- [x] **Test taste_evolution**: 28 test (output structure, periodi, dedup, errori, troncamento, bundle)
- [x] **Test temporal_patterns**: 22 test (streak, daily_minutes, hourly, weekday, DB fallback, first_play_date)
- [x] **Test audio_analyzer**: 18 test (compute_profile, compute_trends, genre aggregation, bundle dedup)

### Fase 1 — Backend: RequestDataBundle — COMPLETATO

- [x] **1.1**: `RequestDataBundle` creato in `backend/app/services/data_bundle.py` (14 test)
- [x] **1.2**: `/wrapped` 13→7 call — bundle wirato a taste_evolution, artist_network, compute_profile, top_tracks diretto
- [x] **1.3**: `/profile` 5→4 call — bundle wirato a profile_metrics, taste_map, get_me
- [x] **1.4**: `/analytics/trends` 6→3 call — audit ha trovato duplicazione nascosta (compute_trends + compute_profile ri-fetchavano). Bundle wirato.

### Fase 2 — Frontend: rendering progressivo — AUDIT COMPLETATO

- [x] **2.2 DashboardPage**: GIA' ottimizzata (3 hook paralleli, per-section skeleton, SectionErrorBoundary)
- [x] **2.3 ProfilePage**: singolo endpoint `/profile` — il bundle backend lo rende gia' piu' veloce. Split in endpoint multipli richiede cambio API → /feature
- [x] **2.4 WrappedPage POST/poll**: implementato. POST avvia task background, GET/{task_id} per polling progressivo. Slide appaiono man mano che i servizi completano. useWrappedTask hook + WrappedStories progressive + shimmer progress bar.
- [x] **2.5 Altre pagine**: gia' semplici (1-2 endpoint), skeleton + section-level gia' presenti

### Fase 3 — Cache strategy — DOCUMENTATO

Gia' applicato in pratica. Gerarchia:
1. API Spotify → dato fresco, sempre priorita'
2. DB update → side-effect non-blocking
3. DB storico → RecentPlay, DailyListeningStats, UserSnapshot
4. Genre cache (7d TTL) → unica eccezione giustificata

### Fase 4 — Documentazione — COMPLETATO

- [x] CLAUDE.md aggiornato con pattern RequestDataBundle
- [x] REFACTOR-LOG.md aggiornato con dettagli completi
- [x] todo.md aggiornato

---

### Fase 5 — Ottimizzazione Redis — COMPLETATO

- [x] **5.1**: Lua script atomico in `spotify_client.py` — consolida cooldown + budget + throttle in 1 EVALSHA (3→1 Redis round-trip per chiamata Spotify)
- [x] **5.2**: `get_window_usage()` ottimizzata — ZCOUNT + ZRANGEBYSCORE LIMIT 0 1 (pipeline, no full member scan)
- [x] **5.3**: 11 nuovi test per Lua script (allowed, cooldown, tier exhausted, user exhausted, window full, fail-open, NOSCRIPT retry)
- [x] **5.4**: Frontend EmptyState convention fix — 6 chart components restituiscono `null` quando vuoti (AudioRadar, GenreTreemap, ListeningHeatmap, MoodScatter, TrendTimeline, ArtistNetwork)
- [x] **5.5**: Skill aggiornate (spotify-api-budget, fastapi-spotify-patterns, react-spotify-patterns)

---

### Fase 6-7 — Playlist cache + Genre enrichment (Sessione 2026-04-03)

**Sintesi**: Implementato `PlaylistMetadata` DB cache permanente per track count playlist (no burst, background sequenziale + polling frontend). Scoperto che Spotify dev mode restituisce `popularity=0, genres=[]` per tutti gli artisti. Implementato fallback a 3 fonti: Spotify → MusicBrainz → Playlist-inferred genres. MusicBrainz arricchisce ~43/83 artisti. Rimossi popularity fallback edges, singleton cluster nascosti, SVG legend filtrata. 493 test.

---

### Prossimi passi

- [ ] Dedup nomi cerchie identici ("Hip Hop / Trap" × 2): usare genere terziario o nome artista top
- [ ] Artisti Ponte / Cerchie: layout gap nella vista Rete (serve scroll lungo per raggiungerle)
- [ ] Playlist inference retry: il warmup Phase 3 si ferma al primo rate limit — aggiungere retry con wait
- [ ] MusicBrainz disambiguation: nomi ambigui (Maz → folk canadese, FISHER → vocal trance)
- [ ] ~34 artisti ancora senza generi: valutare Last.fm API o accettare il limite
- [ ] Test end-to-end Docker: verificare WrappedPage POST/poll con dati reali
