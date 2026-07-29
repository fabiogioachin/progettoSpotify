# LOOP BACKLOG — progettoWrap

LOOP HALTED

> **Il marcatore `LOOP HALTED` qui sopra ferma il loop.** Finché c'è, ogni run esce subito
> senza toccare niente. Toglilo tu quando questa lista ti convince.
>
> Questa è una **bozza**, ricavata da `docs/LAUNCH-PLAN.md` e `docs/RESTRUCTURING-PLAN.md` il
> 2026-07-29. Il piano di ristrutturazione risulta completato; quel che resta è la strada verso la
> beta fra amici. Rivedi, riordina, cancella quel che non vuoi.

## Come si legge

Il loop prende **il primo item non completato** e fa solo quello. Un run, un item.

- `[ ]` da fare · `[x]` fatto · `[FAILED]` tentato e fallito, con l'errore accanto
- `[BLOCKED_USER]` richiede una decisione o un'azione tua: il loop lo salta senza toccarlo

Ogni item deve dire **come si verifica che è fatto**. Un item senza criterio di verifica il loop non
lo sa chiudere, e resterà lì a bloccare la coda.

---

## Item

### 1. `[ ]` Allineare LAUNCH-PLAN a ciò che esiste davvero

Lo Step 2 del piano di lancio descrive come **da fare** cose che nel repo ci sono già:
`docker/docker-compose.prod.yml`, `docker/caddy/`, e due workflow GitHub (`ci.yml`, `build.yml`).
Un piano che descrive come futuro ciò che è presente fa sprecare un giro a chiunque lo legga.

Cosa fare: confrontare voce per voce lo Step 2 con i file reali, spuntare ciò che esiste, lasciare
aperto solo ciò che manca davvero.

**Verifica**: nessuna voce dello Step 2 descrive come da creare un file che esiste nel repo.

### 2. `[ ]` Il workflow di CI non esegue i test, solo il lint

`ci.yml` ha un job `backend-lint`. La suite in `backend/tests/` (una trentina di file) non risulta
girare in CI. Un test che nessuno esegue automaticamente è un test che scopri rotto tardi.

Cosa fare: aggiungere un job `pytest` al workflow, sullo stesso Python 3.12 già usato dal lint.

**Verifica**: `pytest` gira in CI e la suite passa; se qualche test è rosso, l'item si chiude
comunque solo quando è verde — se non ci riesci in 3 tentativi, marca `[FAILED]` con l'errore vero.

### 3. `[ ]` Lint frontend pulito

`npm run lint` deve uscire senza errori. Oggi non è verificato.

**Verifica**: `cd frontend && npm run lint` → exit 0.

### 4. `[ ]` Script di backup del database, versionato

Il piano di lancio descrive un `pg_dump` schedulato con rotazione 7 giornalieri + 4 settimanali, ma
lo lascia come riga di crontab da incollare a mano sul server. Uno script scritto una volta e
lasciato solo nella documentazione è uno script che nessuno rivede.

Cosa fare: metterlo nel repo (`docker/backup/`), con la rotazione dentro, e documentarne
l'installazione.

**Verifica**: lo script gira in locale contro il Postgres di sviluppo e produce un `.sql.gz`
leggibile; la rotazione è coperta da un test o da una prova documentata.

### 5. `[BLOCKED_USER]` Workflow di deploy sul VPS

Serve un server, un dominio e una chiave SSH — decisioni e acquisti tuoi. Finché non esistono,
scrivere `deploy.yml` significa scrivere qualcosa che non si può provare.

Sblocca quando: VPS attivo, dominio puntato, secret SSH nel repo GitHub.

### 6. `[BLOCKED_USER]` Extended Quota Spotify

Richiede screenshot dell'app in produzione e una privacy policy raggiungibile su dominio pubblico.
Dipende dall'item 5. Per la beta fino a 5 amici non serve: è la scelta che hai già scritto nel piano.

---

## Cose che il loop non deve fare

- Toccare `.env`, secret, o la configurazione dell'app Spotify Developer
- Fare `git push` (nessuno)
- Aprire connessioni verso Spotify con credenziali reali per "provare"
- Dedurre item nuovi da solo: questa lista la scrivi tu
