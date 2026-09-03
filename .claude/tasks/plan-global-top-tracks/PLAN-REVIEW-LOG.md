# PLAN-REVIEW-LOG.md — Card "I brani più ascoltati" (globale)

## Round 2.1

revisione fatta da Gemini+Opus (solo ripiego interno). non disponibili: Codex (limite d'uso raggiunto, "Sep 10th, 2026 3:31 AM" secondo l'errore CLI restituito il 2026-09-02).

**Verdetto complessivo: REVISE** (peggiore fra i due: Gemini REVISE con 1 BLOCKER, Opus REVISE con 4 MAJOR).

Rilievi ricevuti: 4 da Gemini (`.audit/REVIEW-gemini.json`: R2G-01 BLOCKER, R2G-02 MAJOR, R2G-03/R2G-04 MINOR), 9 da Opus (`.audit/REVIEW-opus.json`: R2O-01..04 MAJOR, R2O-05..09 MINOR).

### Convergenze (trovate da entrambi i revisori indipendentemente)

- **Cache immagini superflua per Option A** — R2G-03 e R2O-06: se `GET /playlists/{id}/items` restituisce già `album.images`, il giro sulla cache DB (`read_popularity_cache`/`read_track_images`) è superfluo come fonte primaria.
- **Confusione fra card "a matrice Spotify"** — R2G-04(2) e R2O-03: con la nuova card la Dashboard ha tre sezioni "brani più ascoltati", due delle quali entrambe riconducibili a Spotify (personale-algoritmica vs globale-editoriale) con nomi simili.
- **Privacy/consenso per Option B** — R2G-04(3) e R2O-04: togliere il filtro utente espone dati aggregati di altri utenti senza che il piano discuta consenso o rischio di re-identificazione con pochi utenti.

### Decisioni (accettate ora per produrre il delta da ri-sottoporre; il merge formale con motivazioni complete è in `PLAN.md` finale)

| ID | Decisione | Come |
|---|---|---|
| R2G-01 (BLOCKER) | **VALID** | Il job schedulato in Step 10 non aveva un token da usare. Risolto sostituendo "nuovo job APScheduler" con refresh opportunistico agganciato al job `sync_recent_plays` già esistente (gira per ogni utente, stesso pattern del warmup generi) — nessun service-account dedicato, nessun nuovo job. |
| R2G-02 (MAJOR) | **VALID**, risolto dalla stessa modifica | APScheduler esiste già nel progetto (4 job documentati in CLAUDE.md); il punto valido non era "non introdurre scheduler" ma "non introdurre un nuovo job apposta per una card" — risolto agganciandosi a un job esistente invece di crearne uno nuovo. |
| R2O-01 (MAJOR) | **VALID**, risolto dalla stessa modifica | Nessun singolo utente-token è più un punto di rottura: il refresh lo fa "il prossimo utente il cui sync gira", con fallback su ultima cache buona se nessun refresh riesce. |
| R2O-02 (MAJOR) | **VALID** | Aggiunto lock cross-user (Redis SET NX, TTL breve) attorno al refresh, per evitare fetch concorrenti duplicate quando più sync utente scadono vicini nel tempo. |
| R2O-03 (MAJOR) | **VALID** | Aggiunto step esplicito di differenziazione copy fra le tre sezioni. |
| R2O-04 / R2G-04(3) (MAJOR/MINOR, convergente) | **VALID** | Aggiunta soglia minima utenti distinti per mostrare l'aggregato Option B, e nota privacy esplicita. |
| R2O-05 (MINOR) | **VALID** | Riformulata la citazione del precedente "Top 50 secondo Spotify": vale per il pattern UI, non per l'architettura di caching. |
| R2G-03 / R2O-06 (MINOR, convergente) | **VALID** | Step 5 (verifica preliminare) ora include il controllo esplicito se il payload della playlist include già le immagini; se sì, fonte primaria diretta, DB solo fallback. |
| R2O-07 (MINOR) | **VALID** | Aggiunto filtro esplicito su item con `track` assente/null nello Step 6. |
| R2O-08 (MINOR) | **VALID** | Aggiunta una riga di chiarimento: l'aggregato Option B conta tutte le righe storiche indipendentemente dallo stato di sospensione corrente. |
| R2O-09 (MINOR) | **VALID** | Aggiunto comportamento stale-while-revalidate: su fallimento di un refresh con cache già popolata, si serve l'ultimo payload valido. |
| R2G-04(1) (MINOR) | **VALID** | Aggiunta nota su indice DB per Option B, dichiarata non urgente al volume attuale (874 righe). |

Nessun rilievo scartato come INVALID in questo round — tutti e 13 erano fondati, alcuni si sono risolti a vicenda con un'unica modifica architetturale (il refresh opportunistico agganciato a `sync_recent_plays`).

### Applicato

`PLAN.draft.md` aggiornato in-place con le modifiche sopra (non è stata creata una copia `PLAN.v2.md` a questo stadio: l'unico file di piano resta `PLAN.draft.md` fino alla chiusura del Round 2 iterativo).

## Round 2.2 (delta)

revisione fatta da Gemini (conversazione nuova, solo sezioni cambiate). Opus in corso (continuazione dell'agente del giro 1, risposta ancora da arrivare al momento di questa scrittura — vedi sezione successiva quando disponibile).

**Gemini: VERDICT APPROVED.** Confermati chiusi tutti i 4 punti del giro 1 (`"I 4 punti sollevati nel Round 1 [...] sono stati affrontati e pienamente risolti [...] Nessun blocco ulteriore identificato."`). Un rilievo nuovo, non bloccante:

| ID | Decisione | Come |
|---|---|---|
| R2G-2-01 (MINOR, edge_case) | **VALID** | Il refresh usa il token di un utente specifico per fetchare la playlist globale: senza un `market` esplicito, Spotify applica il paese di quell'utente (track relinking diverso per paese). Applicato: `market` fisso e deterministico nella chiamata a `get_playlist_items`, non implicito dal token. |

**Opus (continuazione dello stesso agente del giro 1): VERDICT REVISE**, 5 rilievi nuovi — tutti sulle correzioni appena applicate, non sul piano originale. Prova diretta che "il secondo giro non è facoltativo": senza questo giro, tre di questi difetti (SPOF ancora reale con 1 utente, nessun popolamento iniziale, soglia privacy alla granularità sbagliata) sarebbero rimasti nel piano finale.

| ID | Decisione | Come |
|---|---|---|
| R2O-1-01 (MAJOR) | **VALID** | Il fix di R2O-01 (refresh via altro utente) non risolve nulla con un solo utente registrato oggi — dichiarato esplicitamente come limite non risolto, non nascosto. Aggiunto un campo di osservabilità (`global_chart_cache_age_hours` in `/health/detailed`) per rendere visibile uno stallo. |
| R2O-1-02 (MAJOR) | **VALID** | Il refresh opportunistico da solo lascia la card invisibile per un'ora o più dopo il deploy. Aggiunto un fallback lazy-con-lock al primo miss dentro l'endpoint stesso. |
| R2O-1-03 (MAJOR) | **VALID** | TTL del lock non validato contro il caso peggiore di `retry_with_backoff`. Aggiunta indicazione di dimensionamento (margine sopra 30s dichiarati dalla skill budget) o rinnovo del TTL a ogni retry. |
| R2O-1-04 (MAJOR) | **VALID**, il più sostanziale | La soglia sul conteggio utenti di piattaforma non protegge il singolo brano. Riscritta come soglia per-brano (`HAVING COUNT(DISTINCT user_id) >= 2`) più rimozione del `play_count` esatto dalla risposta dell'endpoint globale. |
| R2O-1-05 (MINOR) | **VALID** | Comportamento del lock su Redis irraggiungibile non dichiarato; a differenza del rate limiter (fail-open per policy), questo lock deve essere fail-closed per non riaprire lo stampede che doveva chiudere. |

Nessun rilievo scartato come INVALID. Gemini non è stato ri-consultato su questo giro (nessuno dei 5 punti contraddice quanto aveva approvato in Round 2.2; sarà comunque incluso nel merge di Round 3 con la propria dichiarazione di provenienza).

## Round 2.3 (delta)

revisione fatta da Opus (continuazione dello stesso agente, focalizzata sui 5 punti del giro precedente). Gemini non ri-consultato in questo giro specifico.

**Opus: VERDICT REVISE**, 4 rilievi nuovi (3 MAJOR, 1 MINOR) — di nuovo sulle correzioni appena applicate, non sul piano precedente.

| ID | Decisione | Come |
|---|---|---|
| R2O-2-01 (MAJOR) | **VALID** | Il fallback lazy-con-lock non dichiarava cosa fa la richiesta che perde il lock, e rischiava di reintrodurre la latenza Spotify nel ciclo richiesta/risposta. Precisato: chi non acquisisce il lock ritorna subito senza dati; chi lo acquisisce lancia un task in background (sessione DB propria, invariante 4) e ritorna anch'esso subito. |
| R2O-2-02 (MAJOR) | **VALID, il più sostanziale di tutto il Round 2** | La soglia per-brano introdotta al giro precedente, **da sola**, con 2-3 utenti totali produce deanonimizzazione quasi certa invece di protezione (matematica verificata da Opus: con 2 utenti, ogni brano visibile prova che l'unico altro utente l'ha ascoltato). Corretto sommando una soglia di piattaforma (default 5+) **prima** della soglia per-brano, non in sua sostituzione. |
| R2O-2-03 (MAJOR) | **VALID**, verificato sul codice reale | `get_playlist_items` non ha oggi un parametro `market` (letto `spotify_client.py`) e il file non era in "File impattati". Aggiunto alla lista, con la nota che va estesa anche la chiave di cache per-utente esistente del metodo. |
| R2O-2-04 (MINOR) | **VALID** | Il file router di `/health/detailed` mancava da "File impattati" nonostante il nuovo campo fosse già deciso nel testo. Aggiunto. |

Nessun rilievo scartato come INVALID nemmeno in questo giro. Pattern che si ripete a ogni giro: ogni round di delta review trova difetti reali nelle correzioni del round precedente, mai negli step originali — prova diretta a favore della regola "il secondo giro non è facoltativo".

## Round 2.4 (delta) — tentativo fallito e ripetuto

Primo tentativo: continuazione dello stesso agente Opus (a9661d79195fce0ae), focalizzata sui 4 punti del giro 2.3. **Fallito**: "Agent stalled: no progress for 600s (stream watchdog did not recover)" — un guasto tecnico, non un verdetto. Per la regola globale "tool esterno fallito: probe fresca, mai solo timestamp", ritentato con una **dispatch nuova** (agente fresco, senza continuità di contesto con le istanze precedenti — verosimilmente lo stallo era legato alla crescita di contesto attraverso 3 continuazioni consecutive, non a un problema del piano).

**Opus (dispatch fresca): VERDICT REVISE**, 5 rilievi (1 BLOCKER, 1 MAJOR, 3 MINOR) — di nuovo trovati leggendo a mente fresca l'intero piano maturato dai 3 round precedenti, non ripetendo rilievi già chiusi.

| ID | Decisione | Come |
|---|---|---|
| R2O-F-01 (BLOCKER) | **VALID**, il più serio di tutto il Round 2 | Il task in background del fallback lazy (fix di R2O-2-01) rischiava di riusare per closure il `SpotifyClient` dell'handler HTTP che l'ha generato — chiuso nel `finally` non appena l'handler ritorna, che qui accade subito per design. La fetch fallirebbe silenziosamente, mascherata dal refresh orario che comunque la popola più tardi: un difetto che nessun test manuale avrebbe scoperto. Corretto: il task costruisce un proprio `SpotifyClient` con una propria sessione DB, mai quello del genitore. |
| R2O-F-02 (MAJOR) | **VALID** | Il grid statico a 3 colonne (Ambiguità nota 2) e la card che può essere legittimamente assente a lungo (Ambiguità nota 3, Option A) erano coerenti singolarmente ma non lette insieme: producono una colonna vuota visibile a ogni deploy e stallo. Corretto: il numero di colonne va calcolato in base a quante card hanno davvero dati, non a una classe fissa. |
| R2O-F-03 (MINOR) | **VALID** | La verifica preliminare dell'ID playlist (Step 5) gira senza `market`, che non esiste ancora sul client in quel punto della sequenza — va ripetuta con `market` esplicito dopo lo Step 6, prima di chiudere l'assunzione #7 definitivamente. |
| R2O-F-04 (MINOR) | **VALID** | Non è confermato se "solo posizione in classifica" (Option B) richieda un prop di rank su `TrackCard.jsx` che oggi non esiste — se sì, va aggiunto a "File impattati" per Option B, in contraddizione con "nessuna modifica prevista" che vale solo per Option A. |
| R2O-F-05 (MINOR) | **VALID** | Il comportamento "nessun tetto massimo di staleness" (stale-while-revalidate senza scadenza) non era mai dichiarato come scelta consapevole. Aggiunta la dichiarazione esplicita del trade-off accettato. |

Nessun rilievo scartato come INVALID. Questo è il quarto giro completato della scala iterativa (il tentativo fallito non conta come giro, essendo un guasto tecnico senza verdetto). Resta un giro disponibile prima del tetto di 5 previsto dal protocollo.

## Round 2.5 — non completato, e perché non blocca

Il quinto giro di verifica sulle correzioni di R2O-F-01..05 è stato dispatchato ma **non ha prodotto un verdetto**: il tool è tornato con un errore interno (`Tool result missing due to internal error`), il secondo guasto tecnico su questo agente dopo lo stallo del giro 2.4. Nel frattempo l'utente ha chiesto esplicitamente di chiudere e passare al merge finale.

**Cosa questo significa, detto con precisione**: le cinque correzioni del giro 2.4 (client Spotify proprio nel task in background, griglia dinamica, ri-verifica con `market`, prop di rank da confermare, staleness dichiarata) sono state applicate **senza una rilettura avversariale successiva**. Tutte le altre correzioni del piano hanno superato almeno un giro di verifica; queste cinque no. Non è un motivo per non implementare — sono correzioni puntuali, ciascuna derivata da un rilievo già argomentato — ma chi implementa le guardi con un occhio in più, perché il precedente dice qualcosa: **ogni giro di questa revisione ha trovato difetti nelle correzioni del giro prima, mai negli step originali.**

## Riepilogo del Round 2

`revisione fatta da Gemini+Opus (quest'ultimo interno, solo ripiego). non disponibili: Codex (limite d'uso raggiunto fino al 10/09/2026).`

**Nessun revisore esterno indipendente ha esaminato gli ultimi due giri**: Gemini ha partecipato ai giri 1 e 2, gli altri tre sono stati fatti dal solo ripiego interno, che gira sullo stesso modello dell'orchestratore e ne condivide i punti ciechi.

| Giro | Revisori | Verdetto | Rilievi | Esito |
|---|---|---|---|---|
| 2.1 | Gemini + Opus | REVISE (1 BLOCKER, 5 MAJOR) | 13 | tutti accolti |
| 2.2 | Gemini | **APPROVED** | 1 MINOR nuovo | accolto |
| 2.3 | Opus | REVISE (5 rilievi) | 5 | tutti accolti |
| 2.4 | Opus (dispatch fresca dopo stallo) | REVISE (1 BLOCKER, 1 MAJOR, 3 MINOR) | 5 | tutti accolti |
| 2.5 | Opus | — | — | **guasto tecnico, nessun verdetto** |

**Totale: 27 rilievi, 27 accolti, 0 respinti** (dettaglio in `REJECTED-SUGGESTIONS.md`).

Due guasti tecnici sullo stesso ruolo: uno stallo di 600s al giro 2.4 (risolto con una dispatch fresca invece di una continuazione — plausibilmente la crescita di contesto attraverso continuazioni consecutive) e un errore interno del tool al giro 2.5.

## Round 3 — merge finale

Prodotti: `PLAN.md` (piano consolidato), `CHANGES-FROM-DRAFT.md` (diff strutturato con la provenienza di ogni modifica), `REJECTED-SUGGESTIONS.md` (nessun respinto, con l'analisi del perché non è un buon segno di per sé). `PLAN.draft.md` conservato come traccia della bozza corretta round per round.

## Round 4 — ambiguità risolta

Una sola ambiguità aperta, sotto le 5 previste dal protocollo (nessuna escalation "piano troppo ambiguo"). Era una decisione di prodotto, non tecnica: nessun revisore ha suggerito di risolverla in autonomia.

**Posta all'utente il 03/09/2026, risposta: Opzione A** — la classifica globale vera di Spotify, letta dalla playlist editoriale pubblica "Top 50 - Global".

Conseguenza accettata con la scelta: **la card non seguirà il selettore di periodo della dashboard**. I due vincoli della richiesta originale ("mondiale" + "nell'arco temporale della dashboard") non erano soddisfacibili insieme, perché quella playlist rappresenta solo "adesso" e Spotify non espone finestre storiche. Il piano finale lo dichiara in cima come conseguenza diretta della scelta, non come compromesso implementativo, e prescrive di dirlo in UI — stesso trattamento già riservato alla sezione "Top 50 secondo Spotify".

## Round 5 — piano finale

`PLAN.md` riscritto con la decisione applicata: gli step condizionali sono diventati una sequenza unica, le Opzioni B e C sono in coda al documento come alternative scartate con la loro motivazione. `PLAN.draft.md` resta come traccia della bozza corretta round per round, e conserva il ragionamento completo sull'Opzione B (incluse le due soglie di privacy) nel caso la verifica dell'ID playlist fallisca e la scelta vada riaperta.
