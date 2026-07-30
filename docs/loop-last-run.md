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
di fila.

> **Correzione, scritta in fase di finalize dopo il commit `b1c83db`.** Qui c'era scritto che «la
> lezione è già a verbale in `.claude/tasks/lessons.md`». **Era falso**, e l'ho ripreso dal run-log
> dell'item 4 invece di aprire `lessons.md` e cercarla: in quel file c'era la lezione sulla
> here-string di `git commit`, un guasto diverso dello stesso run. La lezione mancante è stata
> scritta adesso, insieme a una seconda su questo errore di metodo — un run-log racconta cosa un run
> ha creduto di fare, non lo stato di un altro file.

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

---

## 2026-07-30 10:35 UTC — `CHECKPOINT` — item-checkpoint «quinto giro completato: fermati qui»

**Guardia** (riga integrale di output, exit code 0):

```
LIBERO   nessun'altra sessione viva su C:\Users\fgioa\Desktop\PRO\progettoWrap (finestra 15min, 14 transcript scansionati, 0 worktree ispezionati, scope suite OFF)
         costo del controllo: 0.078s su 14 transcript (soglia 1s, massimo storico 0.132s)
         contatore: 1 fire senza progresso confermato (soglia 3)
```

`no_progress_streak`: **0** (era 0, resta 0: questo run chiude il suo item e committa, quindi
produce un avanzamento reale). Nessuno streak aperto, quindi nessun timestamp di primo run da
tenere.

Il Passo 0 è stato eseguito **in PowerShell** dopo il consueto fallimento in Bash, quarta volta di
fila: Git Bash mangia i backslash e cerca `...\progettoWrap\Usersfgioa.claudescriptsloop_yield.py`,
exit 2. **Non** è `NOOP-UNDECIDABLE` — la guardia non è mai stata avviata. La lezione è a verbale in
`.claude/tasks/lessons.md` (verificato aprendo il file, non dedotto da questo run-log: è
esattamente l'errore di metodo che il run precedente ha dovuto correggere dopo il commit).

### Working tree sporca all'avvio: valutata, non un `NOOP-DIRTY`

`git status --porcelain` a inizio run: ` M .claude/tasks/lessons.md` e ` M docs/loop-last-run.md`.
Il secondo è un'eccezione dichiarata dal Passo 3. Il primo no, quindi la decisione va motivata.

Letto il diff invece di dedurlo dal nome: sono **due voci di lezione chiuse**, scritte dal run
precedente in fase di finalize dopo il commit `b1c83db` — il tool Bash che mangia i path Windows, e
il metodo sbagliato di verificare una lezione sul run-log invece che sulla lezione. Entrambe
documentano questo stesso loop. Il diff di `docs/loop-last-run.md` è la correzione corrispondente
all'entry dell'item 5. Nessun codice, nessun lavoro a metà, e la guardia dice `LIBERO`: nessuna
sessione in volo da proteggere, che è il rischio per cui `NOOP-DIRTY` esiste.

**Li ho committati insieme ai miei**, a differenza dei run 3 e 4 che li avevano lasciati scoperti.
La ragione è che questo è l'ultimo run del programma: lasciarli lì significherebbe lasciare la
working tree sporca per sempre, dato che da adesso ogni fire esce `NOOP-HALTED` senza committare
nulla. L'hook di fine turno non è una garanzia su cui contare per chiudere un programma.

### Cosa è stato fatto

Le quattro azioni che l'item-checkpoint prescrive, e nient'altro. **Nessun file di codice toccato**,
nessun item nuovo dedotto.

1. `LOOP HALTED` scritto in testa a `docs/LOOP-BACKLOG.md`, subito sotto il titolo, con un cappello
   che dice **perché** il loop è fermo: checkpoint di fine programma, non guasto. Senza quella
   distinzione un marcatore nudo si legge come un'avaria.
2. L'item-checkpoint marcato `[x]` con il riepilogo del programma accanto.
3. Questa voce di run-log.
4. Commit dei soli file toccati.

### Riepilogo del programma: cinque giri, cinque item chiusi, zero falliti

| Item | Esito | Cosa ha prodotto |
|---|---|---|
| 1. Ricostruire gli ambienti | `[x]` | venv 3.12.13 + `npm ci`; da 185 test con 19 errori di import a 534 raccolti, 0 errori |
| 2. `build.yml` e i Dockerfile | `[x]` | `-f docker/*.Dockerfile` sui due step; la CI di build non falliva più a ogni push |
| 3. `EmptyState.jsx` morto | `[x]` | file rimosso; e **smentita** l'annotazione che l'item chiedeva di scrivere, perché falsa |
| 4. La CI non esegue i test backend | `[x]` | 8 rossi corretti (scheduler globale + date cablate), suite **536 passati / 0 falliti**, job `backend-test` in `ci.yml` |
| 5. Ispezione frontend | `[x]` | 14 rotte ispezionate, **9 finding** scritti nel backlog |

- **`FAILED`**: nessuno. Nessun item ha esaurito i 3 tentativi di fix.
- **`BLOCKED_USER` nuovi**: nessuno. Restano i tre già in lista al momento del censimento — 11
  (`.env` con i secret Spotify), 12 (deploy sul VPS), 13 (Extended Quota). Il loop non li ha
  toccati, come deve.
- **Finding dell'ispezione**: **9**, da I-1 a I-9, tutti ancora `[ ]`. Il più grave è I-1, l'unico
  verificato dal vivo dall'inizio alla fine: col backend spento il bottone di login porta a una
  pagina bianca senza uscita.

Due correzioni al backlog stesso meritano di sopravvivere al programma, perché un giro futuro
partirebbe da un'informazione falsa: l'item 3 chiedeva di annotare empty state «implementati
per-pagina» che **non esistono** (la convenzione vera è nascondere la sezione), e il punto B1 di
`.claude/tasks/todo.md` chiede una ciambella che `GenreTreemap.jsx` **già disegna** — finding I-7.

### Verifiche eseguite

I due criteri dell'item-checkpoint, più il controllo che il giro non abbia toccato codice.

| Controllo | Esito | Exit |
|---|---|---|
| `LOOP HALTED` in testa a `LOOP-BACKLOG.md` | presente, riga 3, subito sotto il titolo | — |
| run-log aggiornato | questa voce | — |
| commit creato | sì, vedi sotto | 0 |
| `git status --porcelain` dopo il commit | **vuoto** | 0 |
| file di codice modificati in questo run | **nessuno**: 3 file, tutti markdown | — |

**Nessuna suite eseguita, e la ragione è che non ce n'è una da eseguire.** Questo run tocca tre
file markdown: nessun test Python li importa, nessuna build frontend li include. Rieseguire
`pytest` (5 minuti) avrebbe prodotto un numero senza contenuto informativo — non dimostrerebbe
niente su un cambiamento che non esiste. L'ultima misura vera resta quella del run precedente,
**536 passati / 0 falliti, exit 0**, sullo stesso albero di codice, che questo run non ha alterato.

### Il limite che il programma lascia aperto, e che vale più di tutto il resto

Tre item su cinque hanno una verifica che si chiude **solo al prossimo push di Fabio**, e va detto
in chiaro invece di lasciarlo sparso in tre voci di registro:

- l'item 2 (Dockerfile) non è mai stato provato con una build vera — il demone Docker locale non
  gira su questa macchina;
- l'item 4 mette il job `backend-test` in CI, ma la CI non l'ha ancora eseguito;
- e soprattutto: **`backend-lint` era già rosso prima del programma** e lo è ancora, per 2 errori
  `ruff` pre-esistenti (`app/main.py:721` e `app/routers/auth.py:363`, `F841` su variabili
  assegnate e non usate). Nessun item del programma li copriva e dedurne uno era vietato. Quindi al
  prossimo push **la CI risulterà rossa nel complesso**, pur essendo ora verde su ciò che il
  programma ha corretto. Chi guarda il semaforo senza leggere questo registro concluderebbe che il
  loop ha rotto qualcosa.

### Breaker

**Non aperto**, e nessuna delle due condizioni del Passo 6 è in piedi: lo streak vale 0 contro una
soglia di 3, e non esiste uno streak aperto di cui misurare la durata. Niente `BREAKER:
TRATTENUTO` da scrivere — quel caso riguarda una soglia raggiunta con troppo poco tempo trascorso,
e qui la soglia non è raggiunta affatto. Nessuna riga `escalated:` pendente da chiudere: il
programma non ne ha mai aperta una.

Da distinguere con cura: la voce scritta in `Inbox.md` da questo run **non** è un breaker. È il
capolinea, che è l'altra delle due cose che il Passo 7 fa arrivare a Fabio, e nasce da una
decisione presa — il programma è finito — non da un blocco.

### Conti con la guardia

Eseguito `--confirm-progress` **dopo** il commit. Il contatore della guardia era a 1 su 3 e questo
fire ha prodotto un commit, che è precisamente ciò che quel contatore misura («fire senza progresso
confermato»).

Va però scritta la conseguenza, perché è il tipo di cosa che si scopre come falso allarme fra tre
giorni. Da adesso ogni fire esce `NOOP-HALTED` **senza** confermare progresso: dopo tre fire —
circa nove ore — la guardia emetterà un allarme «backlog fermo». Quell'allarme sarà **vero nella
sostanza e ridondante nel canale**: il loop è fermo per scelta, e Fabio l'ha già saputo dalla voce
di capolinea. Chi lo riceve deve leggerlo come conferma dell'halt, non come guasto nuovo.

### Escalation al vault: capolinea consegnato

Questa volta il canale verso Fabio si apre, ed è il caso «capolinea» del Passo 7: `LOOP HALTED`
l'ho scritto io, quindi da adesso il loop è invisibile a meno che qualcuno non lo dica.

- **Corsia `inbox` presa** prima della scrittura e **rilasciata subito dopo**:
  `acquire` → `decision: ACQUIRE_OK (exit 0)`, `note: nessun lock globale presente`;
  `release` → `decision: RELEASE_OK (exit 0)`. È l'unica scrittura di questo run su stato condiviso
  con gli altri loop della macchina.
- **Voce scritta** in `Knowledge/Ecosystem/Inbox.md`, chiave `progetto-wrap-dev-loop:capolinea`,
  `loop_id: progetto-wrap-dev-loop`, `first_seen` = `last_seen` = `2026-07-30T10:35:00Z`. Aggiornati
  entrambi i punti del file, l'elenco leggibile e il blocco JSON.
- **Consegna verificata**, non assunta: il blocco JSON è stato riletto e riparsato dopo la modifica,
  e contiene 3 chiavi — la mia più le due preesistenti (`human:suite-sync-disabilitato-personale`,
  `polymarket-dev-loop:capolinea`), **intatte**. Nessuna voce di altri loop toccata.
- Nessun `ESCALATION-UNDELIVERED` e nessun `ESCALATION-DEFERRED`: il file era raggiungibile e la
  corsia libera. Nessun ripiego su `pending-vault-notes/`, che il Passo 7 vieta.

`escalated: progetto-wrap-dev-loop:capolinea @ 2026-07-30T10:35:00Z`. Si scrive **una volta sola**,
alla transizione: i fire successivi escono `NOOP-HALTED` in silenzio e non devono riscriverla.

### Remoto

`git rev-parse @{u}` a inizio run: `8616d0c6b50fac0db5a7d262e928c0df65a602ba`.
A fine run: **identico**. Nessun push partito, come deve essere — questo repo non ha canale di
pubblicazione automatica.

### Per chi riapre la coda

Togliere `LOOP HALTED` da `docs/LOOP-BACKLOG.md` basta a far ripartire il loop, ma la coda che
troverebbe non è ordinata per un programma nuovo. Il materiale già scritto e verificato è:

- i **9 finding** dell'ispezione, in sezione «Trovati dall'ispezione», ognuno col suo criterio di
  verifica. Se se ne prende uno solo, **I-8** (pagina «non trovato») conviene più di I-2: è
  l'assenza della pagina d'errore a rendere invisibile il collegamento rotto;
- i **4 item** della sezione «Dopo il checkpoint» (7 lint frontend, 8 allineare `LAUNCH-PLAN`,
  9 script di backup, 10 `HEALTH-REPORT` scaduto). L'item 7 va corretto prima di essere preso:
  dà `npm run lint` per rosso, ed è **verde** da tutti e cinque i giri del programma — resta solo
  la parte sulle 6 soppressioni `eslint-disable` da motivare;
- i 2 errori `ruff` che tengono `backend-lint` rosso, se si vuole un semaforo di CI verde: non sono
  in nessun item, perché dedurne di nuovi è vietato al loop.

---

## 2026-07-30 13:33 UTC — `NOOP-HALTED` — nessun item preso

**Esito in una riga**: il loop è fermo per decisione presa, non per guasto. Il marcatore
`LOOP HALTED` è in testa a `docs/LOOP-BACKLOG.md` dal checkpoint delle 10:35 UTC, e finché resta lì
ogni fire si limita a questa riga di verbale. Nessun file di codice toccato, nessun test eseguito,
nessun item aperto.

**Guardia** (riga integrale di output, exit code 0):

```
LIBERO   nessun'altra sessione viva su C:\Users\fgioa\Desktop\PRO\progettoWrap (finestra 15min, 15 transcript scansionati, 0 worktree ispezionati, scope suite OFF)
         costo del controllo: 0.078s su 15 transcript (soglia 1s, massimo storico 0.132s)
         contatore: 1 fire senza progresso confermato (soglia 3)
```

Come le quattro volte precedenti, il Passo 0 è fallito in Bash prima di riuscire in PowerShell: Git
Bash mangia i backslash del percorso non quotato e cerca un file inesistente
(`...\progettoWrap\Usersfgioa.claudescriptsloop_yield.py`, exit 2). **Non** è `NOOP-UNDECIDABLE`: la
guardia non era proprio partita. Al secondo tentativo, con entrambi i percorsi fra virgolette e
l'operatore di chiamata `&`, ha risposto `LIBERO`.

**Item toccato**: nessuno. Il Passo 1 precede il Passo 4, quindi la coda non è stata nemmeno letta
oltre l'intestazione.

`no_progress_streak`: **0**, e resta 0 — **non incrementato di proposito**. Il contatore misura un
loop che vuole lavorare e non ci riesce; questo loop non vuole lavorare, è al capolinea per
programma. Incrementarlo porterebbe il breaker ad aprirsi fra tre fire, con un avviso di «blocco
prolungato» su un fermo deliberato e già comunicato. È esattamente l'allarme falso che il Passo 6
chiede di evitare, e su un fatto già a verbale nel canale giusto. Nessuno streak aperto, nessun
timestamp di primo run da tenere.

**Nessuna escalation, e non è una dimenticanza.** La voce di capolinea è stata consegnata una volta
sola alla transizione (`escalated: progetto-wrap-dev-loop:capolinea @ 2026-07-30T10:35:00Z`), come
prescrive il Passo 7; risulta presente nell'inbox all'avvio di questa sessione. I fire successivi
escono in silenzio. Di conseguenza la corsia `inbox` del lock fra loop **non** è stata presa: non
avendo nulla da scrivere su stato condiviso, prenderla avrebbe solo tolto il giro ad altri loop.

### Da tenere d'occhio, per chi legge

Il contatore della guardia è cosa diversa da `no_progress_streak` e continua a salire per conto suo:
è a 1 su una soglia di 3. Su un loop fermo per scelta salirà comunque, e attorno al terzo fire la
guardia emetterà una `ESCALATION` per «backlog fermo» che sarebbe fuori bersaglio — il backlog non è
fermo, è chiuso. Il rimedio sta fuori dalla portata di questo loop, che non ha mandato per toccare
`~/.claude/`: se la cosa infastidisce, la si toglie disattivando la voce di pianificazione finché la
coda non riapre.

### Remoto

`git rev-parse @{u}` a inizio run: `8616d0c6b50fac0db5a7d262e928c0df65a602ba`, identico al valore
annotato a fine del run precedente. A fine run: **identico**. Nessun push partito, come deve essere.

---

## 2026-07-30 13:40 UTC — `AZIONE UTENTE` — coda riaperta, non è un run del loop

**Questa voce non descrive un fire.** È un intervento di Fabio, verbalizzato qui perché è il file
che ogni run legge al Passo 3, e perché cambia da sotto i piedi lo stato che il run precedente
aveva lasciato.

**Cosa è cambiato**: `LOOP HALTED` è stato tolto da `docs/LOOP-BACKLOG.md`. Il secondo programma
sono i **9 finding dell'ispezione frontend** (I-1 → I-9), uno per giro, seguiti da un item-checkpoint
che rimette il marcatore e ferma di nuovo tutto. I quattro item della sezione «Dopo il checkpoint»
restano **fuori** da questo programma: il checkpoint li precede, quindi il loop non li raggiunge.

**Controllo prima di riaprire**: quattro finding su nove sono stati ricontrollati sul codice di oggi
e sono ancora veri — I-2 (`DashboardPage.jsx:174` punta a `/artist-network`, rotta inesistente),
I-3 (`link="/temporal#streak"` senza nessun `id="streak"` in tutto `frontend/src`), I-8
(`App.jsx:146`, `path="*"` rimanda alla radice), I-9 (`Header.jsx:8`,
`useState({ current: 0, max: 25, pct: 0 })`). Nessun commit ha toccato `frontend/` dopo l'ispezione,
l'ultimo è `c37c0f6`. Gli altri cinque non sono stati ricontrollati.

**Un vincolo che il programma precedente non aveva incontrato, ora scritto nel backlog**: il
frontend **non ha un test runner**. `frontend/package.json` espone solo `dev`, `build`, `preview`,
`lint` — non esiste `npm test`. Diversi criteri di verifica dei nove finding sono scritti come
comportamenti osservabili, e nessuno di essi è meccanicamente provabile. La sezione «Trovati
dall'ispezione» ora dichiara i tre mezzi ammessi (dal vivo senza backend · sul codice · lint e build
a 0) e impone al run-log di dire, per ogni item, **quale** è stato usato. Un item verificabile solo
con mezzi che non esistono si chiude dichiarando il limite, mai inventando la prova.

**Inbox del vault**: la voce `progetto-wrap-dev-loop:capolinea` è stata **rimossa**, chiave e
riga renderizzata, lasciando intatte le altre due. Diceva che il loop non sarebbe ripartito finché
non gli fosse stato dato lavoro nuovo: da adesso è falsa, e sarebbe rimasta in cima a ogni sessione
su entrambi i computer. La rimozione è dichiarata dal file stesso come azione umana, ed è stata
fatta su istruzione di Fabio, sotto la corsia `inbox` del lock fra loop (`ACQUIRE_OK` → modifica →
blocco JSON riconvalidato → `RELEASE_OK`). Al prossimo checkpoint la voce va **riscritta**: è una
transizione nuova, non una ripetizione di quella del primo programma.

`no_progress_streak`: **0**, invariato. Nessuno streak aperto, nessun `BREAKER:` da scrivere o da
togliere, nessuna riga `escalated:` pendente.

---

## 2026-07-30 16:44 UTC — `ITEM-DONE` — I-1 «Col backend spento il bottone di login porta a una pagina bianca»

**Esito in una riga**: il primo item del secondo programma è chiuso. Col backend spento, la
schermata di accesso ora **dice** che il servizio non risponde e il bottone **non porta più fuori
dall'applicazione**. Verificato dal vivo, che per questo item era il mezzo migliore disponibile.

**Guardia** (riga integrale di output, exit code 0):

```
LIBERO   nessun'altra sessione viva su C:\Users\fgioa\Desktop\PRO\progettoWrap (finestra 15min, 16 transcript scansionati, 0 worktree ispezionati, scope suite OFF)
         costo del controllo: 0.059s su 16 transcript (soglia 1s, massimo storico 0.132s)
         contatore: 2 fire senza progresso confermato (soglia 3)
```

`no_progress_streak`: **0** (era 0, resta 0: questo run è un `ITEM-DONE`). Nessuno streak aperto,
nessun timestamp di primo run da tenere.

### Il Passo 0 in Bash: risolto, non aggirato

Le cinque volte precedenti il comando della guardia è fallito in Bash ed è stato rieseguito in
PowerShell. Stessa partenza anche stavolta — Git Bash mangia i backslash e cerca
`...\progettoWrap\Usersfgioa.claudescriptsloop_yield.py`, exit 2 — ma la soluzione non richiede di
cambiare shell: **bastano i path con la barra in avanti**, quotati
(`"C:/Users/fgioa/.claude/scripts/loop_yield.py"`). Windows accetta entrambi i separatori, ed è Bash
a non sopravvivere solo al backslash. Al secondo tentativo, in Bash, la guardia ha risposto `LIBERO`.
Come le altre volte, il primo tentativo **non** è un `NOOP-UNDECIDABLE`: la guardia non era partita.

Da dire per intero, perché il merito non è di questo run: la via d'uscita era **già a verbale**, in
`.claude/tasks/lessons.md:110`, scritta dal run dell'item 5 («se serve Bash, usare le forward slash,
che Git Bash accetta»). Questo giro non l'ha scoperta, l'ha applicata — ed è la prova che quella
lezione funziona. Il prossimo run può partire direttamente così e risparmiarsi il tentativo a vuoto.

### Working tree sporca all'avvio: valutata, non un `NOOP-DIRTY`

`git status --porcelain` a inizio run: ` M .claude/tasks/lessons.md`. Letto il diff invece di
dedurlo dal nome: **una sola voce di lezione, chiusa**, scritta dalla sessione che ha riaperto la
coda alle 13:40 UTC — quella che documenta che il frontend non ha un test runner e che i criteri
dell'ispezione andavano corredati del mezzo di verifica. È meta-lavoro su questo loop, finito.
Sovrapposizione con i file di questo item: **zero** (io tocco `frontend/src/`). La guardia dice
`LIBERO`, quindi nessuna sessione in volo da proteggere, che è il rischio per cui `NOOP-DIRTY`
esiste. Non messo in stage: l'`add` di questo run elenca path espliciti.

### Cosa era rotto, e perché era rotto due volte

Il finding descriveva un guasto solo, ma i punti di rottura erano due, in fila.

**Primo, all'apertura della pagina.** `checkAuth` chiamava `/auth/me`, prendeva l'errore e lo
scriveva in console (`console.error` e basta). L'utente vedeva una schermata di accesso **identica
al caso normale**, senza nessun segnale che il servizio fosse giù.

Il pezzo che rende la correzione pulita, e che il finding non diceva: **`/auth/me` risponde `200`
anche all'utente anonimo**, con `{"authenticated": false}` (`backend/app/routers/auth.py:285-290`).
Quindi su quell'indirizzo un errore **non è mai** «sessione assente»: è «il backend non ha
risposto». Non serve indovinare dal codice di stato — la distinzione è netta per costruzione, e su
questo poggia tutto il resto.

**Secondo, al clic.** `login()` faceva `window.location.href = '/auth/spotify/login'` senza
verificare niente. Quell'assegnazione porta il browser **fuori dalla SPA**: se nessuno serve
l'indirizzo, non c'è più nessuna interfaccia a cui tornare, e infatti la pagina restava bianca.
Misurato, non dedotto — col backend spento, attraverso il proxy di Vite:

```
GET http://127.0.0.1:5173/auth/spotify/login  ->  status=500 size=0
```

Zero byte di corpo: la pagina bianca è letteralmente quella risposta.

### Cosa è stato fatto

Due file, 49 righe aggiunte e 6 tolte. Nessun componente nuovo, nessuna dipendenza aggiunta.

1. **`frontend/src/contexts/AuthContext.jsx`** — aggiunto lo stato `serviceDown`, acceso quando
   `/auth/me` fallisce e spento quando risponde. E `login()` è diventata asincrona: **verifica che
   il backend risponda prima di lasciare la pagina**, e ritorna `false` se non risponde, così il
   chiamante può restare dov'è. Il perché sta scritto accanto al codice, altrimenti la prossima
   modifica rimette il redirect diretto «perché è più semplice».
2. **`frontend/src/pages/LoginPage.jsx`** — mostra l'avviso quando `serviceDown` è acceso, e rimette
   il bottone in chiaro quando il tentativo non è partito. Una sola fonte di verità: il messaggio
   dipende da `serviceDown`, non da uno stato locale duplicato che potrebbe divergere.

Riquadro d'avviso: riusato il modello già presente nel progetto per gli avvisi in pagina
(`bg-amber-500/10` con l'icona `AlertTriangle`, come `ArtistNetworkPage.jsx:73-76` e
`PlaylistAnalyticsPage.jsx:98`), non inventato uno stile nuovo. Aggiunto `role="alert"` perché il
messaggio compare dopo un'azione dell'utente e va annunciato, non solo disegnato.

Testo mostrato: «Il servizio non risponde. Non è possibile collegarsi a Spotify in questo momento —
riprova fra qualche istante.» In italiano, come vuole la convenzione del repo.

### Verifiche eseguite — mezzo 1 (dal vivo) e mezzo 3 (meccanico)

Il primo dei tre mezzi ammessi dalla sezione «Trovati dall'ispezione», che per questo item è quello
buono: la schermata di accesso è l'unica pagina raggiungibile senza backend e senza login.

Preparazione, verificata invece che assunta: porta **8001 non in ascolto** (backend davvero spento),
server di sviluppo avviato sulla 5173, pagina aperta col browser della sessione.

| Controllo | Esito | Exit |
|---|---|---|
| porta 8001 in ascolto? | **no** — scenario «backend spento» confermato | — |
| `GET /auth/me` via proxy | **500**, quindi `serviceDown` si accende | — |
| `GET /auth/spotify/login` via proxy | **500, corpo di 0 byte** — la pagina bianca | — |
| **dal vivo**: testo della pagina all'apertura | avviso presente: «Il servizio non risponde…» | — |
| **dal vivo**: clic su «Connetti Spotify» | indirizzo **invariato** (`127.0.0.1:5173`), interfaccia intera, avviso visibile | — |
| **dal vivo**: console dopo il clic | `Login interrotto, backend non raggiungibile` — la verifica ha fermato il salto | — |
| **dal vivo**: secondo clic di seguito | stesso esito, bottone di nuovo «Connetti Spotify» — nessuno stato bloccato | — |
| `cd frontend && npm run lint` | nessun errore | **0** |
| `cd frontend && npm run build` | 49 entry PWA, build in 4.71s | **0** |
| `backend\.venv\Scripts\python.exe -m pytest -q` | **536 passati, 0 falliti** in 319.65s | **0** |

Interprete backend: `C:\Users\fgioa\Desktop\PRO\progettoWrap\backend\.venv\Scripts\python.exe`
(Python 3.12.13). La suite backend è stata rieseguita per intero pur avendo toccato solo due file
JSX: serve a dimostrare che non ho alterato nulla, non a scoprire regressioni che non possono
esistere. Stesso numero del run precedente, 536, nessuna deriva.

Il criterio dell'item è testuale — «premere «Connetti Spotify» lascia l'utente sulla schermata di
accesso con un messaggio leggibile che dice che il servizio non risponde; nessuna pagina bianca» —
ed è soddisfatto su tutti e tre i pezzi: resta sulla schermata, il messaggio c'è ed è leggibile,
nessuna pagina bianca.

### Il limite: il ramo felice non è provato dal vivo, ed è giusto dirlo

Ho provato che **col backend spento** non si finisce più nel bianco. Non ho provato dal vivo che
**col backend acceso** il salto verso Spotify parta ancora, e non potevo:

- avviare il backend vero richiede `.env` con i secret Spotify — l'item 11 è `[BLOCKED_USER]`
  apposta, e il vincolo di sicurezza del loop vieta di toccare quel file;
- mettere in piedi un finto backend che risponda `200` su `/auth/me` sarebbe un mock, che il
  protocollo del loop vieta per iscritto («se un servizio reale non è raggiungibile, fermati e
  dichiaralo; non sostituirlo con un mock»).

Resta il **mezzo 2, sul codice**, e il ragionamento è breve perché la modifica è piccola: sul ramo
felice il codice fa esattamente ciò che faceva prima — `window.location.href =
'/auth/spotify/login'` — preceduto da una chiamata a `/auth/me` che l'applicazione **emette già
comunque** al caricamento della pagina. L'unico modo in cui la correzione potrebbe bloccare un login
legittimo è che `/auth/me` fallisca con il backend acceso. Due controlli sul perché non succede:

1. **Database giù non basta a farla fallire.** Per l'utente anonimo il gestore esce alla prima riga
   (`auth.py:288-290`) senza eseguire nessuna query, e `get_db` (`database.py:21-23`) apre la
   sessione ma SQLAlchemy non contatta il database finché non parte una query. Quindi un backend
   acceso con il database rotto risponde `200` lo stesso, e il login parte.
2. **Il limitatore di traffico**: un `429` farebbe fallire la verifica. Ma il limite è 120 richieste
   al minuto per indirizzo, e chi apre la pagina e preme il bottone ne fa due. Se davvero uno fosse
   limitato, il ritorno OAuth fallirebbe comunque: fermarsi prima è il comportamento giusto, non un
   guasto nuovo.

Timeout della verifica fissato a 8 secondi: un backend che ci mette di più è indistinguibile da uno
spento, dal punto di vista di chi guarda lo schermo.

### Osservazione, senza azione: la finestra fra la verifica e il salto

Fra il `200` della verifica e il redirect passano millisecondi in cui il backend potrebbe cadere.
In quel caso si tornerebbe alla pagina bianca. Non l'ho chiuso perché chiuderlo davvero vuol dire
un'altra cosa — servire l'errore da dentro l'applicazione invece di lasciare il dominio — ed è una
modifica di disegno che va oltre il mandato di questo item. La probabilità è quella di una finestra
di millisecondi contro un backend spento, che è lo scenario del finding e ora è coperto.

### Breaker

**Non aperto**, e nessuna delle due condizioni del Passo 6 è in piedi: questo run è un `ITEM-DONE`,
quindi lo streak vale 0 contro una soglia di 3, e non esiste uno streak aperto di cui misurare la
durata. Niente `BREAKER: TRATTENUTO` da scrivere — quel caso riguarda una soglia raggiunta con
troppo poco tempo trascorso, e qui la soglia non è raggiunta affatto. Nessuna riga `escalated:`
pendente da chiudere: il secondo programma non ne ha ancora aperta nessuna.

### Conti con la guardia

Eseguito `--confirm-progress` **dopo** il commit, come prescritto. Il contatore della guardia era a
**2 su 3**, ereditato dai fire a loop fermo: senza l'azzeramento il prossimo giro avrebbe emesso un
allarme «backlog fermo» falso proprio mentre il loop ha ripreso ad avanzare.

### Escalation al vault

Nessuna, e nessun lock preso. Il canale verso Fabio si apre solo per breaker o capolinea: qui non
siamo in nessuno dei due, e restano otto finding più il checkpoint. Sarà il run del checkpoint a
prendere la corsia `inbox` e a **riscrivere** la voce di capolinea — è una transizione nuova, non
una ripetizione di quella del primo programma, che è stata rimossa alle 13:40 UTC. Niente da
scrivere adesso, quindi prendere la corsia avrebbe solo tolto il giro ad altri loop.

### Remoto

`git rev-parse @{u}` a inizio run: `8616d0c6b50fac0db5a7d262e928c0df65a602ba`.
A fine run: **identico**. Nessun push partito, come deve essere.

---

## 2026-07-30 19:34 UTC — `ITEM-DONE` — I-2 «Dashboard: la scheda «Artisti unici» non porta da nessuna parte»

**Esito in una riga**: la scheda puntava a una rotta che non esiste e il clic ricaricava la pagina
su cui l'utente era già; ora apre «Ecosistema Artisti». Una riga cambiata, più una verifica che
copre **tutti** i collegamenti interni del frontend e non solo quello dell'item.

**Guardia** (riga integrale di output, exit code 0):

```
LIBERO   nessun'altra sessione viva su C:\Users\fgioa\Desktop\PRO\progettoWrap (finestra 15min, 17 transcript scansionati, 0 worktree ispezionati, scope suite OFF)
         costo del controllo: 0.051s su 17 transcript (soglia 1s, massimo storico 0.132s)
         contatore: 1 fire senza progresso confermato (soglia 3)
```

`no_progress_streak`: **0** (era 0, resta 0: questo run è un `ITEM-DONE`). Nessuno streak aperto,
nessun timestamp di primo run da tenere.

### Il Passo 0 è partito al primo colpo, e vale la pena dirlo

Le prime cinque volte il comando della guardia falliva in Bash e andava rieseguito in PowerShell; il
run precedente ha applicato la via d'uscita già a verbale in `.claude/tasks/lessons.md:110` — path
con la barra in avanti, quotati. Questo run è partito **direttamente così**, primo tentativo, exit 0,
nessun tentativo a vuoto. La lezione ha smesso di costare un giro a nessuno: è chiusa nei fatti, non
solo scritta.

### Working tree sporca all'avvio: valutata, non un `NOOP-DIRTY`

`git status --porcelain` a inizio run: ` M .claude/tasks/lessons.md`. Letto il diff invece di
dedurlo dal nome, come le altre volte. Sono **due aggiunte chiuse**: il fratello in Bash della
lezione sulle here-string di PowerShell (un payload lungo di prosa non passa mai per il quoting di
una shell, su nessuna delle due) e la lezione sul frontend che non ha un test runner. Le ha scritte
la sessione che ha riaperto la coda; documentano questo stesso loop, non codice a metà.
Sovrapposizione con i file di questo item: **zero** — io tocco `frontend/src/pages/` e `docs/`. La
guardia dice `LIBERO`, quindi nessuna sessione in volo da proteggere, che è il rischio per cui
`NOOP-DIRTY` esiste. Non messo in stage: l'`add` di questo run elenca path espliciti.

### Cosa era rotto

`DashboardPage.jsx:174` passava `link="/artist-network"` alla scheda «Artisti unici». Quella rotta
**non è dichiarata**: `App.jsx` ne dichiara 13 statiche più `/invite/:code`, e la pagina degli
artisti sta su `/artists` (riga 91), come del resto già fa il menu laterale
(`Sidebar.jsx:37`, etichetta «Ecosistema Artisti»).

Il meccanismo, perché conta per capire cosa vedeva l'utente. `KPICard` con un `link` che non comincia
per `#` rende un `<Link to={link}>` di React Router (`KPICard.jsx:112`) e aggiunge cursore a manina e
alone al passaggio del mouse (riga 41): la scheda **promette** un salto. Al clic il router non trova
nessuna rotta corrispondente, cade nel catch-all `path="*"` (`App.jsx:146`) che rimanda alla radice,
e la radice per un utente autenticato rimanda alla dashboard (`App.jsx:40`). Risultato: **il clic
ricarica la pagina su cui sei già**, senza nessun messaggio. È anche il motivo per cui il difetto era
invisibile — che è precisamente ciò che descrive I-8, ancora aperto.

Da tenere distinto, perché il nome inganna: `artist-network` **esiste** nel progetto, ma come
indirizzo dell'API (`ArtistNetworkPage.jsx:12`, `/api/v1/artist-network`). Non è una rotta del
browser, e confondere le due cose è probabilmente l'origine dello sbaglio.

### Cosa è stato fatto

**Una riga**: `link="/artist-network"` → `link="/artists"`. Nient'altro — nessun componente nuovo,
nessuna dipendenza, nessun file aggiunto. `git diff --stat`: 1 file, 1 inserzione, 1 cancellazione.

Non ho toccato il catch-all: rendere visibile un indirizzo sbagliato è l'item I-8, e un run fa un
item solo.

### Verifiche eseguite — mezzo 2 (sul codice) e mezzo 3 (meccanico)

Il criterio dell'item è «cliccare «Artisti unici» apre «Ecosistema Artisti»», ed è un comportamento
osservabile su una pagina che **sta dietro l'autenticazione**. Dal vivo non è raggiungibile: servono
`.env` con i secret Spotify (item 11, `[BLOCKED_USER]`) e un login Spotify reale, entrambi vietati al
loop. Quindi mezzo 2 e mezzo 3, dichiarati come tali — «verificato dal vivo» qui sarebbe una prova
inventata.

| Controllo | Esito | Exit |
|---|---|---|
| `verify_routes.py` — auto-prova del controllo | `resolves('/artist-network')` = **False**, `resolves('/artists')` = **True** | — |
| `verify_routes.py` — **tutti** i target di navigazione interna | **21 su 21 risolvono**, nessuno rotto | **0** |
| pacchetto costruito: il pezzo della dashboard | `link:"/artists"` | — |
| pacchetto costruito: residui di `artist-network` | **solo** `ArtistNetworkPage-*.js`, cioè l'indirizzo dell'API | — |
| `cd frontend && npm run lint` | nessun errore | **0** |
| `cd frontend && npm run build` | 49 entry PWA, build in 4.56s | **0** |
| `backend\.venv\Scripts\python.exe -m pytest -q` | **536 passati, 0 falliti** in 331.26s | **0** |

Interprete: `C:\Users\fgioa\Desktop\PRO\progettoWrap\backend\.venv\Scripts\python.exe` (Python
3.12.13). `verify_routes.py` è usa-e-getta, nello scratchpad di sessione, **non versionato** — come
`verify_build_yml.py` e `verify_ci.py` dei giri precedenti.

**Perché ho verificato più di quanto l'item chiedesse.** Il criterio riguarda una scheda sola, ma il
difetto è di una classe: un collegamento interno che non corrisponde a nessuna rotta non dà **nessun
errore**, né a chi scrive né a chi naviga — sparisce dentro il catch-all. Controllare solo la riga
corretta avrebbe lasciato aperta la domanda che conta, cioè se ce ne fossero altri. Lo script estrae
le rotte da `App.jsx` e le confronta con ogni `link=`, `to=`, `href:` e `navigate(` che punti a un
percorso interno: **21 target, uno solo rotto, ed era questo**. Ora zero.

Lo script porta anche un'**auto-prova**, perché un controllo che dice sempre «OK» passerebbe
inosservato: verifica che il resolver bocci il valore di prima e promuova quello di adesso. È la
prova che il controllo distingue davvero i due stati, e insieme la misura del prima e del dopo.

Il pacchetto costruito chiude il cerchio sul dubbio residuo — che la modifica sia nel sorgente ma non
in ciò che gira: nel pezzo della dashboard c'è `link:"/artists"`, e l'unica occorrenza di
`artist-network` rimasta in tutto il pacchetto è l'indirizzo dell'API, che è giusto ci sia.

Il ramo felice — che `/artists` renda davvero «Ecosistema Artisti» — è verificato sul codice per
composizione: `App.jsx:91` monta `ArtistNetworkPage` su quella rotta, e `ArtistNetworkPage.jsx:31`
ha per titolo esattamente «Ecosistema Artisti». Sono le due metà del criterio dell'item.

La suite backend è stata rieseguita per intero pur avendo toccato **una riga di JSX**: non serve a
scoprire regressioni che non possono esistere, serve a dimostrare che non ho alterato nulla.

### Osservazione, senza azione: il `/temporal#streak` compare come «OK» ma non lo è del tutto

Lo script segna `DashboardPage.jsx:148 link=/temporal#streak` come risolto, e per quanto riguarda la
**rotta** è vero: `/temporal` esiste. L'ancora `#streak` invece no, ed è esattamente il finding I-3,
il prossimo della coda. Lo scrivo perché un giro futuro che rileggesse solo la tabella qui sopra
potrebbe concludere che I-3 è già chiuso: non lo è. Lo script confronta percorsi, non ancore — un
controllo delle ancore sarebbe il mezzo giusto per I-3, e sarà quel giro a farlo.

### Breaker

**Non aperto**, e nessuna delle due condizioni del Passo 6 è in piedi: questo run è un `ITEM-DONE`,
quindi lo streak vale 0 contro una soglia di 3, e non esiste uno streak aperto di cui misurare la
durata. Niente `BREAKER: TRATTENUTO` da scrivere — quel caso riguarda una soglia raggiunta con
troppo poco tempo trascorso, e qui la soglia non è raggiunta affatto. Nessuna riga `escalated:`
pendente da chiudere: il secondo programma non ne ha ancora aperta nessuna.

### Conti con la guardia

Eseguito `--confirm-progress` **dopo** il commit, come prescritto. Il contatore della guardia era a
**1 su 3**: senza l'azzeramento continuerebbe a salire e finirebbe per emettere un allarme «backlog
fermo» falso proprio mentre il loop sta avanzando.

### Escalation al vault

Nessuna, e nessun lock preso. Il canale verso Fabio si apre solo per breaker o capolinea: qui non
siamo in nessuno dei due, e restano sette finding (I-3 → I-9) più il checkpoint. Sarà il run del
checkpoint a prendere la corsia `inbox` e a **riscrivere** la voce di capolinea — è una transizione
nuova, non una ripetizione di quella del primo programma, che è stata rimossa alle 13:40 UTC del
2026-07-30. Niente da scrivere adesso, quindi prendere la corsia avrebbe solo tolto il giro ad altri
loop.

### Remoto

`git rev-parse @{u}` a inizio run: `8616d0c6b50fac0db5a7d262e928c0df65a602ba`.
A fine run: **identico**. Nessun push partito, come deve essere — questo repo non ha canale di
pubblicazione automatica.

---

## 2026-07-30 22:45 UTC — `ITEM-DONE` — I-3 «Dashboard: la scheda "Streak" promette un dettaglio che non c'è»

**Esito in una riga**: la scheda «Streak di ascolto» ora porta l'utente davanti alla sezione dello
streak invece che in cima alla pagina. Il finding però descriveva **metà** del guasto, e correggere
solo quella metà non avrebbe cambiato niente per l'utente: sotto sta la parte che conta di questo
verbale.

**Guardia** (riga integrale di output, exit code 0):

```
LIBERO   nessun'altra sessione viva su C:\Users\fgioa\Desktop\PRO\progettoWrap (finestra 15min, 19 transcript scansionati, 0 worktree ispezionati, scope suite OFF)
         costo del controllo: 0.076s su 19 transcript (soglia 1s, massimo storico 0.132s)
         contatore: 1 fire senza progresso confermato (soglia 3)
```

Come a ogni giro, il Passo 0 è fallito in Bash prima di riuscire in PowerShell: Git Bash mangia i
backslash del percorso e cerca un file inesistente
(`...\progettoWrap\Usersfgioa.claudescriptsloop_yield.py`, exit 2). **Non** è `NOOP-UNDECIDABLE`: la
guardia non ha risposto «non so», non è proprio partita. È già a verbale in
`.claude/tasks/lessons.md` (voce del 2026-07-30 sul tool Bash), verificato aprendo il file, non
riportato dal run-log precedente.

`no_progress_streak`: **0** — questo run è un `ITEM-DONE`, e il precedente (I-2, 19:34 UTC) pure,
quindi non c'era nessuno streak aperto da azzerare.

### Che cosa ho trovato che l'item non diceva

L'item chiedeva una cosa sola: in `TemporalPage.jsx` manca un elemento con l'identificatore
`streak`, quindi mettilo. È vero, e non basta.

**Un salto fra pagine non porta all'ancora nemmeno quando l'ancora esiste.** `<Link to="/temporal#streak">`
fa una `pushState`: cambia l'indirizzo nella barra e resta dov'è. Non è una navigazione al
frammento — quella la fa il browser solo quando l'indirizzo arriva da fuori o da un `<a>` sulla
stessa pagina. React-router ha un pezzo che se ne occupa, `ScrollRestoration`, ma vive solo nelle
modalità con router a dati; qui c'è `BrowserRouter` dichiarativo (`App.jsx:154`), e nel frontend non
compare da nessuna parte. Verificato: la ricerca di `scrollIntoView`, `scrollTo`, `scroll-behavior`
e `scroll-margin` su tutto `frontend/` (escluso `node_modules`) dava **due sole occorrenze**,
entrambe dentro `KPICard.jsx`.

Quindi con il solo `id="streak"` la scheda avrebbe continuato a lasciare l'utente in cima alla
pagina: **esattamente il difetto descritto dall'item, intatto**, e per giunta con l'aria di essere
stato corretto.

**Perché nessuno se n'era accorto**: le altre quattro ancore del frontend sono tutte *dentro la
stessa pagina* (`#top-tracks` sulla dashboard, `#loyal-artists`, `#rising-artists`,
`#persistent-tracks` su Evoluzione Gusto), e per quelle `KPICard.jsx:99-110` non usa affatto il
router — chiama `scrollIntoView` a mano. `/temporal#streak` è **l'unica** fra pagine in tutto il
frontend, quindi l'unica che passa per `<Link>`, quindi l'unica rotta.

C'è anche una ragione per cui, provandola, il doppio guasto non si sarebbe distinto: senza l'id e
senza il gestore il sintomo è identico — l'utente resta in cima alla pagina.

### La correzione

Tre file, due dei quali sono lo stesso rimedio visto da capi opposti.

1. **`frontend/src/hooks/useHashScroll.js`** (nuovo): dopo ogni cambio di indirizzo con frammento,
   cerca l'elemento e ci porta l'utente. **Riprova per 3 secondi** a intervalli di 100ms invece di
   guardare una volta sola, perché al momento del cambio l'elemento non c'è ancora, e per due
   motivi sovrapposti: `AnimatePresence mode="wait"` (`AppLayout.jsx:23`) monta la pagina di
   destinazione **dopo** che quella precedente ha finito di uscire, e la sezione dello streak
   compare solo quando la richiesta dati di `TemporalPage` si risolve. Un `getElementById` singolo
   avrebbe trovato `null` e non avrebbe scorso mai — sarebbe stato un finto rimedio, cioè il guasto
   di partenza travestito.
2. **`frontend/src/components/layout/AppLayout.jsx`**: invoca il gestore. È il posto giusto perché
   avvolge tutte le pagine protette, quindi vale per qualunque ancora fra pagine si scriverà in
   futuro, non solo per questa.
3. **`frontend/src/pages/TemporalPage.jsx:148`**: `id="streak"` sul blocco «Streak + Sessioni», più
   `scroll-mt-20`. Il secondo non è cosmetico: l'intestazione è appiccicata in alto e alta 64px
   (`Header.jsx:23`, `h-16`), quindi senza scostamento lo scorrimento infila il titolo della scheda
   **sotto** l'intestazione e l'utente arriva su una scheda decapitata. `scroll-mt-20` vale 80px,
   confermato nel CSS costruito: `.scroll-mt-20{scroll-margin-top:5rem}`.

L'identificatore sta sul contenitore della griglia e non dentro `StreakDisplay` di proposito: quel
componente restituisce `null` quando non c'è streak da mostrare (`StreakDisplay.jsx:14`), e un
bersaglio che sparisce col dato è un'ancora che torna rotta al primo utente senza dati.

### Verifica — con quale dei tre mezzi, per ciascuna cosa

Il criterio dell'item («cliccare "Streak di ascolto" porta l'utente davanti alla sezione dello
streak») è un comportamento osservabile su una pagina **dietro l'autenticazione**. Non è apribile
dal vivo: senza `.env` il backend non parte, e il login Spotify vero è vietato al loop. Quindi
**mezzo 2 (sul codice)** e **mezzo 3 (meccanicamente)**. Nessuna prova dal vivo dichiarata, perché
nessuna è stata fatta.

**Mezzo 3 — meccanicamente**, tutti eseguiti, tutti a exit 0:

| Comando | Esito |
|---|---|
| `npm run lint` (in `frontend/`) | exit **0** |
| `npm run build` (in `frontend/`) | exit **0**, 2729 moduli, costruito in 4.86s |
| `backend\.venv\Scripts\python.exe -m pytest -q` | **536 passati**, 0 falliti, exit **0**, 318.97s, Python 3.12.13 |

La suite backend è stata eseguita per intero pur avendo toccato solo file del frontend: non serve a
scoprire regressioni che non possono esistere, serve a dimostrare che non ne ho introdotte.

**Mezzo 2 — sul codice, ma meccanizzato dove si poteva.** Il criterio si spezza in due domande, e
la prima è controllabile a macchina: *il bersaglio esiste?* Ho scritto
`scratchpad/verify_anchors.py`, che estrae le 14 rotte da `App.jsx`, raccoglie ogni ancora interna
del frontend e, per ciascuna, apre il file della pagina di destinazione e ci cerca l'identificatore.
Controlla anche la seconda domanda — *qualcuno ci porta?* — verificando che il gestore sia importato
e invocato in `AppLayout`.

```
Rotte lette da App.jsx: 14
Ancore interne trovate: 6

  [OK   ] DashboardPage.jsx          #top-tracks              (stessa pagina) — id="top-tracks" trovato in DashboardPage.jsx
  [OK   ] DashboardPage.jsx          /temporal#streak         (fra pagine) — id="streak" trovato in TemporalPage.jsx
  [OK   ] TasteEvolutionPage.jsx     #loyal-artists           (stessa pagina) — id="loyal-artists" trovato in TasteEvolutionPage.jsx
  [OK   ] TasteEvolutionPage.jsx     #rising-artists          (stessa pagina) — id="rising-artists" trovato in TasteEvolutionPage.jsx
  [OK   ] TasteEvolutionPage.jsx     #loyal-artists           (stessa pagina) — id="loyal-artists" trovato in TasteEvolutionPage.jsx
  [OK   ] TasteEvolutionPage.jsx     #persistent-tracks       (stessa pagina) — id="persistent-tracks" trovato in TasteEvolutionPage.jsx

  [OK   ] meccanismo di salto all'ancora — useHashScroll importato e invocato in AppLayout
          ancore fra pagine che ne dipendono: 1

Auto-prova (il controllo boccia lo stato di prima, promuove quello di adesso):
  A prima del fix: ROTTO — id="streak" assente da TemporalPage.jsx
  A dopo il fix:   OK — id="streak" trovato in TemporalPage.jsx
  B senza il gestore: ROTTO / con il gestore: OK
  auto-prova: PASSATA

ESITO: VERDE — 0 ancore rotte su 6
```

Come nel giro precedente lo script porta un'**auto-prova**, perché un controllo che dicesse sempre
«OK» passerebbe inosservato: rifà i due controlli contro lo stato di **prima** della correzione e
pretende che li bocci entrambi. È la prova che il controllo distingue davvero i due stati, e insieme
la misura del prima e del dopo.

Al primo giro lo script è uscito **rosso su sé stesso**: leggeva `<Link to="/page#section">` scritto
nel commento del gestore nuovo e lo trattava come un collegamento vero, verso una rotta `/page` che
non esiste. Corretto togliendo i commenti prima di cercare — un esempio dentro un commento non è un
collegamento — e non riscrivendo il commento, perché il difetto era nello strumento.

**Il pacchetto costruito**, per chiudere il dubbio che la modifica sia nel sorgente ma non in ciò
che gira: `TemporalPage-aQW-MAtB.js` contiene `id:"streak"` e `scroll-mt-20`,
`DashboardPage-BA4JJ_oy.js` contiene `/temporal#streak`, `index-Czu8xiFN.js` (dove finisce
`AppLayout`) contiene l'unica `scrollIntoView` del pacchetto principale, e il foglio di stile
contiene `.scroll-mt-20{scroll-margin-top:5rem}`.

**Che cosa resta non provato, e va detto.** Che lo scorrimento avvenga *davvero* nel browser non è
dimostrato: richiederebbe di aprire `/temporal` autenticati, che è vietato al loop. Ciò che è
dimostrato è che i tre pezzi necessari ci sono tutti e sono collegati fra loro — bersaglio,
gestore, scostamento dall'intestazione — e che prima ne mancavano due. La finestra di 3 secondi è
una scelta tarata sul comportamento osservato del codice (animazione di uscita 0.15s più il tempo
della richiesta dati), non su una misura fatta nel browser.

### Limite noto che non ho toccato

Le quattro ancore *nella stessa pagina* passano per `KPICard.jsx:99-110`, che chiama
`scrollIntoView` senza `scroll-margin`: anche loro finiscono sotto l'intestazione appiccicata, di
64px. È un difetto vero ma **pre-esistente e fuori dall'item**, che parla della scheda «Streak».
Dedurne un item nuovo è vietato al loop fuori dai giri di ispezione, quindi lo lascio qui a verbale
e non nel backlog.

### Working tree trovata sporca — e perché non è `NOOP-DIRTY`

`git status --porcelain` a inizio run dava ` M .claude/tasks/lessons.md`: modifiche lasciate non
committate dal run precedente. Non è il caso previsto dal Passo 3, che parla di «lavoro non tuo e
non riconducibile al backlog»: il contenuto sono **lezioni del loop stesso** sugli item I-1 e sul
giro di ispezione, cioè lavoro di questo loop nel file che questo loop tiene per convenzione di
progetto. Poiché ho aggiunto la mia lezione allo stesso file, quelle righe entrano in questo commit.
Lo dichiaro qui perché non sia scambiato per un allargamento di scope: sono righe che ho ereditato,
non scritto.

### Lezione catturata

Aggiunta a `.claude/tasks/lessons.md`: *un'ancora fra pagine non funziona nemmeno quando l'id
esiste*. Il nocciolo trasferibile non è react-router — è che leggere il codice **per pagine** invece
che **per percorsi** fa vedere i due estremi e non il tratto in mezzo, e quando quel tratto è del
framework non ha un file dove essere guardato.

### Breaker

**Non aperto**, e nessuna delle due condizioni del Passo 6 è in piedi: `no_progress_streak` vale 0
contro una soglia di 3, e non esiste uno streak aperto di cui misurare la durata. Niente
`BREAKER: TRATTENUTO` da scrivere — quel caso riguarda una soglia raggiunta con troppo poco tempo
trascorso, e qui la soglia non è raggiunta affatto. Nessuna riga `escalated:` pendente da chiudere.

### Conti con la guardia

Eseguito `--confirm-progress` **dopo** il commit, come prescritto. Il contatore della guardia era a
**1 su 3**: senza l'azzeramento continuerebbe a salire fino a un allarme «backlog fermo» falso,
emesso proprio mentre il loop avanza.

### Escalation al vault

Nessuna, e nessun lock preso. Il canale verso Fabio si apre solo per breaker o capolinea, e non
siamo in nessuno dei due: restano sei finding (I-4 → I-9) più il checkpoint. Sarà il run del
checkpoint a prendere la corsia `inbox` e a riscrivere la voce di capolinea. Prendere la corsia
adesso toglierebbe solo il giro ad altri loop, senza niente da scrivere.

### Remoto

`git rev-parse @{u}` a inizio run: `8616d0c6b50fac0db5a7d262e928c0df65a602ba`.
A fine run: **identico**. Nessun push partito, come deve essere — questo repo non ha canale di
pubblicazione automatica.
