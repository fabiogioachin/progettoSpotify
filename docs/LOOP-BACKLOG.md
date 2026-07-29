# LOOP BACKLOG — progettoWrap

> **Programma avviato il 2026-07-29: cinque giri, poi checkpoint.** Il quinto item runnable è seguito da un
> item-checkpoint che rimette `LOOP HALTED` in testa a questo file e ferma tutto. A quel punto
> si rivede il lavoro e, se convince, si riapre la coda togliendo il marcatore.
> Il marcatore qui sopra lo togli tu quando vuoi far partire il programma.
>
> Lista costruita il 2026-07-29 da un censimento del repo (ambienti, CI, componenti, piani in
> `docs/` e `.claude/tasks/todo.md`). Ogni affermazione qui sotto è stata verificata sul codice
> quel giorno, con il riferimento accanto.

## Come si legge

Il loop prende **il primo item non completato** e fa solo quello. Un run, un item.

- `[ ]` da fare · `[x]` fatto · `[FAILED]` tentato e fallito, con l'errore accanto
- `[BLOCKED_USER]` richiede una decisione o un'azione tua: il loop lo salta senza toccarlo

Ogni item deve dire **come si verifica che è fatto**. Un item senza criterio di verifica il loop
non lo sa chiudere, e resterà lì a bloccare la coda.

---

## Item

### 1. `[x]` Ricostruire gli ambienti di sviluppo (prerequisito di tutto il resto)

> **Fatto il 2026-07-29.** Venv backend su Python 3.12.13 e `npm ci` sul frontend.
> `pytest --collect-only` raccoglie 534 test con zero errori di import (erano 185 con 19 errori),
> `npm run lint` e `npm run build` escono entrambi con 0, `git status` è vuoto. Nessuna
> configurazione pytest aggiunta: la condizione posta dal punto 4 non si è verificata, la suite
> gira senza. Dettaglio in `docs/loop-last-run.md`.

Oggi nel repo non esiste né `backend/.venv` né `frontend/node_modules`. Senza, **nessun item è
verificabile**: 19 file di test su 30 non collezionano nemmeno (`ModuleNotFoundError: asyncpg`,
`redis`), e `npm run lint`/`npm run build` non partono.

Cosa fare:

1. Creare il venv backend con **Python 3.12**, lo stesso della CI — non il 3.14 di sistema, su cui
   le dipendenze pinnate (`numpy<2.0`, `librosa`) non hanno ruote. Interprete esplicito:
   ```
   "C:\Users\fgioa\AppData\Roaming\uv\python\cpython-3.12.13-windows-x86_64-none\python.exe" -m venv C:\Users\fgioa\Desktop\PRO\progettoWrap\backend\.venv
   ```
2. `backend\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt` (include i runtime).
3. `npm install` dentro `frontend\` (c'è già `package-lock.json`: usa `npm ci`).
4. Se `pytest` al primo giro fallisce per configurazione asyncio mancante (nel repo non c'è
   `pytest.ini` né `asyncio_mode` dichiarato): aggiungere la configurazione minima che fa girare
   la suite, versionata, e dichiararlo nel run-log.

**Verifica**:

- `backend\.venv\Scripts\python.exe -m pytest --collect-only -q` colleziona **senza errori di
  import** (riferimento di oggi: 185 test e 19 errori con l'interprete globale).
- `cd frontend && npm run lint` e `npm run build` **partono** (l'esito può essere rosso: pulirlo
  è un item successivo; qui conta che i comandi siano eseguibili).
- Nessun file di ambiente committato: `.venv/` e `node_modules/` sono già nel `.gitignore`.

### 2. `[ ]` `build.yml` punta a Dockerfile che non esistono

`.github/workflows/build.yml` righe 13 e 16 fanno `docker build ./backend` e `docker build
./frontend`, ma non esistono `backend/Dockerfile` né `frontend/Dockerfile`: i Dockerfile veri sono
`docker/backend.Dockerfile` e `docker/frontend.Dockerfile`. **Il workflow fallisce a ogni push su
master**, e nessun documento di piano ne parla.

Cosa fare: correggere i due step con `-f docker/backend.Dockerfile` (e frontend analogo) e il
context giusto, coerenti con come i compose file li usano.

**Verifica**: ogni path citato in `build.yml` esiste nel repo; lo YAML si carica senza errori
(`python -c "import yaml; yaml.safe_load(open('.github/workflows/build.yml'))"` con il venv
dell'item 1, o strumento equivalente). La prova CI vera arriverà solo al prossimo push
dell'utente: dichiaralo nel run-log come limite.

### 3. `[ ]` Componente morto: `EmptyState.jsx`

`frontend/src/components/ui/EmptyState.jsx` è definito ed esportato ma ha **zero import** in tutto
`frontend/src` — unico componente non referenziato su 48. Intanto `docs/LAUNCH-PLAN.md:15` marca
`[x] Empty states + error boundaries`: il piano dichiara fatto ciò che in parte è solo scritto.

Cosa fare: riverificare che gli import siano ancora zero; se sì, eliminare il file e annotare in
`LAUNCH-PLAN.md` che gli empty state sono implementati per-pagina, non col componente condiviso.
Se invece nel frattempo qualcuno lo importa, non toccarlo: marca `[BLOCKED_USER]` e spiega.

**Verifica**: ricerca di `EmptyState` su `frontend/src` senza risultati; `npm run build` verde.

### 4. `[ ]` La CI non esegue i test backend

`.github/workflows/ci.yml` ha solo lint (backend ruff, frontend eslint+build). I 30 file di test
backend non girano mai automaticamente. Dipende dall'item 1: prima di mettere la suite in CI, va
fatta girare in locale.

Cosa fare: eseguire la suite in locale col venv dell'item 1 (se i test vogliono Postgres/Redis,
avviare solo quei due servizi con `docker-compose -f docker/docker-compose.yml up postgres redis -d`
— è infrastruttura locale, non deploy). Poi aggiungere a `ci.yml` un job `backend-test` su Python
3.12 che rispecchia ciò che ha funzionato in locale, servizi inclusi.

> **Misurato il 2026-07-29** (dal giro dell'item 1, non corretto lì): `pytest -q` dà **526 passati
> e 8 falliti**. Quattro in `test_privacy.py` sono inquinamento tra test — passano da soli e
> falliscono solo dopo un altro `TestClient(app)`, per via dello scheduler globale in
> `app/main.py:87`. Quattro in `test_temporal_patterns.py` falliscono anche in isolamento. Causa e
> riferimenti precisi in `docs/loop-last-run.md`.

**Verifica**: suite verde in locale, con comando, conteggio e interprete dichiarati nel run-log;
job presente in `ci.yml` e YAML valido. Come per l'item 2, la prova CI vera arriva al prossimo
push dell'utente. Se la suite locale resta rossa dopo 3 tentativi: `[FAILED]` con l'errore vero.

### 5. `[ ]` ISPEZIONE FRONTEND — primo giro da utente

Item speciale: segue la «Fase di ispezione frontend» descritta nel protocollo del loop. In breve:
questo giro **non modifica codice**. Si guarda l'app con gli occhi di un utente, si scrivono le
incongruenze trovate come item nuovi nella sezione «Trovati dall'ispezione» qui sotto, ciascuno
con il suo criterio di verifica. I giri successivi li implementeranno uno alla volta.

Piste già note dal censimento, da confermare o smontare guardando:

- `Sidebar.jsx` espone 10 voci ma le route sono 14: `/privacy` e `/admin` non stanno nel menu —
  raggiungibili da qualche parte o pagine fantasma?
- Colori hex cablati fuori dalla palette centralizzata: `StreakDisplay.jsx:102`, `GenreDNA.jsx:29`.
- `.claude/tasks/todo.md` chiede il donut al posto del treemap generi (B1): il Dashboard importa
  ancora `GenreTreemap`.
- Cosa vede davvero un utente non autenticato: la LoginPage è l'unica route pubblica — è
  presentabile? Gestisce l'errore se il backend è giù?

**Limite dichiarato**: senza `.env` il backend non parte, e senza login Spotify reale (vietato)
le pagine protette non si vedono dal browser. Ciò che non è ispezionabile dal vivo si ispeziona
sul codice (route per route: stati vuoti, loading, errori) e si dichiara nel run-log la modalità
usata per ciascuna pagina.

**Verifica**: la sezione «Trovati dall'ispezione» esiste e ogni finding ha un criterio di
verifica; nessun file di codice modificato in questo giro; run-log con l'elenco delle pagine
ispezionate e come.

### ✋ `[ ]` CHECKPOINT — quinto giro completato: fermati qui

Se stai leggendo questo item come «primo item non completato», i cinque item sopra sono chiusi.
Questo giro non implementa niente. Fai solo questo:

1. Scrivi la riga `LOOP HALTED` in testa a questo file, subito sotto il titolo.
2. Marca questo item `[x]`.
3. Scrivi nel run-log l'esito `CHECKPOINT` con un riepilogo: item chiusi, `FAILED`,
   `BLOCKED_USER` nuovi, quanti finding ha prodotto l'ispezione.
4. Committa i file toccati e termina.

**Verifica**: `LOOP HALTED` presente in testa al file; run-log aggiornato; commit creato.

---

## Trovati dall'ispezione

*(vuota finché il primo giro di ispezione non scrive qui. Solo i giri di ISPEZIONE FRONTEND
possono aggiungere item in questa sezione, e solo di tipo frontend/UI.)*

---

## Dopo il checkpoint (si sbloccano togliendo il marcatore)

### 7. `[ ]` Lint frontend pulito

`npm run lint` deve uscire senza errori, comprese le 6 soppressioni `eslint-disable` su
`react-hooks/exhaustive-deps` da rivedere una per una (`ArtistNetwork.jsx:319`,
`ThrottleBanner.jsx:80` — che usa l'espressione booleana `[windowReset > 0]` come dipendenza —,
`useAudioAnalysis.js:108,122`, `useWrappedTask.js:122`): o la soppressione ha una motivazione
scritta accanto, o si corregge la dipendenza.

**Verifica**: `cd frontend && npm run lint` → exit 0; ogni `eslint-disable` residuo ha il perché
nel commento.

### 8. `[ ]` Allineare LAUNCH-PLAN a ciò che esiste davvero

Lo Step 2 del piano di lancio descrive come da fare cose già nel repo (`docker-compose.prod.yml`,
`docker/caddy/`, i due workflow). Confrontare voce per voce, spuntare l'esistente, lasciare aperto
solo ciò che manca.

**Verifica**: nessuna voce dello Step 2 descrive come da creare un file che esiste nel repo.

### 9. `[ ]` Script di backup del database, versionato

Il piano descrive un `pg_dump` con rotazione 7 giornalieri + 4 settimanali come crontab da
incollare a mano. Va messo nel repo (`docker/backup/`), rotazione inclusa, con istruzioni.

**Verifica**: lo script gira in locale contro il Postgres di sviluppo e produce un `.sql.gz`
leggibile; la rotazione è provata (test o prova documentata nel run-log).

### 10. `[ ]` Archiviare o rigenerare `HEALTH-REPORT.md`

`.claude/tasks/HEALTH-REPORT.md` è del 2026-04-01 e 15 dei suoi 21 finding risultano già chiusi
(verifica a campione del 2026-07-29). Un report vecchio preso per buono fa sprecare giri interi.

**Verifica**: nuovo report datato con il delta (chiusi / confermati / nuovi), oppure il vecchio
spostato in un archivio con una riga che dice perché.

### 11. `[BLOCKED_USER]` Creare `.env` dalla `.env.example`

Serve per avviare il backend in locale (`docker-compose.yml` lo richiede) e quindi per
l'ispezione frontend dal vivo oltre la LoginPage. Contiene secret Spotify: **azione tua**, il
loop non tocca quel file per divieto.

### 12. `[BLOCKED_USER]` Workflow di deploy sul VPS

Serve un server, un dominio e una chiave SSH — decisioni e acquisti tuoi. Finché non esistono,
scrivere `deploy.yml` significa scrivere qualcosa che non si può provare.

### 13. `[BLOCKED_USER]` Extended Quota Spotify

Richiede screenshot dell'app in produzione e privacy policy su dominio pubblico. Dipende
dall'item 12. Per la beta fino a 5 amici non serve.

---

## Cose che il loop non deve fare

- Toccare `.env`, secret, o la configurazione dell'app Spotify Developer
- Aprire connessioni verso Spotify con credenziali reali per «provare»
- Fare `git push` (nessuno)
- Fare deploy o toccare infrastruttura di produzione (i container locali postgres/redis sono ok)
- Dedurre item nuovi da solo, **con una sola eccezione**: i giri di ISPEZIONE FRONTEND scrivono
  i loro finding nella sezione «Trovati dall'ispezione», solo lì e solo di tipo frontend/UI
