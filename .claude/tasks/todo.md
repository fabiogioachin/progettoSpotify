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
- [x] B2: Dashboard — unificare selettore temporale (7gg/30gg/3M/Tutto per tutta la pagina, mapping a Spotify time_range)
  — **già fatto il 2026-04-03 in `58e39f2`** («unified time range selector (7gg/30gg/3M/Tutto)»),
  mai spuntato qui. Quel commit ha tolto il selettore che `TrendTimeline` aveva per conto suo e ha
  messo un solo stato `range` in cima a `DashboardPage.jsx`, tradotto nei periodi di Spotify da
  `RANGE_TO_SPOTIFY`. Controllato il 2026-11-24 leggendo la pagina intera: KPI, grafico dei
  minuti, radar audio, ciambella dei generi e le due classifiche sui tuoi ascolti seguono tutti
  quel `range`; `GenreDonut`, `AudioRadar` e `TrendTimeline` non hanno un selettore proprio. Due
  card non lo seguono, per scelta dichiarata nella pagina: la Top 50 di Spotify ha un suo
  selettore coi tre periodi veri di Spotify (`354bcc9`, 2026-08-04, che ha portato i periodi a
  cinque, aggiungendo 1Y), e la classifica mondiale Last.fm esiste solo al presente.
- [x] B3: Dashboard — ThrottleBanner: mostrare budget effettivo per-user, drain progressivo della barra, auto-hide
  — **già fatto il 2026-04-03 in `58e39f2`** («ThrottleBanner with effective per-user budget and
  progressive drain»), mai spuntato qui. Controllato il 2026-11-24 leggendo il codice: il backend
  scrive nell'intestazione `X-RateLimit-Usage` il budget calcolato da `get_effective_budget()`
  (quota per utente attivo, non il 25 fisso di Spotify); `lib/api.js` la legge e la passa al
  banner con l'evento `api:usage`. Il 25 nel banner è solo lo stato iniziale, prima della prima
  risposta. Fra una risposta e l'altra la barra si svuota da sola nel tempo della finestra, e il
  banner si nasconde sotto il 60% di carico; il conto alla rovescia in basso sparisce a finestra vuota.
- [x] B4: Dashboard — classifiche mondiali. **Fatto il 2026-09-03**, commit `f3c7e0a` e `7cc0d7e`,
  ma non come il piano prevedeva: la fonte scelta non esisteva più. La playlist editoriale
  `37i9dQZEVXbMDoHDwVN2tF` risponde 404 in dev mode, come ogni playlist di proprietà di Spotify;
  e il ripiego (l'indice `popularity`) è risultato anch'esso sparito, assente dalle chiavi della
  risposta. Entrambe le card girano ora su **Last.fm**, decisione dell'utente di farle tutte e due:
  «I brani più ascoltati nel mondo» (classifica vera, non segue il periodo e lo dichiara) e
  «Popolari nel mondo, fra i tuoi» (i tuoi brani pesati sugli ascolti mondiali, segue il periodo).
  Verificate dal vivo coi dati veri. Evidenza in `plan-global-top-tracks/GATE-1-RESULT.md` e
  `GATE-2-RESULT.md`; slice in `phases.md`.
- [x] B4-bis: `track_popularity` era una tabella morta (0 righe). **Deciso il 2026-11-24: si toglie,
  non si ripopola da Last.fm.** Perché: `popularity` è un punteggio 0-100 dell'algoritmo interno di
  Spotify, che nessun dato in nostro possesso permette di ricalcolare; Last.fm `track.getInfo` dà
  invece ascolti mondiali assoluti, un'altra scala, e funziona bene (59 brani su 60 con un numero,
  tabella `track_world_playcount`), ma è già usato dove serve, dalla card «Popolari nel mondo».
  Metterlo in `track_popularity` avrebbe voluto dire chiamate Last.fm nel giro orario e una media
  0-100 che non lo è più. Fatto: tolta la scrittura dal giro orario (`background_tasks.py`), la
  popolarità media del giorno resta vuota invece di leggere la tabella (`profile_metrics.py`), e un
  test che torna rosso se la scrittura rientra (`test_background_tasks.py`, rosso prima del taglio).
  Suite 600 verde, ruff pulito.
- [ ] B4-quater: finire di togliere `track_popularity`. `popularity_cache.py` resta solo perché tre
  file lo importano (`routers/library.py`, `routers/playlists.py`, `services/audio_analyzer.py`, più
  i loro test); poi la pulizia in `data_retention.py`, il modello `TrackPopularity`, una migrazione
  che cancella la tabella, la colonna `avg_popularity` delle statistiche giornaliere. Fuori dallo
  scope di B4-bis.
- [ ] B4-ter: sorvegliare l'età della classifica mondiale. Il campo `global_chart.age_hours` c'è già
  in `/health/detailed`, ma nessuno lo guarda: senza una soglia, un rinfresco fermo da settimane
  resta invisibile perché la card continua — per scelta — a mostrare il dato vecchio.
- [x] C1: Ecosistema Artisti — fusione grafi KG + Rete con zoom semantico (KG overview, zoom-in rivela connessioni)
  — **già fatto il 2026-04-03 in `58e39f2`** («merged KG+Rete into single view with semantic zoom»),
  lo stesso commit di B1, B2 e B3, mai spuntato qui. Quel commit ha tolto da `ArtistNetworkPage.jsx`
  i due bottoni «Rete» / «Knowledge Graph» che sceglievano un grafo alternativo all'altro, e ha
  introdotto in `ArtistNetwork.jsx` un solo grafo con `zoomBlend`, che vale 0 sotto la scala 1.3 e 1
  sopra la 2.2. Controllato il 2026-11-24 leggendo dove quel valore agisce, non solo il nome: a
  zoom pieno i nodi-genere scendono al 15% di opacità, i nodi-artista passano dal raggio 3-8 al
  6-22, gli archi fra artisti compaiono (a zoom 0 hanno opacità zero) e le etichette degli artisti
  medi appaiono. Il backend manda davvero `genre_nodes` e `genre_edges` (`build_artist_network`,
  fino a 3 generi per cerchia): provato chiamando il servizio con tre artisti, che restituisce 3
  nodi-genere e 5 archi. I nodi-genere esistono solo se gli artisti hanno generi, cioè quanto copre
  MusicBrainz; non verificato dal vivo nel browser.
- [x] E1: La CI è rossa su `master`, e nessuno se n'è accorto — `ruff check app/` esce 1 con due
  rilievi `F841`, cioè variabili assegnate e mai usate: `synced` in `backend/app/main.py:721` e
  `sync_ok` in `backend/app/routers/auth.py:363`. Vengono entrambe dal commit `0d67cb7` del
  2026-04-03, quindi il lavoro `backend-lint` del workflow CI fallisce anche in remoto da allora:
  la versione di ruff è la stessa fissata in `requirements-dev.txt` (0.9.3) e non c'è nessun file di
  configurazione che disattivi la regola. Sono due righe, ma vanno guardate col codice intorno: in
  entrambi i casi la variabile sembra il residuo di un ramo che doveva riportare l'esito del sync,
  quindi o serviva e manca il suo uso, o è zavorra. Trovato il 2026-09-14 dal loop di sviluppo, che
  non l'ha toccato perché fuori dall'item del giro.
  — **Chiuso il 2026-11-24**: le due variabili erano zavorra e sono state tolte. Ogni fallimento del sync è già registrato nel suo ramo `except`. `ruff check app/` (0.9.3) esce 0, e i test restano 599 su 599.
- [x] D1: Callback OAuth — gestire l'errore imprevisto invece della pagina «Internal Server Error»
  — `spotify_callback` in `backend/app/routers/auth.py` rimanda al frontend con `?error=...` su tutti i
  fallimenti previsti, ma non avvolge la parte di persistenza: un errore del database propaga fino al
  gestore globale e lascia l'utente su una pagina nera senza interfaccia né via d'uscita, sull'indirizzo
  di ritorno di Spotify. Visto dal vivo il 2026-08-04 con lo schema mancante. Serve un `except Exception`
  che registri il traceback e rimandi a `?error=server_error`, **più** la verifica che il frontend legga
  davvero quel parametro: oggi `LoginPage.jsx` mostra un avviso solo tramite il flag `serviceDown`.
  — **Chiuso il 2026-11-24**: in `spotify_callback` la parte dalla ricerca dell'utente al commit è ora dentro un `try/except Exception`, che registra il traceback, annulla la transazione e rimanda a `?error=server_error`. `LoginPage.jsx` non leggeva `?error=` per nessun codice: ora mostra un messaggio per ciascuno (anche `access_denied` di Spotify) e uno generico per i codici ignoti, nello stesso riquadro di `serviceDown`. `ruff check app/` esce 0, i test restano 599 su 599, `npm run lint` e `npm run build` escono 0. Nessun test di regressione dedicato al callback: non verificato dal vivo nel browser.

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
