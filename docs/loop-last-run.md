# Loop — registro dei run

Una riga per run, la più recente in fondo. Lo scrive il loop `progetto-wrap-dev-loop`.

---

## 2026-07-29 20:46 — `ITEM-DONE` — item 1 «Ricostruire gli ambienti di sviluppo»

**Guardia** (riga integrale di output):

```
LIBERO   nessun'altra sessione viva su C:\Users\fgioa\Desktop\PRO\progettoWrap (finestra 15min, 8 transcript scansionati, 0 worktree ispezionati, scope suite OFF)
         costo del controllo: 0.132s su 8 transcript (soglia 1s, massimo storico 0.132s)
         contatore: 1 fire senza progresso confermato (soglia 3)
```

`no_progress_streak`: **0** (azzerato da questo `ITEM-DONE`; era il primo run, nessun run-log precedente
— il file non esisteva).

### Cosa è stato fatto

Ricostruiti i due ambienti di sviluppo, che nel repo non esistevano. Nessun file di codice
modificato: l'item produce solo artefatti locali, tutti già ignorati da git.

- **Backend**: venv creato con l'interprete 3.12 indicato dall'item, non con il 3.14 di sistema.
  `.venv\Scripts\python.exe --version` → `Python 3.12.13`.
- **Frontend**: `npm ci` (c'era `package-lock.json`), 566 pacchetti.

### Verifiche eseguite

| Comando | Esito | Exit |
|---|---|---|
| `backend\.venv\Scripts\python.exe -m pytest --collect-only -q` | **534 test raccolti, 0 errori di import** | 0 |
| `cd frontend && npm ci` | 566 pacchetti aggiunti | 0 |
| `cd frontend && npm run lint` | nessun errore | 0 |
| `cd frontend && npm run build` | 2728 moduli, build in 7.82s | 0 |
| `git status --porcelain` | vuoto | 0 |

Interprete dichiarato: `C:\Users\fgioa\Desktop\PRO\progettoWrap\backend\.venv\Scripts\python.exe`
(Python 3.12.13), creato da
`C:\Users\fgioa\AppData\Roaming\uv\python\cpython-3.12.13-windows-x86_64-none\python.exe`.

Il riferimento dell'item era «185 test e 19 errori con l'interprete globale»: ora **534 raccolti e
zero errori**. I tre criteri di verifica dell'item sono tutti verdi, incluso «nessun file di
ambiente committato» — `git status` è vuoto, `.venv/` e `node_modules/` sono già nel `.gitignore`.

### Configurazione pytest: non serviva, e non è stata aggiunta

Il punto 4 dell'item chiedeva di aggiungere una configurazione asyncio **solo se** pytest fosse
fallito per mancanza di quella configurazione. Non è il caso: la suite gira e 526 test passano.
Resta un avviso di deprecazione (`asyncio_default_fixture_loop_scope` non impostato) che non fa
fallire nulla con `pytest-asyncio==0.25.0`, la versione pinnata. Nessun file di configurazione
creato — la condizione posta dall'item non si è verificata.

### Finding per l'item 4 (suite non ancora verde) — non corretto qui, non è questo l'item

`pytest -q` completo: **526 passati, 8 falliti in 5m42s**. Le rotture non sono di ambiente, e
l'item 4 le prevede già («suite verde in locale»). Le lascio documentate qui perché il giro che
prenderà l'item 4 parta da dati veri e non da zero:

1. **`test_privacy.py` — 4 fallimenti da inquinamento tra test, non da codice rotto.**
   `RuntimeError: Event loop is closed`. Presi singolarmente questi test **passano**
   (`test_delete_account_authenticated` da solo: 1 passed). Falliscono solo se prima di loro è già
   girato un altro `TestClient(app)`. Causa: `scheduler = AsyncIOScheduler()` è un oggetto globale
   di modulo (`app/main.py:87`); ogni `TestClient(app)` usato come context manager esegue il
   lifespan, che fa `scheduler.start()` (`app/main.py:778`) e poi `scheduler.shutdown(wait=False)`
   (`app/main.py:794`). Il secondo `TestClient` riavvia **lo stesso** oggetto globale su un event
   loop nuovo, mentre APScheduler tiene ancora il riferimento al primo loop, ormai chiuso.
   Nota: `asyncio_mode` non c'entra — questi sono test sincroni, senza marker async.

2. **`test_temporal_patterns.py` — 4 fallimenti deterministici, veri anche in isolamento.**
   Esempio: `test_plays_bucketed_to_correct_hour` → `assert hm[weekday][14] == 2` fallisce con
   `assert 0 == 2` (`tests/test_temporal_patterns.py:206`). Le quattro rotture stanno tutte nella
   stessa area (distribuzione oraria, giorno della settimana, streak): plausibile una sola causa
   comune legata al fuso orario, da confermare quando si prenderà l'item.

### Altre osservazioni, senza azione

- **`npm run lint` è già verde** (exit 0). L'item 7, dopo il checkpoint, lo dà per rosso: quando
  si arriverà lì, resterà da fare solo la parte sulle 6 soppressioni `eslint-disable` da motivare,
  non la pulizia degli errori.
- **Node**: in locale gira la v24.15.0, la CI usa la 20 (`ci.yml`). Build e lint passano su
  entrambe per quanto si vede qui, ma la differenza è reale e va tenuta presente.
- **Item 2 e 4 confermati sul codice**: `build.yml:16,19` fa `docker build ./backend` e
  `./frontend`, cartelle che non contengono Dockerfile; `ci.yml` ha solo i due job di lint.
- **Contratto del repo**: `.claude/CLAUDE.md` letto e rispettato. Non concede nulla di più ampio
  del prompt del loop. Non esiste un `CLAUDE.md` in radice.
- **Modifica al backlog oltre allo stato dell'item**: sotto l'item 4 è stata aggiunta una riga di
  rimando a questo run-log per i due fallimenti misurati. Nessun item nuovo creato.

### Remoto

`git rev-parse @{u}` a inizio run: `8616d0c6b50fac0db5a7d262e928c0df65a602ba`.
A fine run: **identico**. Nessun push partito, come deve essere.

---

## 2026-07-29 21:40 — `ITEM-DONE` — item 2 «`build.yml` punta a Dockerfile che non esistono»

**Guardia** (riga integrale di output):

```
LIBERO   nessun'altra sessione viva su C:\Users\fgioa\Desktop\PRO\progettoWrap (finestra 15min, 9 transcript scansionati, 0 worktree ispezionati, scope suite OFF)
         costo del controllo: 0.069s su 9 transcript (soglia 1s, massimo storico 0.132s)
         contatore: 1 fire senza progresso confermato (soglia 3)
```

`no_progress_streak`: **0** (resta a zero, questo run è un `ITEM-DONE`).

### Cosa è stato fatto

Il workflow «Build Docker Images» chiedeva a Docker di costruire due immagini a partire da
`./backend` e `./frontend`, cartelle che non contengono nessun `Dockerfile`: **falliva a ogni push
su master**. I due Dockerfile veri stanno in `docker/`.

Corretti i due step di `.github/workflows/build.yml` aggiungendo `-f docker/backend.Dockerfile` e
`-f docker/frontend.Dockerfile`, e **lasciando i context invariati** a `./backend` e `./frontend`.
Quest'ultima parte è la scelta che contava, ed è stata presa guardando come il repo già costruisce
le stesse immagini altrove, non a intuito:

- `docker/docker-compose.yml:40-41` e `docker/docker-compose.prod.yml:38-39` dichiarano entrambi
  `context: ../backend` con `dockerfile: ../docker/backend.Dockerfile` (idem per il frontend). Il
  workflow ora fa la stessa identica cosa, espressa dalla radice del repo.
- Esistono `backend/.dockerignore` e `frontend/.dockerignore` **separati**, con dentro voci come
  `tests/`, `.venv/` da un lato e `node_modules/`, `dist/` dall'altro: sono scritti rispetto a quelle
  due cartelle, il che conferma che il context inteso è la cartella e non la radice.

Un context sbagliato non avrebbe dato errore di sintassi: avrebbe rotto le `COPY` dentro
l'immagine, o si sarebbe portato dietro l'intero repo. Per questo è stato verificato a parte.

Aggiunto sopra i due step un commento di tre righe che dice perché il Dockerfile e il context
stanno in due posti diversi, così la prossima modifica non li riallinea «per pulizia».

### Verifiche eseguite

| Comando | Esito | Exit |
|---|---|---|
| `verify_build_yml.py` — YAML + esistenza dei path citati | YAML carica, 4 path su 4 esistono | 0 |
| `verify_contexts.py` — ogni `COPY` risolve dentro il context | 8 sorgenti su 8 OK, nessuna esclusa dal `.dockerignore` | 0 |
| `cd frontend && npm run lint` | nessun errore | 0 |
| `cd frontend && npm run build` | 2728 moduli, build in 3.88s | 0 |
| `backend\.venv\Scripts\python.exe -m pytest -q` | **526 passati, 8 falliti** in 4m17s | 1 |

Interprete: `C:\Users\fgioa\Desktop\PRO\progettoWrap\backend\.venv\Scripts\python.exe` (3.12.13).
I due script di verifica sono usa-e-getta, scritti nello scratchpad di sessione e non versionati.

Il primo criterio dell'item («ogni path citato in `build.yml` esiste nel repo; lo YAML si carica
senza errori») è verde. Il secondo controllo non era richiesto dall'item ed è stato aggiunto
perché il criterio richiesto non distingue un context giusto da uno sbagliato: entrambi i path
esisterebbero comunque.

`npm run build` non è un contorno: `docker/frontend.Dockerfile:10` esegue proprio quel comando
**dentro** l'immagine, quindi se fosse rosso lo step di CI fallirebbe comunque, con i path corretti.

### Gli 8 test rossi sono quelli di prima, e non sono di questo item

Identici per numero, file e nome a quelli misurati al run precedente: 4 in `test_privacy.py`,
4 in `test_temporal_patterns.py`, 526 passati in entrambi i giri. Questo run ha toccato **un solo
file YAML sotto `.github/`**, che nessun test importa: nessuna regressione possibile, e infatti
nessuna. Sono il mandato esplicito dell'item 4 e lì restano — un run, un item.

### Limite dichiarato: la build vera non è stata eseguita

`docker version` fallisce, il demone locale non è avviato:

```
failed to connect to the docker API at npipe:////./pipe/dockerDesktopLinuxEngine; check if the
path is correct and if the daemon is running
```

Non è stato avviato Docker Desktop: sarebbe andato oltre il mandato dell'item, che già mette in
conto questo limite. Quindi **la prova che le due immagini si costruiscono davvero arriverà solo
al prossimo push**, come previsto dal testo dell'item. Ciò che è provato qui è tutto ciò che è
provabile senza demone: i path esistono, lo YAML è valido, e ogni file che i Dockerfile copiano è
raggiungibile dentro il context scelto.

### Altre osservazioni, senza azione

- **Discrepanza minore nel backlog**: l'item cita «righe 13 e 16», i due `docker build` stanno in
  realtà alle righe 16 e 19. Il testo dell'item non è stato corretto — descrive la cosa giusta con
  un numero di riga sbagliato, e ora quelle righe sono comunque cambiate.
- **Contratto del repo**: `.claude/CLAUDE.md` riletto. Nessun `CLAUDE.md` in radice. Non concede
  nulla di più ampio del prompt del loop.
- **Nessun item nuovo creato**, nessuna modifica al backlog oltre allo stato dell'item 2.

### Remoto

`git rev-parse @{u}` a inizio run: `8616d0c6b50fac0db5a7d262e928c0df65a602ba`.
A fine run: **identico**. Nessun push partito, come deve essere.

---

## 2026-07-29 22:33 — `NOOP-BUSY` — nessun item preso

**Guardia** (riga integrale di output, exit code 3):

```
CEDI     1 sessione/i viva/e sulla repo (finestra 15min):
         5c1a7c88-4fef-4973-b179-d982fefec1ef  ultimo evento 2026-07-29T22:27:27Z (6.2min fa)
         scrivi NOOP-BUSY nel run-log: cedere non e' sparire
         costo del controllo: 0.010s su 10 transcript (soglia 1s, massimo storico 0.132s)
         contatore: 1 fire senza progresso confermato (soglia 3)
```

`no_progress_streak`: **1** (era 0, azzerato dall'`ITEM-DONE` dell'item 2; primo run dello streak
2026-07-29T22:33:56Z).

### Perché il loop ha ceduto

Il motivo dichiarato dalla guardia è **«sessione viva»**: un'altra sessione stava lavorando su
questa working tree, con ultimo evento sei minuti prima del controllo. È il funzionamento normale
del meccanismo di cortesia, non un guasto — per questo l'esito è `NOOP-BUSY` e non
`NOOP-UNDECIDABLE`. Nessun item preso, nessun file di codice o di backlog toccato: l'unica scrittura
di questo run è questa voce di registro.

### Breaker

**Non aperto.** Serve che siano vere entrambe le condizioni, e la prima non lo è: lo streak vale 1,
la soglia è 3. Non è nemmeno il caso di `BREAKER: TRATTENUTO`, che riguarda una soglia raggiunta ma
con troppo poco tempo trascorso: qui la soglia non è raggiunta affatto.

### Conti con la guardia

Nessuno dei due comandi di chiusura è stato eseguito, e in questo ramo è corretto così:
`--confirm-progress` vale solo dopo un `ITEM-DONE`, `--confirm-escalation` solo se la guardia stampa
una riga `ESCALATION` — questa ha stampato `CEDI`.

### Escalation al vault

Nessuna. Il canale verso Fabio si usa per il breaker aperto o per il capolinea, e non siamo in
nessuno dei due casi. Il lock fra loop non è stato preso, perché non c'era nulla da scrivere in
`Inbox.md`.

### Remoto

`git rev-parse @{u}` a inizio run: `8616d0c6b50fac0db5a7d262e928c0df65a602ba`.
A fine run: **identico**. Nessun push partito. `git status --porcelain` era vuoto prima di questa
voce di registro.

---

## 2026-07-30 03:41 — `ITEM-DONE` — item 3 «Componente morto: `EmptyState.jsx`»

**Guardia** (riga integrale di output, exit code 0):

```
LIBERO   nessun'altra sessione viva su C:\Users\fgioa\Desktop\PRO\progettoWrap (finestra 15min, 11 transcript scansionati, 0 worktree ispezionati, scope suite OFF)
         costo del controllo: 0.071s su 11 transcript (soglia 1s, massimo storico 0.132s)
         contatore: 2 fire senza progresso confermato (soglia 3)
```

`no_progress_streak`: **0** (era 1, portato a zero da questo `ITEM-DONE`; lo streak apertosi col
`NOOP-BUSY` del 2026-07-29T22:33:56Z è chiuso).

### Nota di metodo: il path della guardia va passato a PowerShell, non a Bash

Il comando del Passo 0 eseguito nella shell Bash è **fallito senza eseguire nulla**: Git Bash ha
mangiato i backslash e ha cercato
`C:\Users\fgioa\Desktop\PRO\progettoWrap\Usersfgioa.claudescriptsloop_yield.py`, exit 2. Non era la
guardia a dire «non so rispondere» — era la shell a non aver mai avviato lo script, quindi **non**
è un caso di `NOOP-UNDECIDABLE`. Rieseguito in PowerShell con l'operatore `&` e i path quotati, ha
risposto `LIBERO`. Vale la regola globale: su Windows mai path Windows nudi dentro Bash.

### Working tree sporca all'avvio: valutata, non un `NOOP-DIRTY`

`git status --porcelain` a inizio run non era vuoto: ` M .claude/tasks/lessons.md`. Il Passo 3
prevede `NOOP-DIRTY` per «lavoro non tuo e non riconducibile al backlog», e le due eccezioni note
(stato della guardia sotto `_local\`, run-log) non coprono questo file. Non mi sono fermato, e la
ragione va scritta perché è una decisione, non una svista:

- **Cosa contiene**: una sola voce di lezione, completa e chiusa, che documenta il comportamento di
  questo stesso loop — l'hook globale di fine turno committa il run-log che il loop, nei rami che
  cedono, lascia scoperto. È meta-lavoro sul loop, non codice a metà.
- **Chi l'ha scritta**: la sessione interattiva che aveva causato il `NOOP-BUSY` precedente. La
  guardia di questo run dice `LIBERO`, quindi quella sessione è finita: non c'è lavoro in volo da
  proteggere, che è il rischio per cui `NOOP-DIRTY` esiste.
- **Sovrapposizione con questo item**: **zero**. Io ho toccato `frontend/src/components/ui/`,
  `docs/LAUNCH-PLAN.md`, `docs/LOOP-BACKLOG.md`, `docs/loop-last-run.md`. Il file non è stato
  aperto in scrittura né messo in stage: l'`add` di questo run elenca path espliciti.

Fermarsi qui avrebbe bruciato un giro e portato lo streak a 2 per una voce di documentazione già
finita. Prevedibile che l'hook di fine turno la committi a parte, come già accaduto in `91937b2`.

### Cosa è stato fatto

`frontend/src/components/ui/EmptyState.jsx` era definito, esportato e **importato da nessuno**.
Rimosso il file, e annotata la cosa in `LAUNCH-PLAN.md`.

Prima di cancellare ho riverificato gli import come chiede l'item, allargando la ricerca a tutto il
repo e non solo a `frontend/src`. `EmptyState` compariva in 5 posti, nessuno dei quali un import:
la propria definizione, il backlog, `.claude/CLAUDE.md:116`, `docs/RESTRUCTURING-PLAN.md` (Phase 3,
che lo aveva pianificato) e `.claude/skills/react-spotify-patterns/SKILL.md:116`. Nessuno importa,
quindi non è scattata la condizione di `[BLOCKED_USER]` prevista dall'item.

### Perché era morto: non dimenticato, ma superato da una convenzione

Il pezzo che l'item non diceva, e che cambia l'annotazione da scrivere.
`.claude/skills/react-spotify-patterns/SKILL.md:116` **vieta esplicitamente** l'empty state dentro
i chart: i chart restituiscono `null` senza dati e il genitore decide la visibilità. Combacia con la
convenzione di `.claude/CLAUDE.md` («Empty sections: hide rather than showing "nessun dato
disponibile"»). Il componente nasce dalla Phase 3 di `RESTRUCTURING-PLAN.md:188`, che voleva un
empty state per sette chart; poi la scelta si è ribaltata, e il file è rimasto lì.

Non ho preso la cosa dai documenti: l'ho verificata sul codice. I chart escono con `null` quando i
dati mancano — `AudioRadar.jsx:28`, `GenreTreemap.jsx:37`, `MoodScatter.jsx:24`,
`TrendTimeline.jsx:25`, `ListeningHeatmap.jsx:97`, `ArtistNetwork.jsx:420`, `OverlapHeatmap.jsx:27`,
`PlaylistComparison.jsx:24`, `TasteOverlapBar.jsx:24`, `StreakDisplay.jsx:14`.

### Correzione al testo dell'item: l'annotazione richiesta era falsa

L'item chiedeva di annotare che «gli empty state sono implementati per-pagina, non col componente
condiviso». **Non è vero, e non l'ho scritto.** In tutto `frontend/src` esiste **un solo** messaggio
testuale di «nessun dato», in `AdminPage.jsx:442`. Non c'è un empty state per pagina: la scelta di
prodotto è non mostrare nulla e nascondere la sezione. Scrivere la frase dell'item avrebbe messo a
verbale nel piano di lancio un'affermazione che il codice smentisce, ed è esattamente il tipo di
documento che un giro successivo prende per buono.

In `LAUNCH-PLAN.md` ho quindi scritto la versione vera, con i riferimenti al codice qui sopra, più
il fatto che la metà «error boundaries» della voce è invece piena per davvero: `SectionErrorBoundary`
avvolge le sezioni di **9 pagine** (96 occorrenze su 10 file, `SectionErrorBoundary.jsx` incluso).
La voce `- [x] Empty states + error boundaries` alla riga 15 non è stata declassata — è vera, ma
andava spiegata: ora rimanda alla nota.

### Verifiche eseguite

| Comando | Esito | Exit |
|---|---|---|
| ricerca `EmptyState` su `frontend/src` | **nessun risultato** | — |
| `cd frontend && npm run lint` | nessun errore | 0 |
| `cd frontend && npm run build` | 2728 moduli, build in 4.26s, 49 entry PWA | 0 |
| `backend\.venv\Scripts\python.exe -m pytest -q` | **526 passati, 8 falliti** in 4m19s | 1 |

Interprete backend: `C:\Users\fgioa\Desktop\PRO\progettoWrap\backend\.venv\Scripts\python.exe`
(Python 3.12.13). I due criteri di verifica dell'item sono entrambi verdi.

Gli 8 rossi sono **gli stessi di sempre**, identici per numero, file e nome ai due run precedenti:
4 in `test_privacy.py`, 4 in `test_temporal_patterns.py`, 526 passati in tutti e tre i giri. Questo
run ha cancellato un componente React che nessuno importava e ha toccato due file markdown: nessun
test Python li carica, nessuna regressione possibile, e infatti nessuna. Restano il mandato
dell'item 4.

### Due riferimenti pendenti che **non** ho toccato, e perché

La cancellazione lascia due documenti che citano un file ora inesistente. Non li ho corretti perché
stanno sotto un divieto esplicito del `CLAUDE.md` globale — non modificare `CLAUDE.md`, file di
skill, agent o command senza richiesta esplicita — e il Passo 2 dice che il vincolo più restrittivo
vince. Li segnalo perché la decisione è di Fabio, non mia:

1. **`.claude/CLAUDE.md:116`** — «EmptyState component for charts with no data». Ora è **falso** su
   due fronti: il componente non esiste più, e i chart non usavano quel pattern nemmeno prima.
2. **`.claude/skills/react-spotify-patterns/SKILL.md:116`** — «Non usare `EmptyState` nei chart».
   L'istruzione resta giusta nella sostanza (non aggiungere empty state ai chart), ma nomina un file
   cancellato.

`docs/RESTRUCTURING-PLAN.md` lo lascio invece **per scelta**, non per divieto: è un piano concluso
che descrive cosa si era deciso allora, e riscriverlo sarebbe falsificare un registro storico. La
nota in `LAUNCH-PLAN.md` dice esplicitamente che quelle righe restano come traccia.

### Breaker

**Non aperto.** Nessuna delle due condizioni è in piedi: questo run è un `ITEM-DONE`, quindi lo
streak è 0 contro una soglia di 3. Nessun `BREAKER: TRATTENUTO` da scrivere, e nessuna riga
`escalated:` pendente da chiudere — il run precedente non ne aveva aperta nessuna.

### Conti con la guardia

Eseguito `--confirm-progress` **dopo** il commit, come prescritto: serve ad azzerare il contatore
della guardia, che era a 2 su 3 e al prossimo giro avrebbe emesso un allarme «backlog fermo» falso
proprio mentre il loop stava avanzando.

### Escalation al vault

Nessuna, e nessun lock preso. Il canale verso Fabio si apre solo per breaker o capolinea: qui non
siamo in nessuno dei due, e restano da fare l'item 4, l'ispezione frontend e il checkpoint. Nulla da
scrivere in `Inbox.md`, quindi la corsia `inbox` non è stata occupata.

### Remoto

`git rev-parse @{u}` a inizio run: `8616d0c6b50fac0db5a7d262e928c0df65a602ba`.
A fine run: **identico**. Nessun push partito, come deve essere.

---

## 2026-07-30 04:53 UTC — `ITEM-DONE` — item 4 «La CI non esegue i test backend»

**Guardia** (riga integrale di output, exit code 0):

```
LIBERO   nessun'altra sessione viva su C:\Users\fgioa\Desktop\PRO\progettoWrap (finestra 15min, 12 transcript scansionati, 0 worktree ispezionati, scope suite OFF)
         costo del controllo: 0.080s su 12 transcript (soglia 1s, massimo storico 0.132s)
         contatore: 1 fire senza progresso confermato (soglia 3)
```

`no_progress_streak`: **0** (era 0, resta 0: questo run è un `ITEM-DONE`).

Il comando del Passo 0 è stato eseguito **in PowerShell**, non in Bash, per la ragione già
registrata al run precedente: Git Bash mangia i backslash dei path Windows e lo script non parte
nemmeno. Il primo tentativo in Bash è fallito allo stesso modo (exit 2, file inesistente) e **non**
è un `NOOP-UNDECIDABLE`: non era la guardia a non saper rispondere, era la shell a non averla mai
avviata.

### Working tree sporca all'avvio: valutata, non un `NOOP-DIRTY`

`git status --porcelain` a inizio run: ` M .claude/tasks/lessons.md`. Stessa decisione del run
precedente, con una ragione in più. Il file contiene **due** voci di lezione, entrambe chiuse ed
entrambe sul funzionamento di questo loop: l'hook di fine turno che committa il run-log, e la
here-string PowerShell che ha spezzato il commit dell'item 3. La seconda l'ha scritta la sessione
dell'item 3 documentando un guaio proprio suo. È meta-lavoro sul loop, finito, e la sovrapposizione
con i file di questo item è **zero**. La guardia dice `LIBERO`, quindi nessun lavoro in volo da
proteggere — che è il rischio per cui `NOOP-DIRTY` esiste. Non messo in stage: l'`add` elenca path
espliciti.

### Gli 8 rossi erano due guasti distinti, e nessuno dei due era «i test sono sbagliati a caso»

Il backlog li dava per due gruppi, ed è vero, ma la causa del secondo gruppo non era quella
ipotizzata («plausibile una sola causa comune legata al fuso orario»). Non è il fuso orario.

**Gruppo A — `test_privacy.py`, 4 rossi: lo scheduler globale.** Confermata la diagnosi del run
dell'item 1. `scheduler = AsyncIOScheduler()` stava a livello di modulo (`app/main.py:87`): un
oggetto solo per processo, avviato dal lifespan. Ogni `TestClient(app)` usato come context manager
esegue un ciclo di vita completo, quindi il secondo riavviava **lo stesso** oggetto su un event loop
nuovo mentre APScheduler teneva ancora il riferimento al primo, ormai chiuso — `RuntimeError: Event
loop is closed`.

Applicata la **correzione strutturale**, non quella di ripiego lato test: lo scheduler ora nasce
dentro `lifespan()`, così ogni ciclo di vita ha il suo, coerente col loop che lo ospita. Resta un
attributo di modulo perché due endpoint lo leggono — `/health/detailed` (`app/main.py`) e
`admin.list_jobs` (`app/routers/admin.py:159`, import lazy) — e ora vale `None` fuori dal lifespan,
quindi entrambi hanno la guardia. Il perché è scritto accanto alla dichiarazione, così la prossima
modifica non lo riporta a livello di modulo «per pulizia».

Questo non è solo un guaio di test: uno scheduler legato a un loop morto è un rischio reale a ogni
riavvio in-process dell'app.

**Gruppo B — `test_temporal_patterns.py`, 4 rossi: date di calendario cablate, scadute.** I quattro
test fissavano `datetime(2026, 3, 25, ...)`. `compute_temporal_patterns` scarta gli ascolti più
vecchi della sua finestra (`temporal_patterns.py:106`, `days=30` di default): il 25 marzo, oggi, è
**127 giorni fa**, quindi ogni play veniva filtrato e la pipeline restituiva `_empty_result()`. Da
lì tutti gli `assert 0 == 2`. Il servizio è corretto; erano i test a marcire. Prova che il discrimine
è la data e non altro: **tutti** i test dello stesso file che usano `datetime.now()` passavano già.

Corretti rendendo le date relative a ora (`_recent_day`, `_recent_weekday`), il che tiene i test
dentro la finestra di default senza cambiare cosa verificano. `_recent_weekday` risale al massimo di
8 giorni, quindi il giorno della settimana resta quello voluto qualunque sia oggi. Tutto in UTC,
niente ora legale: nessuna dipendenza dall'orologio oltre a «che giorno è oggi».

Aggiunta `TestTimeWindowCutoff` (2 test) che **fissa il taglio** dei 30 giorni sui due lati: è la
regressione vera, perché quel comportamento è ciò che ha divorato in silenzio quattro test facendoli
sembrare un calcolo rotto invece che un input fuori intervallo.

### Verifiche eseguite

| Comando | Esito | Exit |
|---|---|---|
| `pytest tests/test_privacy.py tests/test_temporal_patterns.py -q` (prima) | **8 falliti, 21 passati** | 1 |
| `pytest tests/test_privacy.py -q` (dopo fix scheduler) | 7 passati | 0 |
| `pytest tests/test_temporal_patterns.py -q` (dopo fix date) | 24 passati | 0 |
| `pytest -q` — **suite completa** | **536 passati, 0 falliti** in 318.72s | **0** |
| `pytest -q` con `DATABASE_URL`/`REDIS_URL` su porte chiuse | **536 passati** in 257.04s | **0** |
| `python verify_ci.py` — YAML + struttura del job | 7 controlli su 7 OK | 0 |
| `ruff check app/main.py app/routers/admin.py` | 1 errore, **pre-esistente** (vedi sotto) | 1 |
| `cd frontend && npm run lint` | nessun errore | 0 |
| `cd frontend && npm run build` | 49 entry PWA, build ok | 0 |

Interprete: `C:\Users\fgioa\Desktop\PRO\progettoWrap\backend\.venv\Scripts\python.exe` (Python
3.12.13). Erano 534 test raccolti, ora 536: i 2 in più sono `TestTimeWindowCutoff`.
`verify_ci.py` è usa-e-getta, nello scratchpad di sessione, non versionato.

### Il job `backend-test`, e perché **senza** servizi

L'item metteva in conto di dover avviare Postgres e Redis. **Non servono**, e non l'ho dedotto dal
codice: ho rieseguito la suite intera con `DATABASE_URL` e `REDIS_URL` puntati a porte chiuse
(`127.0.0.1:5599` e `:6699`). Stesso risultato, 536 passati. I test che toccano il DB usano
`AsyncMock` e il lifespan tollera l'assenza di entrambi.

Il controllo serviva davvero: su questa macchina **la porta 5432 è in ascolto**, quindi un run
locale «verde» non avrebbe distinto una suite che ignora il DB da una che ci si appoggia in
silenzio. Con i servizi veri spenti la distinzione è provata. Il perché è scritto come commento
dentro il job, altrimenti il prossimo che legge aggiunge un blocco `services:` che non serve.

Il job rispecchia ciò che ha funzionato in locale: Python 3.12, `pip install -r requirements-dev.txt`,
`pytest -q`, più `timeout-minutes: 15` perché la suite gira in 4-5 minuti e un job appeso non deve
bruciare minuti. Job indipendente dagli altri due: segnale più leggibile.

### Finding che riguarda l'esito dell'item: `backend-lint` era **già rosso**

Non l'ho toccato — non è questo l'item — ma va detto perché cambia cosa vedrà l'utente al prossimo
push. `ruff check app/`, il comando esatto che esegue il job `backend-lint` di `ci.yml`, **fallisce
con 2 errori**:

- `app/main.py:721` — `F841 Local variable 'synced' is assigned to but never used`
- `app/routers/auth.py:363` — `F841 Local variable 'sync_ok' is assigned to but never used`

**Sono pre-esistenti, non miei**, e l'ho verificato invece di affermarlo: `auth.py` non l'ho aperto
in scrittura, e sulla copia di `main.py` estratta da `HEAD` ruff dà lo stesso errore alla riga 716
(le mie 5 righe di commento lo spostano a 721). Conseguenza pratica: la CI **resta rossa nel
complesso** finché non si sistemano, ma il job `backend-test` è indipendente e riporterà il proprio
esito a parte, quindi lo scopo dell'item — i test girano in CI — è raggiunto lo stesso. La decisione
se aprire un item è di Fabio: un giro, un item, e dedurne di nuovi è vietato.

Nota minore, stessa famiglia: `ruff format app/ --check` segnala 10 file da riformattare, `main.py`
incluso **già a HEAD**. Nessun job di CI lo esegue, quindi non fa da gate; e non ho aggiunto deriva.

### Osservazione, senza azione: `_empty_result()` non ha la chiave `first_play_date`

`temporal_patterns.py:314-340` restituisce 12 chiavi, il ramo pieno ne restituisce 13:
`first_play_date` manca solo nel ramo vuoto. Chi consuma la risposta con zero ascolti riceve una
chiave assente invece di `None`. Nessun test lo copre — `test_all_expected_keys_present` usa date
recenti e non passa mai di lì. Non l'ho corretto: non rende rosso nulla e non è l'item. Lo scrivo
perché è il tipo di incoerenza che un giro successivo scambia per un bug del frontend.

### Breaker

**Non aperto.** Nessuna delle due condizioni: questo run è un `ITEM-DONE`, streak 0 contro soglia 3.
Nessun `BREAKER: TRATTENUTO` da scrivere, nessuna riga `escalated:` pendente da chiudere.

### Conti con la guardia

Eseguito `--confirm-progress` **dopo** il commit, come prescritto: il contatore della guardia era a
1 su 3 e senza l'azzeramento arriverebbe a emettere un allarme «backlog fermo» falso mentre il loop
sta avanzando.

### Escalation al vault

Nessuna, e nessun lock preso. Il canale verso Fabio si apre solo per breaker o capolinea: qui non
siamo in nessuno dei due, e restano l'ispezione frontend (item 5) e il checkpoint. Niente da
scrivere in `Inbox.md`, quindi la corsia `inbox` non è stata occupata.

### Remoto

`git rev-parse @{u}` a inizio run: `8616d0c6b50fac0db5a7d262e928c0df65a602ba`.
A fine run: **identico**. Nessun push partito, come deve essere.

---

## 2026-07-30 07:40 UTC — `ITEM-DONE` — item 5 «ISPEZIONE FRONTEND — primo giro da utente»

**Guardia** (riga integrale di output, exit code 0):

```
LIBERO   nessun'altra sessione viva su C:\Users\fgioa\Desktop\PRO\progettoWrap (finestra 15min, 13 transcript scansionati, 0 worktree ispezionati, scope suite OFF)
         costo del controllo: 0.074s su 13 transcript (soglia 1s, massimo storico 0.132s)
         contatore: 1 fire senza progresso confermato (soglia 3)
```

`no_progress_streak`: **0** (era 0, resta 0: questo run è un `ITEM-DONE`).

Il Passo 0 è stato eseguito **in PowerShell** dopo che il tentativo in Bash è fallito allo stesso
modo dei due run precedenti: Git Bash mangia i backslash dei path Windows e ha cercato
`...\progettoWrap\Usersfgioa.claudescriptsloop_yield.py`, exit 2. **Non** è un `NOOP-UNDECIDABLE`:
non era la guardia a non saper rispondere, era la shell a non averla mai avviata. È la terza volta
di fila; la lezione è già a verbale in `.claude/tasks/lessons.md`.

### Working tree pulita all'avvio

`git status --porcelain` a inizio run: **vuoto**. Nessuna decisione da prendere su lavoro altrui,
a differenza dei due run precedenti.

### Cosa è stato fatto

Giro di sola osservazione: **nessun file di codice modificato**, come impone l'item. Ispezionate
tutte e 14 le rotte dichiarate in `App.jsx` e prodotti **9 finding** nella sezione «Trovati
dall'ispezione» del backlog, ciascuno col suo criterio di verifica.

### Modalità di ispezione, pagina per pagina

Il protocollo chiede di dichiarare per ogni pagina se è stata guardata dal vivo o sul codice.

| Rotta | Pagina | Modalità |
|---|---|---|
| `/` | LoginPage | **Dal vivo** — server di sviluppo su 5173, pagina caricata, testo e console letti |
| `/auth/spotify/login` | (uscita verso Spotify) | **Dal vivo** — percorso col backend spento, 500 e pagina bianca |
| `/dashboard` | DashboardPage | Codice |
| `/profile` | ProfilePage | Codice |
| `/discovery` | DiscoveryPage | Codice |
| `/evolution` | TasteEvolutionPage | Codice |
| `/temporal` | TemporalPage | Codice |
| `/artists` | ArtistNetworkPage | Codice |
| `/playlists` | PlaylistComparePage | Codice |
| `/playlist-analytics` | PlaylistAnalyticsPage | Codice |
| `/wrapped` | WrappedPage | Codice |
| `/friends` e `/invite/:code` | FriendsPage | Codice |
| `/privacy` | PrivacyPage | Codice |
| `/admin` | AdminPage | Codice |
| `*` | rimando alla radice | Codice |

Il limite era previsto dall'item: senza `.env` il backend non parte, e il login Spotify reale è
vietato, quindi le pagine protette non sono visibili dal browser. Confermato che il backend fosse
davvero spento invece di darlo per scontato: la porta 8001 non è in ascolto, quindi il 500 è il
proxy di Vite che non trova nessuno, cioè esattamente lo scenario «backend giù» che l'item chiedeva
di provare.

### Due delle quattro piste del censimento erano sbagliate

Le piste del backlog erano ipotesi da confermare o smontare. Due non reggono, e vanno dette perché
un giro successivo le prenderebbe per buone.

1. **«`/privacy` e `/admin` non stanno nel menu — pagine fantasma?»** — **Falso.** Ci sono
   entrambe, nel piè di pagina della barra laterale (`Sidebar.jsx:118-145`), separate dalle voci
   principali da un bordo. `/admin` compare solo se `user.is_admin`, ed è la scelta giusta. Tutte e
   14 le rotte sono raggiungibili dall'interfaccia. Verificato anche che non ci sia un buco di
   accesso: `AdminPage.jsx:561-562` rimanda alla dashboard chi non è amministratore, quindi la
   protezione non dipende solo dal menu.
2. **«il Dashboard importa ancora `GenreTreemap`»** — vero come nome, **falso come sostanza**.
   `GenreTreemap.jsx:54-70` disegna un `PieChart` con raggio interno al 45%: è già una ciambella.
   Il punto B1 di `todo.md:17` chiede «donut chart al posto del treemap» ed è segnato da fare, ma la
   modifica c'è già. È diventato il finding I-7, che è un rinominare, non un riscrivere.

Le altre due piste sono confermate, e una va allargata parecchio:

3. **Colori cablati** — il backlog ne nominava 2 (`StreakDisplay.jsx:102`, `GenreDNA.jsx:29`).
   Sono **120, su 24 file**, mentre `lib/chartTheme.js` esiste e lo importano 7 grafici su 13.
   Finding I-6.
4. **«la LoginPage gestisce l'errore se il backend è giù?»** — **No**, ed è il finding più grave
   del giro (I-1), l'unico verificato dal vivo dall'inizio alla fine.

### I 9 finding, in breve

| # | Cosa vede l'utente | Dove |
|---|---|---|
| I-1 | Backend giù: preme «Connetti Spotify» e finisce su una pagina bianca senza uscita | `AuthContext.jsx:31-34`, `LoginPage.jsx:86` |
| I-2 | La scheda «Artisti unici» ricarica la dashboard invece di aprire la pagina artisti | `DashboardPage.jsx:174` |
| I-3 | La scheda «Streak» porta in cima a `/temporal`, l'ancora promessa non esiste | `DashboardPage.jsx:148` |
| I-4 | Esportazione dati e cancellazione account falliscono senza dire niente | `PrivacyPage.jsx:25,37-40` |
| I-5 | Tre riquadri vuoti con un testo di «nessun dato» scritto e mai mostrato | `TasteEvolutionPage.jsx:75,78,81,244,285` |
| I-6 | Cambiare il colore d'accento richiede di aprire 24 file | 24 file, `lib/chartTheme.js` |
| I-7 | Un item di lavoro aperto chiede una modifica che il codice ha già | `GenreTreemap.jsx:54-70`, `todo.md:17` |
| I-8 | Ogni indirizzo sbagliato scarica sulla dashboard, senza spiegazione | `App.jsx:146` |
| I-9 | «0/25» in cima a ogni pagina prima che sia stata fatta una misura | `Header.jsx:8` |

I-2 e I-8 si tengono per mano: è l'assenza di una pagina «non trovato» a rendere invisibile il
collegamento rotto. Se ne fosse corretto uno solo, conviene I-8, perché fa emergere gli altri.

### Verifiche eseguite

| Comando | Esito | Exit |
|---|---|---|
| `cd frontend && npm run lint` | nessun errore | 0 |
| `cd frontend && npm run build` | 2728 moduli, build in 4.00s, 49 entry PWA | 0 |
| `backend\.venv\Scripts\python.exe -m pytest -q` | **536 passati, 0 falliti** in 319.34s | **0** |
| `git status --porcelain` a fine ispezione | solo `docs/LOOP-BACKLOG.md` | 0 |
| porta 8001 in ascolto? | **no** — conferma che il 500 è «backend spento» | — |

Interprete backend: `C:\Users\fgioa\Desktop\PRO\progettoWrap\backend\.venv\Scripts\python.exe`
(Python 3.12.13). Il criterio dell'item «nessun file di codice modificato in questo giro» è
verificato dal `git status`: l'unico file toccato durante l'ispezione è il backlog, più questo
run-log.

La suite backend è stata rieseguita per intero anche se questo giro non tocca Python: serve a
dimostrare che l'ispezione non ha alterato nulla, non a scoprire regressioni che non possono
esistere.

### Breaker

**Non aperto.** Nessuna delle due condizioni: questo run è un `ITEM-DONE`, streak 0 contro soglia
3. Nessun `BREAKER: TRATTENUTO` da scrivere, nessuna riga `escalated:` pendente da chiudere.

### Conti con la guardia

Eseguito `--confirm-progress` **dopo** il commit: il contatore della guardia era a 1 su 3 e senza
azzeramento arriverebbe a emettere un allarme «backlog fermo» falso mentre il loop sta avanzando.

### Escalation al vault

Nessuna, e nessun lock preso. Il canale verso Fabio si apre solo per breaker o capolinea. Qui non
siamo in nessuno dei due, ma **il prossimo run lo sarà**: resta solo l'item-checkpoint, che scrive
`LOOP HALTED` e ferma il programma. Sarà quel run a prendere la corsia `inbox` e a scrivere la voce
`progetto-wrap-dev-loop:capolinea`, come prescrive il Passo 7. Niente da scrivere adesso.

### Remoto

`git rev-parse @{u}` a inizio run: `8616d0c6b50fac0db5a7d262e928c0df65a602ba`.
A fine run: **identico**. Nessun push partito, come deve essere.
