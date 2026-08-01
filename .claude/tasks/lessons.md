# Lessons Learned

## Active
Lessons that affect future tasks. Target: under 15 entries.

### 2026-03-26 — [codebase] Docker backend.Dockerfile must include scripts/
**Context**: `python -m scripts.backfill_artist_genres` inside container failed with `ModuleNotFoundError`
**What happened**: `docker/backend.Dockerfile` only copied `app/` and `alembic/`, not `scripts/`
**Root cause**: When `scripts/` directory was created, the Dockerfile wasn't updated to include it
**Action**: When adding new top-level directories to backend/ that need to run inside Docker, always update `docker/backend.Dockerfile` COPY statements

### 2026-03-26 — [codebase] Backfill scripts must respect API budget with delays
**Context**: `backfill_artist_genres` with P2_BATCH priority exhausted budget after 3 artists (3 call/window)
**What happened**: Script used `gather_in_chunks` with no delay between chunks — all 50 artists attempted in <1s, 47 rate-limited
**Root cause**: P2_BATCH allows only 3 calls/30s. Script assumed `gather_in_chunks` would handle throttling, but budget exhaustion happens before the throttle layer
**Action**: Backfill scripts must: (1) use P1_LOGIN priority minimum, (2) add explicit `asyncio.sleep(6)` between calls, (3) on rate limit, pause 35s then retry once

### 2026-03-21 — [tool] Local PostgreSQL intercepts Docker-mapped ports
**Context**: Docker Compose mapped postgres to host port 5432, then 5433 — both intercepted by local PG installation.
**What happened**: `asyncpg.connect()` hit the local PostgreSQL (which doesn't have the `spotify` user), not the Docker container.
**Root cause**: Local PostgreSQL listens on 5432 AND 5433. Docker port mapping creates a second listener on the same port, but the OS routes to the local PG first.
**Action**: Use port 5434 for Docker PostgreSQL on this machine. If port conflicts arise, always check `netstat -ano` before assuming Docker owns the port.

### 2026-03-19 — [codebase] Never add background API calls without budget verification
**Context**: Added `fire_bg_enrich` — a background task that called `GET /tracks/{id}` ×15 after a 35s delay to populate popularity cache.
**What happened**: The 35s delay wasn't enough. User navigation filled the budget again. The background task triggered a 429 with `retry_after=40445s` (11 hours of cooldown).
**Root cause**: Added API calls without counting the real budget impact. A rolling 30s window means a fixed delay doesn't guarantee availability — any user action during the delay refills the window.
**Action**: Never add ANY Spotify API call (even background/deferred) without explicit budget accounting in the `spotify-api-budget` skill. If an endpoint's data isn't available in dev mode, accept it and hide the feature — don't try to work around it with extra API calls.

### 2026-03-18 — [codebase] NaN from numpy/sklearn crashes JSON serialization
**Context**: `GET /api/profile` returned 500 — `ValueError: Out of range float values are not JSON compliant: nan`
**What happened**: PCA, StandardScaler, NetworkX PageRank/betweenness, and cosine similarity can produce NaN/inf when input data has zero variance or edge cases. Python's `json.dumps` rejects non-finite floats.
**Root cause**: No defense-in-depth — individual fixes (e.g. nan_to_num in PCA) missed other NaN sources in the same response pipeline.
**Action**: Always wrap router returns with `sanitize_nans()` from `app.utils.json_utils` when the response includes float data from numpy/sklearn/NetworkX. Applied to profile, analytics, artist_network, wrapped.

### 2026-03-14 — [codebase] Spotify dev mode keeps removing endpoints
**Context**: `/artists/{id}/related-artists` started returning 403
**What happened**: Fourth+ deprecated endpoint. artist_network.py and discovery.py wasted calls on always-failing requests.
**Root cause**: Spotify dev mode progressively removes endpoints without advance warning.
**Action**: When any endpoint returns 403, treat as permanently removed — delete entirely, never wrap in try/except.

### 2026-03-14 — [codebase] Don't re-fetch data the frontend already has
**Context**: `POST /api/analyze-tracks` received only track_ids, re-fetched 50 tracks → instant 429.
**Action**: Pass full objects in request body when the frontend already has them.

### 2026-03-10 — [workflow] Task marked complete without live verification
**Context**: Bug fix marked `[x]` after code change, without verifying data flows end-to-end.
**Action**: Bug fix cycle: code → lint/test → live verification with real data → only then mark complete.

### 2026-03-06 — [codebase] dict.get() failures are silent in Python
**Context**: prompt_builder accessed wrong keys → silent empty output.
**Action**: Always verify key names between service return values and consumer code.

### 2026-03-14 — [workflow] git status -u non eseguito durante verifica
**Context**: `pip install networkx>=3.2` senza quoting ha creato file `backend/=3.2` e `backend/=1.4` (shell redirect). Non intercettati fino al commit finale.
**Root cause**: Il workflow di verifica (lint/test/build) non include `git status -u` per individuare file spazzatura.
**Action**: Dopo ogni wave di agenti, eseguire `git status -u` per individuare file non tracked inattesi. Verificare che i comandi pip usino quoting (`"pkg>=version"`).

### 2026-03-21 / 2026-04-02 — [codebase] Login sync: cache poisoning + priority + retry
**Context**: Login/startup sync ran but stored 0 items. DB stuck at March 28, Spotify API had April 1 data.
**What happened**: Three stacked bugs: (1) `get_recently_played(limit=50)` cached in Redis 120s — page load cached stale data, sync got cached result. (2) P1_BACKGROUND_SYNC budget (1 call/user) exhausted by page loads. (3) ThrottleError swallowed with `break`, no retry.
**Root cause**: Sync shared the same cached `get_recently_played` as the interactive endpoints. The sync MUST see fresh data to detect new plays.
**Action**: (1) `skip_cache=True` on `get_recently_played` in sync — fresh API data always. (2) P0_INTERACTIVE priority. (3) `raise_on_throttle=True` + retry loop (3 attempts). (4) Same fix in both startup sync (main.py) and login sync (auth.py).

### 2026-04-03 — [codebase] Spotify dev mode returns empty genres AND popularity for ALL artists
**Context**: Ecosistema Artisti showed 0 connections, 82 artists without genres
**What happened**: `/me/top/artists` AND `/artists/{id}` both return `popularity: 0, genres: []` for every artist in dev mode. Not just underground — Sfera Ebbasta, Drake, Ludovico Einaudi all empty.
**Root cause**: Spotify dev mode strips these fields entirely. This is NOT a per-artist issue — it's a blanket dev mode limitation.
**Action**: (1) Never rely on Spotify for genres/popularity in dev mode. (2) Use MusicBrainz as primary genre source (1 req/s, search + MBID lookup). (3) Use playlist-inferred genres as tertiary fallback. (4) Remove popularity-based fallback logic (all zeros = garbage edges).

### 2026-04-03 — [codebase] MusicBrainz first match is often wrong for common names
**Context**: MEDUZA matched "Eddie Meduza" (Swedish rock) instead of "MEDUZA" (Italian house group)
**What happened**: MusicBrainz search returns by score. "Eddie Meduza" had score=100, correct "MEDUZA" had score=91.
**Root cause**: First-match-above-threshold picks the wrong artist when names are shared.
**Action**: Among candidates within 10 score points, prefer exact name match (case-insensitive). Implemented in `_pick_best_match()`.

### 2026-04-03 — [codebase] MusicBrainz tags include non-genre junk that creates false graph edges
**Context**: Ludovico Einaudi placed in Trap cluster. MusicBrainz tagged him "italian" — same tag as Sfera Ebbasta.
**Root cause**: MusicBrainz community tags include nationality, roles, decades, junk. These create false genre-similarity edges.
**Action**: `_NON_GENRE_TAGS` blocklist (~100 entries) filters nationality, decades, roles, meta tags. Applied at fetch time in `musicbrainz_client.py`.

### 2026-07-29 — [codebase] Module-level AsyncIOScheduler breaks a second `TestClient(app)`
**Context**: `pytest -q` gives 526 passed / 8 failed. The 4 in `test_privacy.py` fail with `RuntimeError: Event loop is closed`, but each one **passes when run alone**.
**What happened**: Every `with TestClient(app)` runs the app lifespan, which does `scheduler.start()` then `scheduler.shutdown(wait=False)` on exit. The first client in a file passes, every later one fails.
**Root cause**: `scheduler = AsyncIOScheduler()` is instantiated at module scope (`app/main.py:87`), so it is a process-wide singleton. The second `TestClient` restarts that same object on a fresh event loop while APScheduler still holds a reference to the first, now-closed one. Nothing to do with `asyncio_mode` — these are sync tests with no async marker, so pytest-asyncio config cannot affect them.
**Action**: Don't bind asyncio objects to module scope when the app lifespan starts them — build the scheduler inside `lifespan()`. Until then, a test file must not open more than one `TestClient(app)` context: share a single module-scoped client fixture. When a test passes alone but fails in the file, suspect a loop-bound global before suspecting the test.

### 2026-03-21 — [codebase] Falsy-zero bug: `not t.get("popularity")` treats 0 as missing
**Context**: `popularity_cache.py` line 31 used truthiness check on a numeric field.
**Root cause**: Python `not 0` is `True`.
**Action**: For numeric fields that can be 0, always use `is None` check, never truthiness.

### 2026-07-29 — [workflow] Il run-log del loop viene committato dall'hook, non dal loop
**Context**: Run `NOOP-BUSY` del loop `progetto-wrap-dev-loop`. Il contratto del loop, nei rami che cedono il passo, dice di non committare: si scrive solo la voce nel registro `docs/loop-last-run.md` e si termina. Il report di fine run ha dichiarato, correttamente per quel contratto, che la voce restava non committata.
**What happened**: A fine turno il file risultava committato comunque, come `91937b2 chore(auto): salva 1 file di fine turno`, e `git status --porcelain` era vuoto. Nessun `git add`/`git commit` era stato eseguito dal loop.
**Root cause**: L'hook globale di fine turno (`finalize-stop.py`, autorizzazione permanente all'auto-commit nel CLAUDE.md globale) committa ciò che la sessione ha scritto e non ha committato. Sta fuori dal repo, quindi il contratto del loop non lo governa e non può sopprimerlo.
**Action**: (1) Un run del loop non deve dichiarare «resta non committato» come stato finale: la frase vale al massimo fino alla fine del turno. Dire invece cosa **il loop** ha committato, e verificare `git log` dopo, non prima. (2) Un run successivo che trova commit `chore(auto): ...` non li tratti come lavoro sporco di altri o come push anomalo: sono l'hook di questa macchina, e il confronto che conta per il divieto di pubblicazione resta `git rev-parse @{u}`, che qui non si è mosso. (3) L'effetto è benigno e allineato al Passo 5 del contratto — la working tree resta pulita per il run dopo — ma non è una garanzia del loop: senza l'hook la voce resterebbe scoperta.

### 2026-07-30 — [tooling] Here-string PowerShell in `git commit -m` spezza il messaggio in pathspec
**Context**: Commit dell'item 3 del loop `progetto-wrap-dev-loop`, messaggio multi-riga con apostrofi e parentesi. Passato come here-string single-quoted: `git commit -m @'...'@`.
**What happened**: Exit 1, **nessun commit creato**, e tre errori che non nominano il messaggio: `error: pathspec 'state' did not match any file(s) known to git`, più due frammenti di frase trattati come path. Il commit sembra fallito per colpa dei file in stage, non del messaggio — lo stage era corretto.
**Root cause**: Windows PowerShell 5.1 non passa una here-string a un eseguibile nativo come singolo argomento: la ri-tokenizza sugli spazi. Ogni parola del corpo diventa un argomento posizionale, e `git commit` interpreta gli argomenti dopo `-m <primo token>` come pathspec. Le parentesi e gli apostrofi nel testo rendono lo split ancora più imprevedibile. Non è un problema di encoding né di quoting del messaggio.
**Action**: Per ogni messaggio di commit multi-riga su questa macchina, scrivere il testo in un file (scratchpad di sessione) e usare `git commit -F <path>`. Vale anche per gli altri eseguibili nativi con argomenti lunghi: here-string a `git`/`docker`/`npm` non è affidabile in PS 5.1. Corollario di lettura: `pathspec did not match` dopo un `-m` multi-riga va letto come «il messaggio è stato spezzato», non come «lo stage è sbagliato» — verificare con `git status --porcelain` prima di rifare l'add.
**Fratello in Bash, 2026-07-30 (item I-1)**: lo stesso guaio esiste sull'altra shell, con sintomo diverso. Un heredoc `cat >> docs/loop-last-run.md << 'RUNLOG_EOF'` con 130 righe di prosa italiana è morto in parsing — `unexpected EOF while looking for matching '` — **senza scrivere niente**. Delimitatore quotato, quindi il contenuto sarebbe dovuto essere letterale; non ho isolato quale carattere lo rompe. La generalizzazione che regge su entrambe le shell: **un payload lungo di prosa non passa mai per il quoting di una shell**. Scrivilo con il tool Write nello scratchpad, poi accodalo (`Add-Content -Raw -Encoding UTF8`) o passalo per riferimento (`git commit -F`). Corollario di verifica: dopo l'accodamento controlla `git diff --stat` — solo inserzioni, zero cancellazioni — perché un heredoc andato male può anche troncare invece di non scrivere.

**Contro-esempio 2026-07-30 (item 5)**: la stessa costruzione `git commit -m @'...'@` ha funzionato, messaggio di 3 paragrafi arrivato intero (verificato con `git log -1 --format=%B`), apostrofo compreso. La differenza visibile con il caso rotto è che qui il corpo **non conteneva parentesi tonde**; non ho isolato la causa con una prova controllata, quindi lo annoto come osservazione e non come regola. Conseguenza pratica: «here-string sempre rotta» è **troppo forte** — l'`Action` qui sopra resta la via sicura, ma un fallimento non va diagnosticato assumendo che la here-string sia l'unica spiegazione possibile. Verificare sempre il messaggio con `git log -1 --format=%B` dopo un commit multi-riga, invece di fidarsi dell'exit code: è l'unico controllo che distingue i due casi.

### 2026-07-30 — [tooling] Il tool Bash mangia i backslash dei path Windows: lo script non parte mai
**Context**: Passo 0 del loop `progetto-wrap-dev-loop`, comando `"C:\...\python.exe" C:\Users\fgioa\.claude\scripts\loop_yield.py --repo-root "..."` eseguito nel tool Bash (Git Bash). Successo per tre run consecutivi: item 3, item 4, item 5.
**What happened**: Exit 2 con `can't open file 'C:\Users\fgioa\Desktop\PRO\progettoWrap\Usersfgioa.claudescriptsloop_yield.py'`. I backslash sono spariti e il resto del path si è incollato alla cartella di lavoro corrente. Rieseguito identico in PowerShell con l'operatore `&`, risponde `LIBERO`.
**Root cause**: Git Bash tratta il backslash come carattere di escape, non come separatore di cartelle. Un path Windows non quotato viene consumato carattere per carattere e ciò che resta è una stringa relativa, che Python risolve rispetto alla cartella corrente — di qui il path assurdo, che sembra un file mancante nel repo e non un errore di shell.
**Action**: Su Windows i path assoluti vanno al tool **PowerShell**, con `&` e le virgolette; se serve Bash, usare le forward slash (`C:/Users/...`), che Git Bash accetta. **Il punto di lettura conta più della regola**: per il loop, questo exit 2 **non** è il caso `NOOP-UNDECIDABLE` («la guardia non sa rispondere») — la guardia non è mai stata avviata, quindi il run prosegue dopo aver rieseguito il comando nella shell giusta. Confonderli fa cedere un run che poteva lavorare.
**Aggiunta 2026-08-01 (item I-8), rimedio più economico**: restare in Bash e **quotare il path dello script**, esattamente come già si quotano quello dell'interprete e `--repo-root`. Provato: stesso comando, stesso tool, `LIBERO` al secondo tentativo, nessun cambio di shell. La causa lo spiega — Git Bash consuma i backslash solo *fuori* dalle virgolette — e mostra che l'errore vero è **un'asimmetria di quoting**: i path quotati sopravvivevano, quello nudo no. Regola pratica: in Bash su Windows si quotano **tutti** i path della riga, non solo quelli con spazi. Restano valide le altre due strade; questa costa un carattere per parte.

### 2026-07-30 — [workflow] Un run-log che cita una lezione va verificato sulla lezione, non sul run-log precedente
**Context**: Run dell'item 5. Nel run-log ho scritto che la lezione sul tool Bash «è già a verbale in `.claude/tasks/lessons.md`», riprendendo la frase dal run-log dell'item 4, e ho committato.
**What happened**: In fase di finalize il `grep` su `lessons.md` non ha trovato nulla: la lezione **non c'era**. Il run-log dell'item 3 diceva di averla registrata, ma ciò che era finito in `lessons.md` era un'altra cosa — la here-string di `git commit`, un guasto diverso dello stesso run. L'affermazione committata era falsa e andava corretta con una modifica successiva.
**Root cause**: Ho trattato il run-log precedente come fonte autorevole sullo stato di un **altro** file. È esattamente il divieto del CLAUDE.md globale («artefatto autorevole prima della diagnosi: mai da memoria, leggi PRIMA la fonte»), applicato però a un artefatto di seconda mano invece che alla memoria — la trappola è che un documento scritto sembra già una verifica.
**Action**: Prima di scrivere «X è già registrato in Y», aprire Y e cercarci X. Vale in particolare fra i run di un loop, dove ogni run parte a memoria zero e l'unica tentazione è fidarsi del run-log precedente: quel file racconta **cosa un run ha creduto di fare**, non lo stato attuale del repo. Lo stato attuale si legge solo dal file di cui si parla.

### 2026-07-30 — [testing] Date di calendario cablate nei test marciscono contro una finestra mobile
**Context**: Item 4 del loop. Quattro test in `test_temporal_patterns.py` fissavano `datetime(2026, 3, 25, ...)` e fallivano con `assert 0 == 2`, `assert 0 == 3`. Il backlog li dava per «una sola causa comune legata al fuso orario».
**What happened**: Non c'entrava il fuso orario. `compute_temporal_patterns` scarta gli ascolti più vecchi della sua finestra (`temporal_patterns.py:106`, `days=30`): il 25 marzo era ormai 127 giorni indietro, ogni play veniva filtrato e la pipeline restituiva `_empty_result()`. Tutti gli zeri arrivavano da lì, non da un calcolo rotto.
**Root cause**: Un test con data assoluta contro un servizio con finestra relativa a `now()` passa il giorno in cui lo scrivi e si rompe da solo dopo N giorni, senza che nessuno tocchi il codice. Il sintomo che inganna è che il valore atteso non arriva **mai**: sembra logica sbagliata, non input fuori intervallo.
**Action**: (1) Nei test contro codice che filtra per finestra temporale, le date si costruiscono **relative a `datetime.now()`** (qui `_recent_day`/`_recent_weekday`), mai come costanti di calendario. (2) Serve un giorno della settimana preciso? Calcolalo all'indietro dall'oggi (`(anchor.weekday() - target) % 7`), non fissare la data. (3) Fissa il taglio con un test dedicato sui due lati della soglia (`TestTimeWindowCutoff`): rende esplicito il comportamento che altrimenti divora gli altri test in silenzio. (4) Diagnosi rapida: se **tutti** gli assert di un test danno 0 e i test vicini che usano `now()` passano, sospetta la finestra prima della logica.

### 2026-07-30 — [testing] Il frontend non ha un test runner, e l'ispezione ha scritto criteri che nessuno può eseguire
**Context**: Riapertura della coda del loop sui 9 finding dell'ispezione frontend. Prima di consegnarli al loop ho controllato con che cosa si sarebbero verificati.
**What happened**: `frontend/package.json` espone solo `dev`, `build`, `preview`, `lint` — **`npm test` non esiste**, non c'è Vitest né altro. Ma diversi criteri di verifica scritti dal giro di ispezione sono comportamenti osservabili: I-4 chiede di provare che esportazione e cancellazione mostrino un messaggio «con le due chiamate che rispondono errore», e quella pagina sta pure dietro l'autenticazione, quindi non è apribile senza `.env` e senza login Spotify (vietato al loop). Il criterio non è raggiungibile con nessuno strumento presente nel repo.
**Root cause**: Il giro di ispezione ha guardato il codice e ha scritto cosa sarebbe giusto osservare, senza mai chiedersi **con quale strumento** lo si sarebbe osservato. È un'asimmetria strutturale della fase di ispezione: chi ispeziona non implementa, quindi non incontra mai il muro della verifica, e lo lascia in eredità a nove giri successivi che invece ci sbattono. Il rischio concreto non è lo stallo — è che un run, dovendo chiudere l'item, dichiari «verificato» qualcosa che non ha potuto osservare.
**Action**: (1) Una fase di ispezione deve dichiarare, per ogni criterio che scrive, **con quale mezzo si verifica**, scegliendo fra i mezzi che il repo ha davvero; un criterio senza mezzo è un item non chiudibile. (2) Qui i mezzi sono tre e sono ora scritti in testa alla sezione «Trovati dall'ispezione» di `docs/LOOP-BACKLOG.md`: dal vivo (solo ciò che si raggiunge senza backend e senza login, cioè la LoginPage e gli errori a backend spento), sul codice (tutto ciò che sta dietro l'autenticazione), meccanicamente (`npm run lint` e `npm run build` a 0 — necessari sempre, sufficienti per nessun item da solo). (3) Il run-log deve dire **quale** dei tre ha usato, per ogni item; «verificato dal vivo» su una pagina non apribile è una prova inventata. (4) Se servono verifiche comportamentali vere, va introdotto Vitest come item a sé **prima** degli altri — non di soppiatto dentro un item di correzione.

### 2026-07-30 — [frontend] Un'ancora fra pagine non funziona nemmeno quando l'id esiste: react-router non scorre
**Context**: Item I-3 del loop. Il finding diceva: la scheda «Streak» punta a `/temporal#streak` ma in `TemporalPage.jsx` non c'è nessun elemento con quell'identificatore. Rimedio apparente: aggiungere l'id.
**What happened**: Aggiungere solo l'id non avrebbe cambiato niente per l'utente. Un `<Link to="/temporal#streak">` fa una `pushState`, che **non è una navigazione al frammento**: il browser aggiorna l'indirizzo e resta dov'è. L'app usa `BrowserRouter` in modalità dichiarativa (`App.jsx:154`), quindi non ha nemmeno `ScrollRestoration`, che è l'unico pezzo di react-router che gestisce il frammento. Le altre quattro ancore del frontend funzionavano solo perché sono tutte **nella stessa pagina**, e per quelle `KPICard.jsx:99-110` chiama `scrollIntoView` da sé senza passare dal router. `/temporal#streak` era l'unica fra pagine, quindi l'unica scoperta.
**Root cause**: L'ispezione ha cercato il bersaglio mancante e si è fermata lì, senza chiedersi **chi dovrebbe portare l'utente** al bersaglio. È il difetto tipico di chi legge il codice per pagine invece che per percorsi: l'estremo di partenza e quello di arrivo si vedono, il tratto in mezzo — che qui è del framework, non del progetto — non ha un file dove essere guardato. Non si vede nemmeno provando, perché senza l'id il sintomo dei due guasti è identico: l'utente resta in cima alla pagina.
**Action**: (1) Su questo repo, un'ancora fra pagine richiede **due** pezzi: `id="<frammento>"` sulla destinazione **e** un gestore che scorra dopo il cambio di indirizzo (`hooks/useHashScroll.js`, invocato da `AppLayout`). Aggiungerne uno solo lascia il difetto intatto. (2) Il gestore deve **riprovare per qualche secondo**, non guardare una volta sola: al cambio di indirizzo la destinazione non è ancora montata (`AnimatePresence mode="wait"` la monta dopo l'uscita della pagina precedente) e la sezione compare solo quando la sua richiesta dati si risolve. Un `getElementById` singolo trova `null` e non scorre mai. (3) L'intestazione è appiccicata e alta 64px: il bersaglio porta `scroll-mt-20` (80px), altrimenti scorre sotto l'intestazione e il titolo resta coperto. (4) Diagnosi rapida: se un salto interno non porta dove promette, controlla **prima** se è nella stessa pagina o fra pagine — sono due meccanismi diversi, e solo il primo funziona da solo.

### 2026-07-31 — [frontend] Un `catch` vuoto che delega a un intercettore condiviso copre solo ciò che quell'intercettore copre
**Context**: Item I-4 del loop. `PrivacyPage.jsx` aveva `catch { /* axios interceptor handles 401/429 */ }` sull'esportazione dei dati, e sulla cancellazione dell'account un `catch` che chiudeva la finestra di conferma.
**What happened**: Il commento era **esatto** su ciò che l'intercettore fa, e proprio per questo ingannava su ciò che non fa: `api.js:31-58` gestisce solo il 429 (ritenta) e il 401 (evento `auth:expired`), e su tutto il resto — 500, 502, rete caduta, timeout — fa `Promise.reject` senza toccare l'interfaccia. Sull'esportazione il bottone tornava in chiaro senza che si scaricasse niente. Sulla cancellazione era peggio: il `catch` chiudeva la finestra di conferma, cioè **lo stesso gesto del successo**, quindi un'eliminazione fallita era indistinguibile da una riuscita, sull'azione più irreversibile dell'applicazione.
**Root cause**: Il commento documentava la copertura del delegato, non il buco. Un intercettore condiviso è un contratto **parziale**: delegargli il caso d'errore senza nominare i casi che restano fuori trasforma «gestito altrove» in «non gestito», e il commento rende la cosa invisibile a chi rilegge, perché sembra una scelta ponderata.
**Action**: (1) Su questo repo l'intercettore di `lib/api.js` copre **solo** 401 e 429: ogni altro esito arriva al chiamante e, se il chiamante tace, nessuno parla. Un `catch` vuoto è accettabile solo dove l'unico errore possibile è uno di quei due. (2) **Un ramo d'errore non deve mai riusare il gesto del successo** — chiudere la finestra, redirigere, azzerare il modulo sono il vocabolario del «fatto». Sull'errore l'interfaccia resta dov'è e dichiara l'accaduto. (3) Per le azioni irreversibili il messaggio deve dire **in che stato sono rimasti i dati** («il tuo account e i tuoi dati sono ancora al loro posto»), non solo che l'operazione è fallita: è l'unica cosa che l'utente non può verificare da sé. (4) `err.response?.data?.detail` non è sempre una stringa — sulle risposte `responseType: 'blob'` non è leggibile affatto e FastAPI usa una lista sugli errori di validazione: controlla il tipo prima di stamparlo, o finisce `[object Object]` in faccia all'utente.

### 2026-07-31 — [frontend] Fra «mostra il vuoto» e «nascondi la sezione» decidono i collegamenti che entrano lì, non lo stile
**Context**: Item I-5 del loop. Le tre colonne di `TasteEvolutionPage.jsx` ricevevano `emptyText` ma il componente non lo elencava in firma e il ramo vuoto rendeva `null`. L'item concedeva due strade — mostrare il testo, oppure togliere il parametro e nascondere la colonna vuota — e la convenzione del progetto («le sezioni senza dati si nascondono») sembrava indicare la seconda.
**What happened**: La seconda strada avrebbe rotto tre delle quattro schede in cima alla stessa pagina. `KPICard.jsx:105` salta con `document.getElementById(...)?.scrollIntoView(...)`: l'incatenamento opzionale fa sì che **un'ancora mancante produca un clic che non fa niente e non dice niente**. «Fedeltà» e «Artisti Fedeli» puntano a `#loyal-artists`, «Turnover» a `#rising-artists` — e quelle ancore sarebbero sparite **nello stesso identico caso** in cui le schede segnano 0, compresa quella il cui suggerimento dice «Clicca per vederli».
**Root cause**: La convenzione è scritta come regola di stile e si legge come se valesse ovunque, ma parla del segnaposto generico «nessun dato disponibile» — di cui in questo frontend esiste **un solo** esemplare (`AdminPage.jsx:442`). Applicarla a un bersaglio di ancora la trasforma da regola di pulizia in generatore di collegamenti morti: nascondere un elemento non toglie chi ci punta.
**Action**: (1) Prima di nascondere una sezione vuota, **cerca chi ci punta**: `grep` del suo `id` fra i `link=`/`href=`/`scrollIntoView` del frontend. Se qualcuno ci punta, il bersaglio resta e dichiara il vuoto. (2) Un'ancora rotta qui **non si vede**: `?.scrollIntoView()` non lancia, non logga, e `npm run lint`/`npm run build` restano verdi. L'unica prova è la lettura del percorso, non un comando. (3) Il caso peggiore è quando bersaglio e sorgente si svuotano **insieme** — è la norma, non l'eccezione, perché di solito leggono lo stesso dato: la rottura appare esattamente quando l'utente ha più bisogno della spiegazione. (4) Se il contatore nell'intestazione mostra `0` comunque, «nascondere» non fa sparire niente: rende solo muto un riquadro che resta.

### 2026-07-31 — [frontend] Un censimento che prende per perimetro una cartella misura sé stesso, non il problema
**Context**: Item I-6 del loop. Il finding contava «120 colori cablati in 24 file» e aveva cercato dentro `frontend/src`. Portati tutti gli esadecimali in `src/lib/palette.js`, il conteggio dentro `src` era sceso a zero e l'item sembrava chiuso.
**What happened**: Non lo era. Cambiando la sola riga `indigo` di `palette.js` e ricostruendo, il vecchio accento `#6366f1` restava in **2** punti del pacchetto: `index.html:7` (`<meta name="theme-color">`, cioè la barra del browser sul telefono) e `vite.config.js:13-14` (`theme_color` e `background_color` del manifesto dell'app installabile). Stanno entrambi **fuori da `src/`**, cioè fuori dal perimetro in cui il censimento aveva contato — quindi non erano mai comparsi nei 120, e chiudere l'item sul conteggio li avrebbe lasciati lì.
**Root cause**: Il perimetro della ricerca era diventato, di fatto, la definizione del problema. Un censimento fatto su una cartella e poi verificato **sulla stessa cartella** non può che tornare a zero: la verifica ripete l'assunzione della misura invece di metterla alla prova. E i due superstiti erano proprio i file che non sembrano interfaccia — configurazione e HTML statico — cioè quelli che nessuno apre quando pensa «colori».
**Action**: (1) Su questo repo i colori del prodotto vivono in `src/lib/palette.js`, e `index.html` **non può importarlo**: i suoi segnaposto `__COLOR_*` li riempie `vite.config.js` con un innesto `transformIndexHtml`, che vale sia in `build` sia nel server di sviluppo (verificato servendo la pagina). (2) La verifica di una centralizzazione non si fa contando le occorrenze rimaste, ma **cambiando il valore in un punto e ricostruendo**: ciò che non si muove è ciò che è rimasto fuori, e lo dice senza bisogno di sapere dove cercare. (3) Come sentinella non usare `#ff0000`: la minificazione CSS la riscrive in `red` e i conteggi risultano falsati per difetto — serve un colore senza forma abbreviata né nome, tipo `#7d2b8c`. (4) `npm run lint` e `npm run build` restano verdi qualunque colore si scriva: su una palette non fanno da rete, mai usarli come prova.

### 2026-08-01 — [workflow] Cercare il nome di un tipo trova anche l'identificatore che lo contiene, e risponde il falso
**Context**: Item I-7 del loop. Per chiudere B1 di `todo.md` con una data vera invece che con un generico «già fatto», serviva sapere in quale commit `GenreTreemap` aveva smesso di essere un treemap. Ho scorso i sette commit che toccano il file cercandoci la stringa `Treemap`.
**What happened**: Risposta `TREEMAP` su **tutti e sette**, ciambelle comprese. Sembrava che il componente non fosse mai cambiato, cioè l'esatto contrario del vero. La stringa non veniva dal componente di recharts ma dal nome del componente locale, `GenreTreemap`, che compare in ogni versione del file. Rifatta la ricerca sull'**import da recharts** — l'unica cosa che distingue davvero i due disegni — il salto è netto: `Treemap` fino a `0d67cb7`, `PieChart, Pie, Cell` da `58e39f2` (2026-04-03) in poi.
**Root cause**: Ho cercato un **concetto** («qui c'è un treemap») con una ricerca di **testo**, in un file dove quel testo compare anche per un'altra ragione. È un falso positivo che non si annuncia: il conteggio non è zero, quindi la ricerca sembra aver funzionato, e il risultato sbagliato ha la stessa forma di quello giusto. Aggravante specifica di questo item: il difetto da correggere **era proprio** un nome che mente, quindi il rumore veniva dalla cosa stessa che stavo indagando — la ricerca ingenua non poteva che confermare la bugia.
**Action**: (1) Per datare un cambio di comportamento in un file, cerca il **punto di ingresso della dipendenza** (la riga `import`, la chiamata all'API esterna), non il nome del concetto: l'import è l'unico posto che non può mentire, perché è ciò che il codice fa davvero. (2) Quando la ricerca di una stringa torna positiva su **tutte** le revisioni di un file, sospetta il falso positivo prima di concludere «non è mai cambiato»: un file che non cambia mai è più raro di una ricerca formulata male. (3) Prima di fidarsi del conteggio, guarda **la riga che ha fatto match**, non solo il numero — qui bastava vederla per capire che era la riga dell'`export default`. (4) Vale in particolare sui rinomina: finché il nome vecchio sopravvive, ogni ricerca su quel nome mescola le occorrenze del concetto e quelle dell'identificatore.

### 2026-08-01 — [frontend] Una rotta di raccolta che rimanda invece di dire «non esiste» nasconde tutti i collegamenti rotti
**Context**: Item I-8 del loop. `App.jsx:146` mandava alla radice ogni indirizzo non riconosciuto, e la radice manda alla dashboard chi ha una sessione. Sembra una cortesia verso l'utente: non lo lasci mai davanti a un errore.
**What happened**: Quella cortesia costa la diagnosi di un'intera classe di difetti. Un collegamento interno rotto non si distingue da uno funzionante: l'utente clicca, la pagina cambia, e arriva **da qualche parte** — solo non dove era promesso. È precisamente il motivo per cui il difetto I-2 è sopravvissuto fino all'ispezione: la scheda «Artisti unici» puntava a `/artist-network`, una rotta che non esiste, e il clic ricaricava la dashboard su cui l'utente era già. Nessun errore, nessuna traccia in console, niente da cercare. Con una pagina «non trovato» al suo posto, quel difetto si sarebbe annunciato da solo al primo clic.
**Root cause**: Il ripiego era stato pensato per l'**utente** e nessuno ha considerato che azzera anche il segnale per **chi sviluppa**. Un rimando riuscito e un indirizzo sbagliato producono lo stesso identico esito osservabile, quindi il difetto non ha nessun sintomo — e un difetto senza sintomo non viene cercato. È la forma generale del guaio: ogni ripiego silenzioso nasconde esattamente la categoria di errori che è lì per assorbire.
**Action**: (1) La rotta di raccolta rende una pagina che **nomina l'indirizzo cercato**; un cartello generico non basta, perché è l'indirizzo a rivelare il refuso o il collegamento vecchio. (2) Su questo repo la rotta di raccolta passa da `ProtectedRoute`: chi ha la sessione vede la pagina dentro il guscio, con la barra laterale per andarsene, e chi non ce l'ha continua ad arrivare alla schermata di accesso. Renderla pubblica scambierebbe una destinazione sbagliata con un'altra. (3) **Prima** di toccare quella rotta, verifica quali indirizzi non arrivano mai al router: qui `/auth`, `/api` e `/health` sono deviati al backend dal server di sviluppo e sono esclusi dal ripiego dell'app installabile (`navigateFallbackDenylist`), quindi il ritorno di Spotify dopo il consenso non passa di lì. Senza questo controllo si teme di rompere l'accesso, o lo si rompe davvero. (4) Dopo aver aggiunto la pagina «non trovato», ricontrolla i collegamenti interni: da quel momento affiorano da soli quelli che il rimando teneva nascosti.

## Archive
Resolved or one-off entries. Not read by agents.

### 2026-03-21 — [codebase] TrackPopularity had no writer — RESOLVED 2026-04-02
Writer implemented: `sync_recent_plays` now correctly iterates `all_items` (was `items` — last page only). Fixed `popularity == 0` rejection. Table populates on every hourly sync.

### 2026-03 — [codebase] html2canvas doesn't resolve CSS variables
Pass explicit `backgroundColor: '#121212'` to html2canvas options. Fixed.

### 2026-03 — [codebase] framer-motion AnimatePresence requires mode="wait"
Always use `mode="wait"` for sequential page transitions. Fixed.

### 2026-03 — [codebase] Spotify IDs aren't always 22 characters
Use regex `{15,25}` for Spotify ID validation. Fixed.

### 2026-03 — [codebase] Expected 403s confuse debugging
Deprecated API 403s are expected — check if handled before investigating. Resolved.

### 2026-03 — [codebase] Deprecated API calls removed
get_or_fetch_features → pure cache lookup, get_recommendations removed, get_related_artists removed. All resolved.

### 2026-03 — [codebase] Various fixes
globals.css path, circular import, datetime.utcnow(), CI branch, snapshot dedup, rate limiter memory leak, X-Forwarded-For, TrendTimeline gradients, MoodScatter quadrants, PlaylistComparePage stale comparison. All resolved.

### 2026-03-14 — [codebase] Artist network data quality issues — RESOLVED
NetworkX + fuzzy genre matching implemented. BFS replaced with Louvain communities, PageRank + betweenness centrality added. Tooltips fixed. Resolved by scikit-learn + NetworkX integration feature.
