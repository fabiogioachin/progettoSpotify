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
