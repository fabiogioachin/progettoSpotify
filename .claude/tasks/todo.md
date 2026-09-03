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
- [x] B4: Dashboard — classifiche mondiali. **Fatto il 2026-09-03**, commit `f3c7e0a` e `7cc0d7e`,
  ma non come il piano prevedeva: la fonte scelta non esisteva più. La playlist editoriale
  `37i9dQZEVXbMDoHDwVN2tF` risponde 404 in dev mode, come ogni playlist di proprietà di Spotify;
  e il ripiego (l'indice `popularity`) è risultato anch'esso sparito, assente dalle chiavi della
  risposta. Entrambe le card girano ora su **Last.fm**, decisione dell'utente di farle tutte e due:
  «I brani più ascoltati nel mondo» (classifica vera, non segue il periodo e lo dichiara) e
  «Popolari nel mondo, fra i tuoi» (i tuoi brani pesati sugli ascolti mondiali, segue il periodo).
  Verificate dal vivo coi dati veri. Evidenza in `plan-global-top-tracks/GATE-1-RESULT.md` e
  `GATE-2-RESULT.md`; slice in `phases.md`.
- [ ] B4-bis: `track_popularity` è una tabella morta — 0 righe a fronte di 469 brani distinti, perché
  il giro orario legge un campo che Spotify non manda più. Va decisa: rimuoverla insieme al codice
  che la scrive e la legge (`popularity_cache.py`, il ramo in `background_tasks.py`, il filtro in
  `profile_metrics.py`), oppure ripopolarla da Last.fm. Finché resta così, ogni lettura di
  `popularity` in giro per il codice ritorna vuoto in silenzio.
- [ ] B4-ter: sorvegliare l'età della classifica mondiale. Il campo `global_chart.age_hours` c'è già
  in `/health/detailed`, ma nessuno lo guarda: senza una soglia, un rinfresco fermo da settimane
  resta invisibile perché la card continua — per scelta — a mostrare il dato vecchio.
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
  ascoltato il brano. Le copertine hanno una cache permanente (`track_metadata`) riempita in
  sottofondo, una chiamata per brano, al massimo i 50 visibili per volta: la pagina richiede la
  lista finché non sono tutte a posto, con un segno che impedisce alle code di moltiplicarsi.
  I periodi sono cinque (7gg / 1M / 3M / 1Y / Tutto) e si contano tutti sugli ascolti registrati;
  la sezione di Spotify ha il suo selettore coi suoi tre nomi veri, perché tre mesi e un anno
  Spotify non li calcola.
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
- **Il ponte esiste già** dal 2026-09-03: `backend/app/services/lastfm_client.py`, chiave in
  `LASTFM_API_KEY`, già configurata. Manca solo il metodo `artist.getTopTags` da aggiungergli.
- Quarto fallback generi: Spotify → MusicBrainz → Playlist → Last.fm
- Target: ridurre i 16 artisti senza generi
