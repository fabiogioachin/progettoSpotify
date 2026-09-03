# Cosa è cambiato dalla bozza iniziale

Confronto fra la bozza del Round 1 e `PLAN.md` finale. Ogni voce cita il rilievo che l'ha generata (`R2G-*` = Gemini, `R2O-*` = Opus interno).

## Aggiunte

| Cosa | Origine |
|---|---|
| **Le due soglie di privacy per l'Opzione B** — soglia di piattaforma (5+ utenti distinti) sommata alla soglia per brano (2+ contributori), più la rimozione del conteggio esatto degli ascolti dalla risposta | R2O-04 + R2G-04, poi corretta due volte (R2O-1-04, R2O-2-02) |
| **Nota nella pagina Privacy**: gli ascolti di un utente possono contribuire a un aggregato visibile ad altri | R2O-04 |
| **Lock condiviso Redis** attorno al refresh della cache, con TTL dimensionato sopra il caso peggiore di `retry_with_backoff` e comportamento **fail-closed** su Redis irraggiungibile (diverso dal fail-open del rate limiter esistente) | R2O-02, R2O-1-03, R2O-1-05 |
| **Stale-while-revalidate**: su refresh fallito con cache già popolata si serve l'ultimo payload valido invece di nascondere la card | R2O-09 |
| **Filtro sugli item con `track` null** (brani rimossi dal catalogo) prima di costruire la risposta | R2O-07 |
| **Fallback di primo popolamento** dentro l'endpoint, perché il solo refresh orario lascerebbe la card invisibile per un'ora dopo il deploy | R2O-1-02 |
| **Il task in background costruisce un proprio `SpotifyClient`**, mai quello dell'handler (che viene chiuso appena l'handler ritorna) — difetto che sarebbe fallito in silenzio | R2O-F-01 (**BLOCKER**) |
| **Campo `global_chart_cache_age_hours` in `/health/detailed`** per rendere visibile uno stallo del refresh | R2O-1-01 |
| **Parametro `market` su `SpotifyClient.get_playlist_items`** (oggi inesistente), incluso nella chiave di cache per-utente del metodo | R2G-2-01, dipendenza scoperta da R2O-2-03 |
| **Ripetizione della verifica preliminare con `market` esplicito** dopo aver esteso il client | R2O-F-03 |
| **Ambiguità nota: tre sezioni "brani più ascoltati" sulla stessa pagina**, due riconducibili a Spotify con scope opposto → revisione del copy obbligatoria | R2O-03 + R2G-04 |
| **Verifica se serve un prop di rank su `TrackCard.jsx`** per l'Opzione B | R2O-F-04 |
| **Nota sul costo della query a scala** (indice su `played_at, track_spotify_id`) | R2G-04 |
| **Chiarimento sugli utenti sospesi** nell'aggregato dell'Opzione B | R2O-08 |
| **Trade-off dichiarati esplicitamente**: nessun tetto di staleness; primo caricamento post-deploy senza card; Opzione B oggi duplica la card accanto | R2O-F-05 |
| Casi di test corrispondenti a ciascuno dei punti sopra | vari |

## Modifiche

| Cosa | Prima | Dopo | Origine |
|---|---|---|---|
| **Aggiornamento della cache (Opzione A)** | Nuovo job APScheduler dedicato, oppure lazy | Refresh **opportunistico** agganciato al job `sync_recent_plays` esistente, col token dell'utente di turno | R2G-01 (**BLOCKER**: un job isolato non ha un token da usare, il progetto non ha client-credentials), R2G-02, R2O-01 |
| **Fonte delle copertine (Opzione A)** | Leggere dalla cache DB (`read_track_images`) come percorso principale | La risposta della playlist include già `album.images`: quella è la fonte primaria, la cache DB solo fallback per i campi mancanti | R2G-03 + R2O-06 (convergenti) |
| **Griglia del layout** | Classe CSS fissa a 3 colonne quando la card esiste nel codice | Numero di colonne calcolato su quante card hanno **davvero dati** — altrimenti resta una colonna vuota visibile a ogni deploy e stallo | R2O-F-02 |
| **Citazione del precedente "Top 50 secondo Spotify"** | Presentato come precedente per l'intera Opzione A | Precisato: vale per il *pattern UI* (selettore disaccoppiato), non per il caching cross-user, che è nuovo | R2O-05 |
| **Il refresh opportunistico "risolve" il punto singolo di rottura** | Presentato come risolto | Dichiarato **auto-risolvente solo con più utenti**: con l'unico utente di oggi il rischio è identico a prima | R2O-1-01 |
| **Struttura del documento** | Sezioni ordinate per round, con l'archeologia delle correzioni inline | Piano consolidato leggibile dall'inizio; cronologia dei round spostata in `PLAN-REVIEW-LOG.md` | merge finale |

## Rimozioni

| Cosa | Perché |
|---|---|
| Il nuovo job APScheduler dedicato per la cache | Sostituito dal refresh opportunistico (R2G-01, R2G-02) |
| L'ipotesi «soglia di privacy sul solo conteggio totale di utenti» | Protegge la card, non il singolo brano (R2O-1-04) |
| L'ipotesi «soglia di privacy solo per brano» | Con 2-3 utenti totali deanonimizza invece di proteggere (R2O-2-02) — sostituita dalla combinazione di entrambe |
| I riferimenti di riga puntuali dentro il piano finale | Spostati o resi meno fragili: i numeri di riga invecchiano a ogni commit |

## Cosa NON è cambiato

L'ambiguità centrale — cosa significa "a livello mondiale" — **resta aperta per scelta**: è una decisione dell'utente, non tecnica, e nessun revisore ha suggerito di risolverla in autonomia. È l'unica cosa che blocca l'implementazione.
