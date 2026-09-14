# Rapporto di salute del progetto

**Generato**: 2026-09-14 — **Progetto**: Spotify Listening Intelligence (progettoWrap)
**Stack**: FastAPI 0.115 + React 18 + Vite 6 + PostgreSQL 16 + Redis 7
**Tipo**: rigenerazione con delta sul rapporto precedente del 2026-04-01

## In breve

**I 21 rilievi del rapporto vecchio sono tutti chiusi.** Li ho ricontrollati uno per uno sul codice
di oggi: nessuno è ancora vero. Il rapporto precedente era quindi interamente obsoleto, e chi lo
avesse aperto per decidere cosa fare avrebbe lavorato su una lista di problemi che non esistono più.

Al loro posto ne resta **uno solo, nuovo e vero**: la verifica automatica su `master` è rossa, e lo
è da cinque mesi senza che nessuno se ne sia accorto.

| Misura | Valore |
|---|---|
| Rilievi del rapporto vecchio | 21 |
| Chiusi | 21 |
| Ancora veri | 0 |
| Nuovi trovati oggi | 1 confermato, 1 informativo |

### Perché il rapporto vecchio era così fuori fuoco

L'ultima volta che il file è stato toccato è il commit `0d67cb7` del **2026-04-03**. È lo stesso
commit che ha introdotto il difetto nuovo descritto qui sotto. Da allora il rapporto è rimasto fermo
mentre il codice andava avanti: cinque mesi di lavoro — fra cui i nove rilievi dell'ispezione
frontend del 2026-07-30, chiusi uno per giro da questo loop — hanno smontato la sua lista senza che
lui lo registrasse. Un controllo a campione del 2026-07-29 ne dava già 15 su 21 chiusi; oggi sono
21 su 21.

## Il rilievo nuovo

### E1 — `master` non passa la verifica automatica, e non lo fa da cinque mesi

**Gravità: alta.** Non perché il codice sia rotto — l'applicazione funziona — ma perché una verifica
sempre rossa non protegge più nulla. Chi introduce un difetto vero vede lo stesso semaforo rosso di
sempre e non ha modo di distinguerlo.

Il lavoro `backend-lint` del flusso di verifica esegue `ruff check app/`, che esce con codice 1 su
due rilievi `F841`, cioè variabili assegnate e mai lette:

| File | Riga | Variabile |
|---|---|---|
| `backend/app/main.py` | 721 | `synced` |
| `backend/app/routers/auth.py` | 363 | `sync_ok` |

Sono la stessa cosa scritta due volte. In entrambi i casi siamo dentro un ciclo che riprova fino a
tre volte a sincronizzare gli ascolti recenti: al primo successo la variabile viene messa a vero e
subito dopo un `break` esce dal ciclo. Il `break` porta già da sé l'informazione «è andata bene»,
quindi la variabile non viene mai riletta — né lì né più avanti nella funzione.

**Non è un difetto di comportamento**: togliere le due righe non cambia ciò che l'applicazione fa.
È zavorra, e va guardata col codice intorno prima di cancellarla, perché in entrambi i punti la
variabile ha l'aria del residuo di un ramo che doveva riportare l'esito della sincronizzazione a chi
chiamava. Delle due l'una: o quell'uso serviva e manca, o la variabile va via.

Entrambe arrivano dal commit `0d67cb7` del 2026-04-03, quindi il lavoro `backend-lint` fallisce
anche in remoto da quella data. La versione dello strumento è la stessa fissata in
`requirements-dev.txt` (ruff 0.9.3) e non c'è nessun file di configurazione che disattivi la regola:
il rosso è vero, non un effetto di versione.

**Già in coda**: la voce E1 di `.claude/tasks/todo.md`, aperta il 2026-09-14.

### Informativo — la formattazione automatica diverge su 10 file

`ruff format app/ --check` segnala che riformatterebbe 10 file su 68, fra cui
`app/routers/temporal.py`, `app/services/background_tasks.py`, `app/services/taste_map.py` e
`app/services/temporal_patterns.py`.

**Non è un difetto e non blocca niente**: il flusso di verifica esegue `ruff check`, mai
`ruff format --check`, quindi questa divergenza non ha nessun effetto sul semaforo. La riporto solo
perché chi legge `CLAUDE.md` trova `ruff format` fra i comandi del progetto e potrebbe aspettarsi
che sia sorvegliato. Non lo è. Se lo si vuole sorvegliare è una decisione da prendere, non un guasto
da riparare.

## I 21 rilievi vecchi, uno per uno

Ogni riga è stata verificata sul codice di oggi. La colonna «prova» dice dove ho guardato.

### Erano critici o alti

| ID | Cosa diceva | Verdetto | Prova |
|---|---|---|---|
| DEP-9 | `vite-plugin-pwa` fra le dipendenze di sviluppo, ma serve alla compilazione | **Chiuso** | `frontend/package.json:21` — ora sta in `dependencies` |
| DEAD-1 | Campo `"historical": []` sempre vuoto nella risposta delle tendenze | **Chiuso** | `backend/app/routers/analytics.py:42` — la risposta è `{"current": trends}` |
| DEAD-2 | `GET /api/v1/library/recent-summary` senza nessun chiamante | **Chiuso** | `frontend/src/pages/ProfilePage.jsx:20` — ora lo chiama |
| UI-1 | Il radar dei generi usava valori inventati (100→50) invece delle frequenze vere | **Chiuso** | `GenreDNA.jsx:14-18` — calcola `count / maxCount` |
| UI-2 | La striscia di giorni consecutivi si disegnava anche a zero | **Chiuso** | `StreakDisplay.jsx:16` — `if (streak === 0 && uniqueDays === 0) return null` |
| UI-3 | Anno scritto a mano come 2026 nell'ultima schermata del Wrapped | **Chiuso** | `SlideOutro.jsx:37,56,78` — tre usi di `new Date().getFullYear()` |
| UI-4 | La sospensione di un utente falliva in silenzio | **Chiuso** | `AdminPage.jsx:58-61` — imposta `actionError`, mostrato a riga 86 |
| UI-5 | La creazione di un invito falliva in silenzio | **Chiuso** | `AdminPage.jsx:202-205` — imposta `createError`, mostrato a riga 252 |
| DEP-1 | `psycopg2-binary` fra le dipendenze di produzione ma usato solo da uno script una tantum | **Chiuso** | Ora solo in `requirements-dev.txt:5` |
| DEP-5 | `librosa` (~300 MB) importato sempre, anche quando non serve | **Chiuso** | `audio_feature_extractor.py:31` — importato dentro `_analyze_audio` |

### Erano medi

| ID | Cosa diceva | Verdetto | Prova |
|---|---|---|---|
| UI-6 | La finestra di benvenuto guardava solo il browser, non il dato sul server | **Chiuso** | `DashboardPage.jsx:57-58` — controlla `onboarding_completed` **e** il browser |
| UI-7 | Il grafico delle tendenze disegnava righe piatte per le misure senza dati | **Chiuso** | `TrendTimeline.jsx:48-51` — `activeKeys` tiene solo le chiavi con valori |
| UI-14 | L'avviso della pagina temporale diceva «0 ascolti» mentre stava ancora caricando | **Chiuso** | `TemporalPage.jsx:67` — l'avviso sta dentro `{!loading && ...}` |
| UI-8 | Soppressione del controllo sulle dipendenze di un effetto, con rischio di valore vecchio | **Chiuso** | `PlaylistComparePage.jsx` — nessuna soppressione nel file |
| UI-9 | Due soppressioni sull'effetto della simulazione del grafo | **Chiuso, con la riserva qui sotto** | `ArtistNetwork.jsx:322` — ne resta **una**, ora motivata in sei righe di commento |
| UI-10 | L'invito a un amico falliva in silenzio | **Chiuso** | `FriendsPage.jsx:81` — imposta `inviteError`, mostrato a riga 153 |
| UI-11 | La rimozione di un amico falliva in silenzio | **Chiuso** | `FriendsPage.jsx:113` — imposta `removeError`, mostrato a riga 190 |
| DEP-8 | `html2canvas` (200 kB) sempre nel pacchetto principale | **Chiuso** | Quattro usi, tutti con importazione ritardata; la compilazione lo mette in un file suo da 202 kB |

### Erano bassi

| ID | Cosa diceva | Verdetto | Prova |
|---|---|---|---|
| UI-15 | Un riquadro di riserva sempre presente nella pagina, anche invisibile | **Chiuso** | `SlideTopTracks.jsx:35-45` — ora è un'alternativa vera, o l'una o l'altro |
| UI-16 | Una proprietà `type` passata e mai usata | **Chiuso** | `TasteComparison.jsx` — la parola `type` non compare più |
| UI-18 | L'etichetta di stato dei lavori pianificati distingueva male i casi | **Chiuso** | `AdminPage.jsx:505-515` — tre stati distinti: in esecuzione, pianificato, in pausa |

### L'unico caso che merita una riga in più: UI-9

La soppressione del controllo sulle dipendenze **è ancora lì**, a `ArtistNetwork.jsx:322`. La conto
chiusa lo stesso, e vale la pena dire perché: il rilievo non chiedeva di toglierla, chiedeva di
**verificare se le dipendenze fossero giuste**. Quella verifica oggi è scritta nel codice, in sei
righe di commento che spiegano che `dataKey` è l'identità dei dati, e che elencare gli array al suo
posto rifarebbe partire la simulazione a ogni ridisegno, congelando il grafo a metà.

Lo scrivo per un motivo pratico: chi cercherà soppressioni con una ricerca testuale la ritroverà e
la riaprirà come rilievo nuovo. Non lo è.

## Cose controllate oggi e trovate sane

Nessuna di queste è un rilievo. Le elenco perché un rapporto che dice solo cosa è rotto non permette
di capire cosa sia stato guardato.

| Controllo | Esito |
|---|---|
| Componenti dell'interfaccia mai importati da nessuno | **0** su tutti i file `.jsx` di `components/` e `pages/` |
| Endpoint del server senza nessun chiamante | **0** su 34. L'unico senza riferimenti è `/auth/spotify/callback`, che lo chiama Spotify, non l'interfaccia |
| Dipendenze del server dichiarate e mai importate | **0** su 16 |
| Segnalibri `TODO` / `FIXME` / `HACK` lasciati nel codice | **0** |
| Catena delle migrazioni del database | 9 revisioni, catena unica, una sola testa (`3bf86040aebd`) — nessun ramo |
| Suite di test del server (`pytest -q`) | **Verde**, 599 test passati, uscita 0 |
| Controllo dello stile dell'interfaccia (`npm run lint`) | **Verde**, uscita 0 |
| Compilazione dell'interfaccia (`npm run build`) | **Verde**, uscita 0, 4,08 s |

## Un controllo che non ha saputo rispondere

Ho provato a verificare da programma il primo invariante di `CLAUDE.md`: ogni `except Exception` che
avvolga una chiamata a Spotify dev'essere preceduto da `except SpotifyAuthError: raise`, altrimenti
un errore di sessione scaduta viene inghiottito e l'utente vede dati vecchi invece di tornare al
login.

La ricerca automatica ha segnalato **25 punti su 50**. Ne ho aperti quattro a campione e **tutti e
quattro erano falsi allarmi**, per due motivi diversi: o il blocco non tocca Spotify affatto — è una
scrittura sul database protetta apposta, come vuole il terzo invariante — oppure
`except SpotifyAuthError` c'era davvero, solo più in alto della finestra di righe che stavo
guardando (è il caso di `wrapped.py`, dove sta otto righe sopra).

**Quindi non apro nessun rilievo qui.** Il metodo automatico non sa decidere questa domanda: per
rispondere servirebbe sapere, punto per punto, se dentro il `try` ci sia davvero una chiamata a
Spotify, e questo si vede solo leggendo. Lo scrivo perché il prossimo che ci prova non rifaccia la
stessa strada credendo di aver trovato venticinque difetti.

## Come è stato verificato

Tutti i comandi eseguiti il 2026-09-14, su `master` alla revisione `bc097d3`.

| Comando | Esito |
|---|---|
| `ruff check app/` | **1** — 2 rilievi `F841` (è E1) |
| `ruff format app/ --check` | 10 file su 68 divergono (informativo, non sorvegliato) |
| `pytest -q` | **0** — 599 test passati, 23 avvisi, 320,96 s |
| `npm run lint` | **0** |
| `npm run build` | **0** |

Interprete del server: `backend/.venv/Scripts/python.exe`, Python 3.12.13, ruff 0.9.3.

## Cosa conviene fare

1. **Riportare al verde la verifica automatica** (E1). Due righe, ma la decisione non è meccanica:
   per ciascuna va deciso se la variabile fosse il residuo di un uso mancante o solo zavorra. È la
   cosa con più valore in questa lista, perché finché il semaforo è rosso ogni difetto nuovo si
   confonde con quello vecchio.
2. **Decidere se sorvegliare anche la formattazione.** Oggi non lo è. Aggiungerla al flusso di
   verifica significa prima riformattare i 10 file, altrimenti nasce rossa.
3. **Non fidarsi di questo rapporto fra sei mesi.** Quello vecchio è arrivato al 100% di rilievi
   falsi in cinque mesi. Un rapporto di salute è una fotografia con una data sopra, e la data conta
   quanto il contenuto.

---

*Il rapporto precedente, del 2026-04-01, resta nella storia di git al commit `0d67cb7`.*
