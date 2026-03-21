# Spotify Listening Intelligence — Task List

## Sprint attuale: Daily Stats Pipeline (1C)

### Obiettivo
Popolare `daily_listening_stats` con dati reali da `RecentPlay` — retroattivamente (496 righe
esistenti, 15 giorni) e in avanti ad ogni login.

### Task

#### T1. Verifica sync-on-login (già implementato)
- [ ] Avviare il backend e fare login — **richiede verifica live**
- [ ] Controllare i log per `Login sync` e `nuovi ascolti salvati`
- [ ] Verificare che `recent_plays` cresca dopo un login fresco

#### T2. Estendere `compute_daily_stats` con i campi mancanti
File: `backend/app/services/profile_metrics.py`

- [x] Popolare `avg_popularity`: join `RecentPlay.track_spotify_id` → `TrackPopularity.track_spotify_id`,
      media `TrackPopularity.popularity` per le tracce del giorno. Se nessuna traccia ha
      un valore in `TrackPopularity`, lasciare `None` (non impostare 0 come fallback).
- [x] Popolare `peak_hour`: estrarre `func.strftime('%H', RecentPlay.played_at)`, raggruppare
      per ora, prendere il conteggio massimo. Campo nuovo — aggiungere `peak_hour = Column(Integer, nullable=True)`
      al modello `DailyListeningStats` in `listening_history.py`.
- [x] Popolare `top_artist_of_day`: `Counter(p.artist_name for p in plays).most_common(1)`.
      Campo nuovo — aggiungere `top_artist = Column(String(500), nullable=True)` al modello.
- [x] `top_genre` rimane `None` per ora — nessuna `ArtistCache` disponibile, non inventare dati.
- [x] Aggiornare `get_recent_daily_stats` per includere i nuovi campi nell'output dict.

Nota modello: usare Alembic se il progetto usa migrazioni; altrimenti SQLite `CREATE TABLE IF NOT EXISTS`
ricrea la tabella sullo schema aggiornato al riavvio. Verificare `backend/app/database.py` per capire
come vengono applicate le migrazioni.

#### T3. Funzione di backfill retroattivo
File: `backend/app/services/profile_metrics.py` (nuova funzione) +
      `backend/app/services/background_tasks.py` (chiamante)

- [x] Aggiungere `backfill_daily_stats(db, user_id)` in `profile_metrics.py`:
      - Query date distinte con dati in `RecentPlay` per questo utente
      - Query date già presenti in `DailyListeningStats`
      - Per ogni data mancante, chiamare `compute_daily_stats(db, user_id, target_date)`
      - Loggare: `"Backfill daily stats: user_id=%d — %d date elaborate"`
- [x] La funzione deve essere idempotente: un secondo run non duplica righe (l'upsert
      dentro `compute_daily_stats` già gestisce questo).

#### T4. Integrare il backfill nel flusso di login
File: `backend/app/services/background_tasks.py` + `backend/app/routers/auth.py`

- [x] In `background_tasks.py`, aggiungere `run_daily_aggregates_for_user(user_id)`:
      chiama `compute_daily_stats` per ieri se mancante (versione per-utente di
      `compute_daily_aggregates`).
- [x] In `_try_sync_and_snapshot` (auth.py), dopo il sync e lo snapshot, aggiungere step 3:
      ```
      # 3. Backfill daily stats + ricalcolo ieri se necessario
      async with async_session() as db:
          await backfill_daily_stats(db, user_id)
      ```
      Avvolto in `try/except` con `logger.warning` — non deve mai bloccare il login.
- [x] Verificare che la sequenza rimanga: sync → snapshot → backfill (ordine importante:
      il sync porta nuovi dati prima del calcolo delle statistiche).

#### T5. Verifica end-to-end
- [ ] Riavviare il backend
- [ ] Fare login
- [ ] Controllare i log per `Backfill daily stats`
- [ ] Interrogare il DB: `SELECT count(*) FROM daily_listening_stats` — deve essere > 0
- [ ] Verificare un campione di righe: `avg_popularity` non-null per le date dove
      `TrackPopularity` ha dati, `peak_hour` tra 0-23, `top_artist` valorizzato
- [x] Eseguire: `cd backend && pytest` — 168 passed
- [x] Eseguire: `cd backend && ruff check app/` — All checks passed

---

## Feature Roadmap

### Tier 3 — Analytics Avanzati & Engagement

#### 3A. Milestones & Achievements
- [ ] feat: modello `Achievement` + servizio `achievements.py`
- [ ] feat: `AchievementGrid.jsx` integrato in ProfilePage

#### 3B. Digest Settimanale/Mensile
- [ ] feat: servizio `digest.py` — confronto settimana/mese corrente vs precedente
- [ ] feat: `DigestCard.jsx` in cima alla Dashboard

#### 3C. Wrapped Personalizzato
- [ ] feat: endpoint `GET /api/wrapped/custom?start_date&end_date`
- [ ] feat: `DateRangePicker.jsx` in WrappedPage

#### 3D. Mood Timeline
- [ ] feat: servizio `mood_proxy.py` — genre-mood mapping statico
- [ ] feat: `MoodTimeline.jsx` in TemporalPage o ProfilePage

### Backlog DB (dopo sprint attuale)

#### 1A. Cache top tracks/artists ad ogni visita
- [ ] Tabella `TrackCache` con TTL 24h — popolata da `/api/library/top`
- [ ] Tabella `ArtistCache` con TTL 24h — popolata da `/api/analytics/trends`

#### 1B. Classifiche storiche (TopRanking)
- [ ] Modello `TopRanking(user_id, spotify_id, entity_type, rank, time_range, captured_date)`
- [ ] Popolato dal daily snapshot — abilita "brani in salita/discesa"

#### 1D. Genre tracking storico
- [ ] Modello `DailyGenreStats(user_id, date, genre, play_count, minutes)`
- [ ] Richiede `ArtistCache` (1A) — dipendenza esplicita

#### 2A. Loyalty & Discovery metrics
- [ ] `artist_loyalty_score` da `RecentPlay` (giorni distinti per artista)
- [ ] `discovery_rate`: % brani/artisti nuovi per settimana
- [ ] `mainstream_index`: media popularity ponderata 30 giorni

#### 2B. Listening sessions detection
- [ ] Raggruppa `RecentPlay` in sessioni (gap > 30 min)
- [ ] Modello `ListeningSession(user_id, start_at, end_at, track_count, total_minutes, primary_genre)`

#### 2C. Tendenze settimanali/mensili
- [ ] Modello `WeeklyDigest` + job domenica notte
- [ ] Frontend `DigestCard.jsx`

#### 2D. Year-in-Review (Wrapped da dati locali)
- [ ] Aggregazione annuale da DB locale invece dei soli 3 snapshot Spotify

#### 3A. Indici e performance DB
- [ ] Indice composito su `RecentPlay(user_id, played_at)`
- [ ] Indice su `DailyListeningStats(user_id, date)`
- [ ] Vacuum periodico SQLite

---

## Completato (recente)

- **Daily Stats Pipeline (1C)** (2026-03-21) — `compute_daily_stats` ora calcola avg_popularity (da TrackPopularity), peak_hour, top_artist. Nuova `backfill_daily_stats` popola retroattivamente le lacune. Wired in login flow (sync → snapshot → backfill). 2 nuove colonne DailyListeningStats + migration idempotente.
- **Sync on login + data loss fix** (2026-03-21) — `_try_sync_and_snapshot` sincronizza ascolti recenti al login. Safety net per quando il backend è spento.
- **Bug fix wave + health** (2026-03-21) — 5 bug fix + health scan con 9 auto-fix. 168 test, build + lint clean.
