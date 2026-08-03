# Todo

## Storico completato

**Pre-refactoring** (12 bug fix): GenreDNA, popularity cache, wrapped slides, admin/friends error feedback, TrendTimeline, compound index, first_play_date, artist network threshold, login sync.

**Refactoring API** (Fasi 1-4): RequestDataBundle (13→7 call /wrapped, 5→4 /profile, 6→3 /trends), frontend rendering progressivo (WrappedPage POST/poll, skeleton loading), cache strategy documentata.

**Ottimizzazione Redis + Playlist + Genre** (Fasi 5-7): Lua script atomico 3→1 Redis round-trip. PlaylistMetadata DB cache permanente + polling frontend. Spotify dev mode genres=[] → fallback Spotify → MusicBrainz (43/83 artisti) → Playlist-inferred. Singleton cluster nascosti, SVG legend filtrata, MusicBrainz disambiguation. 518 test.

**Budget + Analytics + Polish** (Sessione 2026-04-03): Budget per-user dinamico (1 user = 100% tier). Playlist analytics ordine crescente + retry paziente. WrappedPage crash fix. Cluster dedup cascading 4-pass. Obsidian KG documentazione (6 note).

---

## Fix/Refactor in corso

- [x] B1: Dashboard — generi: donut chart al posto del treemap (phonk 79% nascondeva gli altri generi)
  — **già fatto il 2026-04-03 in `58e39f2`** («donut chart for genres»), mai spuntato qui. Il
  componente disegnava un `PieChart` con `innerRadius="45%"` più una legenda che elenca fino a 12
  generi con la percentuale, quindi un genere dominante non ne nasconde più nessuno. Restava solo
  il nome, che diceva ancora `GenreTreemap`: rinominato in `GenreDonut` il 2026-08-01 (finding I-7
  di `docs/LOOP-BACKLOG.md`).
- [ ] B2: Dashboard — unificare selettore temporale (7gg/30gg/3M/Tutto per tutta la pagina, mapping a Spotify time_range)
- [ ] B3: Dashboard — ThrottleBanner: mostrare budget effettivo per-user, drain progressivo della barra, auto-hide
- [ ] C1: Ecosistema Artisti — fusione grafi KG + Rete con zoom semantico (KG overview, zoom-in rivela connessioni)
- [ ] D1: Callback OAuth — gestire l'errore imprevisto invece della pagina «Internal Server Error»
  — `spotify_callback` in `backend/app/routers/auth.py` rimanda al frontend con `?error=...` su tutti i
  fallimenti previsti, ma non avvolge la parte di persistenza: un errore del database propaga fino al
  gestore globale e lascia l'utente su una pagina nera senza interfaccia né via d'uscita, sull'indirizzo
  di ritorno di Spotify. Visto dal vivo il 2026-08-04 con lo schema mancante. Serve un `except Exception`
  che registri il traceback e rimandi a `?error=server_error`, **più** la verifica che il frontend legga
  davvero quel parametro: oggi `LoginPage.jsx` mostra un avviso solo tramite il flag `serviceDown`.

- [x] D2: Cache Redis — la scadenza raddoppiava senza tetto, e la cache diventava perenne
  — `extend_cache_ttl` in `backend/app/services/api_budget.py` raddoppiava la scadenza di tutte le
  chiavi dell'utente a ogni esaurimento del budget Spotify, partendo ogni volta dal valore già
  raddoppiato. Le chiavi in Redis erano arrivate a 166 milioni di anni: la pagina serviva per sempre
  la stessa copia. Corretto il 2026-08-04 con `MAX_CACHE_TTL = 3600` e due test di regressione.
- [x] D3: Dashboard — «Top 50 Brani» mostra la classifica di Spotify, non quello che ascolti davvero
  — **Chiuso il 2026-08-04**: la sezione principale ora conta gli ascolti registrati
  (`GET /api/v1/library/top-played`, solo database, zero chiamate a Spotify) e segue il periodo
  scelto in alto; accanto resta una seconda sezione con la classifica di Spotify sull'ultimo anno,
  l'unica finestra che lo storico proprio non copre. Ogni riga della prima mostra quante volte hai
  ascoltato il brano. Le copertine si prendono dalla lista Spotify quando il brano compare in
  entrambe, altrimenti restano vuote: recuperarle costerebbe una chiamata per brano.
  — La sezione legge `/me/top/tracks` di Spotify, che è un aggregato lento: misurato il 2026-08-04,
  la lista «1M» aveva **3 brani su 50** in comune con gli ascolti reali della sera prima. Non è un
  difetto dell'app, che riporta fedelmente quello che Spotify restituisce, ma è il motivo per cui la
  classifica sembra vecchia. Ora che lo storico proprio esiste (629 ascolti dal 02/03), si può
  costruire una classifica vera da `recent_plays` — la pagina Pattern Temporali lo fa già nella
  sezione «Brani Più Ascoltati». Da decidere: sostituire la sezione, o affiancarne una seconda
  dichiarando la fonte di ciascuna.

**Recupero storico (2026-08-04)**: importati dal vecchio SQLite di `provaClaude/progettoWrap` 574
ascolti (2–21 marzo), 9 istantanee e 15 giornate di statistiche. La migrazione SQLite→PostgreSQL non
era mai stata eseguita: il database Docker non aveva mai contenuto lo storico. Dettagli in
`lessons.md`.

---

## Sviluppo futuro (PERSISTENTE)

### Discovery page rebuild
- Scoperte recenti: aggiungere contesto (genere, mood, trend, first_play_date, info tracce)
- Sezioni bloccate da dev mode: mood scatter, genre donut, outliers → valutare librosa-only
- Nuova musica: API Recommendations deprecata → content-based filtering da DB, Last.fm similar, nuove uscite
- Playlist pubbliche come fonte di scoperta
- Trend analysis dai dati DB accumulati

### Profile page enhancement
- Confronto periodi (questo mese vs precedente) con trend indicators su KPI cards
- Confronto con amici
- Metriche di fedeltà artista (dati presenti, non esposti)

### Last.fm API integration
- Quarto fallback generi: Spotify → MusicBrainz → Playlist → Last.fm
- API key gratuita, `artist.gettoptags`, 5 req/s, copertura underground superiore
- Target: ridurre i 16 artisti senza generi
