# LOOP BACKLOG — progettoWrap

> **Secondo programma, aperto il 2026-07-30 su richiesta di Fabio: i 9 finding dell'ispezione
> frontend.** Il marcatore `LOOP HALTED` è stato tolto da qui. Il loop riparte da **I-1** e ne fa uno
> per giro, nell'ordine in cui stanno nella sezione «Trovati dall'ispezione»; dopo I-9 incontra un
> item-checkpoint che rimette `LOOP HALTED` in testa a questo file e ferma di nuovo tutto.
>
> I quattro item della sezione «Dopo il checkpoint» (7, 8, 9, 10) **non fanno parte di questo
> programma**: il checkpoint li precede, quindi il loop non li raggiunge. Restano scritti lì per il
> giro successivo.
>
> **Stato dei finding alla riapertura**: scritti dall'ispezione dello stesso 2026-07-30 e
> ricontrollati a campione prima di riaprire — I-2, I-3, I-8 e I-9 sono ancora veri sul codice di
> oggi, e nessun commit ha toccato `frontend/` dopo l'ispezione (l'ultimo è `c37c0f6`). Gli altri
> cinque non sono stati ricontrollati: valgono per come li ha scritti l'ispezione.

> **Primo programma, 2026-07-29 → 2026-07-30: chiuso.** Cinque item più un checkpoint, tutti `[x]`,
> zero `FAILED`. Lista costruita il 2026-07-29 da un censimento del repo (ambienti, CI, componenti,
> piani in `docs/` e `.claude/tasks/todo.md`), ogni affermazione verificata sul codice quel giorno.
> Resta qui sotto come storia, non come lavoro da fare. Riepilogo in `docs/loop-last-run.md`.

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

### 2. `[x]` `build.yml` punta a Dockerfile che non esistono

> **Fatto il 2026-07-29.** Aggiunto `-f docker/backend.Dockerfile` e `-f docker/frontend.Dockerfile`
> ai due step, lasciando i context `./backend` e `./frontend` come li usano i due compose file.
> Verificato che ogni path citato dal workflow esiste e che ogni sorgente `COPY` dei Dockerfile
> risolve dentro il context dichiarato senza essere esclusa dal `.dockerignore` di quel context.
> Il demone Docker locale non gira, quindi la build vera non è stata eseguita: la prova arriva al
> prossimo push. Dettaglio in `docs/loop-last-run.md`.

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

### 3. `[x]` Componente morto: `EmptyState.jsx`

> **Fatto il 2026-07-30.** Import riverificati: zero, il file citava solo se stesso. Rimosso.
> `EmptyState` non compare più in `frontend/src`, `npm run lint` e `npm run build` escono 0.
> **Correzione al testo dell'item**: l'annotazione chiesta («empty state implementati per-pagina»)
> sarebbe stata falsa — in tutto il frontend esiste **un solo** messaggio testuale di «nessun dato»
> (`AdminPage.jsx:442`). La convenzione vera è l'opposto: la sezione senza dati **si nasconde**, il
> chart restituisce `null` e il genitore decide. In `LAUNCH-PLAN.md` è stata scritta quella, con i
> riferimenti al codice. Dettaglio in `docs/loop-last-run.md`.

`frontend/src/components/ui/EmptyState.jsx` è definito ed esportato ma ha **zero import** in tutto
`frontend/src` — unico componente non referenziato su 48. Intanto `docs/LAUNCH-PLAN.md:15` marca
`[x] Empty states + error boundaries`: il piano dichiara fatto ciò che in parte è solo scritto.

Cosa fare: riverificare che gli import siano ancora zero; se sì, eliminare il file e annotare in
`LAUNCH-PLAN.md` che gli empty state sono implementati per-pagina, non col componente condiviso.
Se invece nel frattempo qualcuno lo importa, non toccarlo: marca `[BLOCKED_USER]` e spiega.

**Verifica**: ricerca di `EmptyState` su `frontend/src` senza risultati; `npm run build` verde.

### 4. `[x]` La CI non esegue i test backend

> **Fatto il 2026-07-30.** Suite verde in locale: **536 passati, 0 falliti, exit 0** con
> `backend\.venv\Scripts\python.exe -m pytest -q` (Python 3.12.13). Job `backend-test` aggiunto a
> `ci.yml`, **senza servizi**: la suite è stata rieseguita con `DATABASE_URL` e `REDIS_URL` puntati
> a porte chiuse e ha dato di nuovo 536 passati, quindi Postgres e Redis non servono in CI.
> Gli 8 rossi erano due guasti distinti, nessuno dei due nel codice di produzione dei test:
> lo scheduler globale (corretto in `app/main.py`) e quattro test con date di calendario cablate a
> marzo 2026, ormai fuori dalla finestra di 30 giorni del servizio. Dettaglio in
> `docs/loop-last-run.md`. **Limite**: `backend-lint` era già rosso prima di questo giro (2 errori
> ruff pre-esistenti), quindi la CI nel complesso resta rossa finché non si sistemano — vedi
> run-log.

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

### 5. `[x]` ISPEZIONE FRONTEND — primo giro da utente

> **Fatto il 2026-07-30.** Nessun file di codice modificato. Ispezionate 14 route: la LoginPage dal
> vivo col server di sviluppo, le altre sul codice (senza `.env` il backend non parte). Prodotti
> **9 finding** nella sezione «Trovati dall'ispezione».
> **Due delle quattro piste del censimento erano sbagliate e sono state smontate**: `/privacy` e
> `/admin` sono nel menu (piè di pagina della barra laterale, `Sidebar.jsx:118-145`, l'admin solo
> se `user.is_admin`), e `GenreTreemap` **disegna già una ciambella** — B1 di `todo.md` chiede una
> cosa che il codice fa già, resta solo il nome sbagliato. Le altre due sono confermate e allargate:
> i colori cablati non sono 2 ma **120 su 24 file**. Dettaglio in `docs/loop-last-run.md`.

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

### ✋ `[x]` CHECKPOINT — quinto giro completato: fermati qui

> **Eseguito il 2026-07-30T10:35:00Z.** `LOOP HALTED` scritto in testa al file, nessun file di
> codice toccato. I cinque item del programma sono chiusi, **zero `FAILED`**, e nessun
> `BLOCKED_USER` nuovo oltre ai tre già in lista (11, 12, 13). L'ispezione del quinto giro ha
> prodotto **9 finding**, tutti ancora aperti. Voce di capolinea scritta nel canale Inbox del
> vault. Riepilogo completo in `docs/loop-last-run.md`.

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

*Scritti dal giro di ispezione del 2026-07-30. Ordinati per quanto pesano sull'utente, non per
quanto costa correggerli. Ognuno dice cosa si vede di sbagliato, dove, e come si verifica che è
chiuso.* **Da qui prende il lavoro il secondo programma: un item per giro, dall'alto.**

**Con che cosa si verifica, in questo repo.** Va detto prima di cominciare, perché diversi criteri
qui sotto sono scritti come comportamenti osservabili e **il frontend non ha un test runner**:
`frontend/package.json` espone solo `dev`, `build`, `preview`, `lint`. Non esiste `npm test`, e
nessuno di questi item lo introduce. Quindi «verificato» qui significa una di tre cose, e il
run-log deve dire **quale**, per ciascun item:

1. **Dal vivo**, per ciò che si raggiunge senza backend e senza login — cioè la schermata di accesso
   e gli errori che si producono spegnendo il backend. È il caso di **I-1**, ed è il modo migliore:
   usalo dove è possibile.
2. **Sul codice**, per tutto ciò che sta dietro l'autenticazione: **I-4** (pagina privacy), **I-5**,
   e in parte I-2, I-3, I-8. Si mostra il punto corretto e si spiega perché chiude il difetto.
   **Non** si scrive «verificato dal vivo» per una pagina che non si è potuta aprire.
3. **Meccanicamente**: `cd frontend && npm run lint` e `npm run build`, entrambi a exit 0. Servono
   **sempre**, e da soli non bastano per nessuno di questi item.

Nessun test finto e nessuna verifica dichiarata ma non eseguita. Se un criterio non è raggiungibile
con questi tre mezzi, l'onestà è dichiarare il limite nel run-log e chiudere l'item spiegando fin
dove si è arrivati — non inventare una prova.

**Se un finding risulta sbagliato**, come è già successo a due piste su quattro nel giro di
ispezione: non forzarlo. Correggi il testo dell'item, spiega nel run-log cosa era sbagliato, e
chiudilo per quello che è. Un item che descrive un difetto inesistente si chiude smontandolo.

### I-1. `[ ]` Col backend spento il bottone di login porta a una pagina bianca

L'unico percorso che un utente non autenticato può percorrere, ed è senza uscita. **Verificato dal
vivo**, non dedotto: con il server di sviluppo attivo e il backend spento, `/auth/spotify/login`
risponde 500 e il browser resta su una **pagina completamente vuota**. Da lì non si torna indietro
se non col tasto del browser: la pagina ha lasciato l'applicazione, quindi non c'è più nessuna
interfaccia.

Il guasto comincia prima. All'apertura della pagina la verifica della sessione fallisce, ma
l'errore **muore in console** (`AuthContext.jsx:31-34`: `console.error` e basta) e la schermata di
accesso si disegna identica al caso normale. L'utente non ha modo di sapere che il servizio è giù:
vede una pagina sana, preme il bottone, e finisce nel vuoto. Il bottone intanto è rimasto su
«Connessione in corso…» (`LoginPage.jsx:86`), che è l'ultima cosa che vede prima del bianco.

**Verifica**: col backend spento, premere «Connetti Spotify» lascia l'utente sulla schermata di
accesso con un messaggio leggibile che dice che il servizio non risponde; nessuna pagina bianca.

### I-2. `[ ]` Dashboard: la scheda «Artisti unici» non porta da nessuna parte

`DashboardPage.jsx:174` punta a `/artist-network`, ma quella rotta **non esiste**: la pagina degli
artisti sta su `/artists` (`App.jsx:91`, ed è così anche nel menu, `Sidebar.jsx:37`). L'unica altra
occorrenza di quel nome nel frontend è l'indirizzo dell'API, che è un'altra cosa.

Cosa vede l'utente: la scheda si illumina al passaggio del mouse e ha il cursore a manina, quindi
promette un salto; al clic la regola di raccolta (`App.jsx:146`) rimanda alla radice, che per un
utente autenticato rimanda alla dashboard. **Il clic ricarica la pagina su cui sei già.**

**Verifica**: cliccare «Artisti unici» apre «Ecosistema Artisti».

### I-3. `[ ]` Dashboard: la scheda «Streak» promette un dettaglio che non c'è

`DashboardPage.jsx:148` punta a `/temporal#streak`, e il suggerimento dice «Vai ai Pattern
Temporali per i dettagli». La pagina è quella giusta, ma **l'ancora non esiste**: in
`TemporalPage.jsx` non c'è nessun elemento con quell'identificatore, e la sezione dello streak
(riga 149) non ne ha uno. L'utente atterra in cima alla pagina e deve cercarsi da solo il pezzo che
gli era stato promesso.

Sulla stessa pagina, le due schede che puntano a un'ancora interna funzionano
(`#top-tracks`, `DashboardPage.jsx:135`), quindi la differenza si nota.

**Verifica**: cliccare «Streak di ascolto» porta l'utente davanti alla sezione dello streak, non in
cima alla pagina.

### I-4. `[ ]` Privacy: esportazione e cancellazione dell'account falliscono in silenzio

Il posto peggiore dove tacere. In `PrivacyPage.jsx` entrambe le azioni ingoiano l'errore senza
dire niente:

- **Esportazione** (riga 25): il blocco di cattura è vuoto, con un commento che si affida
  all'intercettore delle chiamate. Ma quell'intercettore (`api.js:56-58`) gestisce **solo** la
  sessione scaduta e il troppo-traffico: su un 500 o sulla rete caduta non fa nulla. Il bottone
  torna da «Esportazione in corso…» a «Esporta i miei dati», **non si scarica niente**, e non
  compare nessun messaggio. L'utente non sa se riprovare.
- **Cancellazione** (righe 37-40): in caso di errore la finestra di conferma **si chiude come se
  l'operazione fosse andata a buon fine**. L'utente ha appena chiesto di cancellare il proprio
  account per sempre e resta senza risposta: non sa se è stato cancellato o no.

**Verifica**: con le due chiamate che rispondono errore, entrambe le azioni mostrano un messaggio
visibile; la finestra di conferma della cancellazione **non** si chiude su errore.

### I-5. `[ ]` Evoluzione Gusto: tre messaggi di «nessun dato» scritti e mai mostrati

`TasteEvolutionPage.jsx` passa alle tre colonne un testo per il caso vuoto — «Nessun nuovo
artista», «Nessun artista fedele», «Nessun artista in calo» (righe 75, 78, 81) — ma il componente
che le disegna **non riceve quel parametro**: la sua firma (riga 244) non lo elenca, e alla riga
285 il caso vuoto rende `null`.

Risultato: chi non ha dati vede tre riquadri con un titolo, un contatore a zero e sotto il vuoto.
Non è nemmeno la convenzione del progetto, che dice di **nascondere** la sezione senza dati: qui la
sezione resta, svuotata. Va deciso quale delle due cose si vuole, perché oggi non è né l'una né
l'altra.

**Verifica**: o il testo compare, o il parametro sparisce e la colonna vuota viene nascosta. In
nessun caso restano riquadri vuoti con un parametro inutilizzato.

### I-6. `[ ]` La palette è centralizzata solo a metà: 120 colori cablati in 24 file

Esiste `lib/chartTheme.js` che dichiara i colori, ma **lo importano 7 dei 13 grafici**. Nel resto
del frontend ci sono **120 colori scritti a mano su 24 file**, e fra questi l'indaco `#6366f1` che
`.claude/CLAUDE.md` indica come colore d'accento del prodotto — ripetuto una decina di volte
(`StreakDisplay.jsx:102`, `GenreDNA.jsx:32-33`, `ArtistNetworkPage.jsx:175,210`,
`DiscoveryPage.jsx:315`, `PlaylistComparePage.jsx:265,416`, `PlaylistAnalyticsPage.jsx:137,208`,
fra gli altri).

L'effetto non è estetico ma pratico: **cambiare il colore d'accento oggi vuol dire aprire 24 file**,
e chi ne dimentica uno lascia una pagina scoordinata rispetto alle altre. Lo stesso vale per il
grigio della griglia e per quello delle etichette, ripetuti ovunque.

**Verifica**: i colori dei grafici arrivano da `chartTheme.js` o dalle variabili CSS; cambiato
l'accento in un solo punto, cambia in tutta l'applicazione.

### I-7. `[ ]` `GenreTreemap` disegna una ciambella: il nome mente e `todo.md` risulta aperto a torto

Il punto B1 di `.claude/tasks/todo.md:17` chiede «donut chart al posto del treemap» ed è segnato da
fare. **Il lavoro è già stato fatto**: `GenreTreemap.jsx:54-70` disegna un `PieChart` con un raggio
interno del 45%, cioè esattamente una ciambella. Del treemap è rimasto solo il nome del file e del
componente.

Non è pignoleria sul nome: è un item di lavoro aperto che promette una modifica già presente, e il
prossimo che lo prende rifà una cosa fatta. Costa la stessa lettura scoprirlo dopo o adesso.

**Verifica**: il componente ha un nome che descrive ciò che disegna, tutti i punti che lo importano
sono aggiornati, e B1 in `todo.md` è chiuso o annotato come già fatto.

### I-8. `[ ]` Nessuna pagina «non trovato»: ogni indirizzo sbagliato scarica sulla dashboard

`App.jsx:146` manda alla radice tutto ciò che non riconosce, e la radice manda alla dashboard chi è
autenticato. Un refuso nell'indirizzo, o un vecchio segnalibro, non producono nessun messaggio:
l'utente si ritrova sulla dashboard senza sapere perché, e crede che il collegamento che aveva
funzioni ancora. È anche ciò che rende invisibile il difetto I-2.

**Verifica**: un indirizzo inesistente mostra una pagina che dice che non esiste, con un
collegamento per tornare alla dashboard.

### I-9. `[ ]` L'indicatore di budget API mostra «0/25» prima di aver misurato qualcosa

`Header.jsx:8` parte da `{ current: 0, max: 25 }` e si aggiorna solo quando arriva la prima
risposta con l'intestazione del contatore. Fino ad allora, in cima a ogni pagina, si legge «0/25»
in verde: un numero che sembra una misura e non lo è, per giunta col 25 che è proprio il limite
vero della finestra Spotify, quindi del tutto credibile.

È il caso che l'invariante 5 di `.claude/CLAUDE.md` vieta per nome — niente valori finti
plausibili, i dati mancanti si dichiarano mancanti.

**Verifica**: finché non è arrivata una misura vera, l'indicatore è nascosto o dichiara di non
avere ancora dati; non mostra uno zero che sembra misurato.

### ✋ `[ ]` CHECKPOINT — i 9 finding sono chiusi: fermati qui

Se stai leggendo questo item come «primo item non completato», i nove finding sopra sono chiusi o
dichiarati `[FAILED]`. **Questo giro non implementa niente.** Fai solo questo:

1. Scrivi la riga `LOOP HALTED` in testa a questo file, subito sotto il titolo.
2. Marca questo item `[x]`.
3. Scrivi nel run-log l'esito `CHECKPOINT` con il riepilogo del programma: quali finding chiusi,
   quali `[FAILED]` e con che errore, quali si sono rivelati sbagliati e sono stati smontati, e per
   ciascuno **con quale dei tre mezzi** è stato verificato.
4. Manda la voce di capolinea nel canale Inbox del vault, come prescrive il Passo 7 del protocollo:
   è una transizione nuova, quindi la voce va riscritta anche se ne esiste già una del programma
   precedente.
5. Committa i file toccati e termina.

**Verifica**: `LOOP HALTED` presente in testa al file; run-log aggiornato; commit creato.

---

## Dopo il checkpoint (non fanno parte del secondo programma)

*Il checkpoint qui sopra li precede, quindi il loop non li raggiunge. Per farli lavorare servirà un
terzo programma: spostarli sopra il checkpoint, o dare loro un checkpoint proprio.*

> **Da correggere prima di prenderlo**: l'item 7 dà `npm run lint` per rosso, ma è **verde** da
> tutti e cinque i giri del primo programma. Di quell'item resta viva solo la parte sulle 6
> soppressioni `eslint-disable` da motivare.

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
