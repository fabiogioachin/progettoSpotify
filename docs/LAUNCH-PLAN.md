# Launch Plan — Beta tra Amici

## Obiettivo

Primo lancio dell'app tra 5-20 amici con account Spotify Premium. L'app è funzionante in locale — servono: bug fix, polish UI, deploy su VPS, e (opzionale) Extended Quota per superare il limite di 5 utenti dev mode.

---

## Pre-requisiti completati

- [x] PostgreSQL + Redis (Docker Compose)
- [x] Auth invite-gated con PKCE + HMAC state
- [x] Rate limit 4 livelli (API, user quota, Spotify throttle, budget priority)
- [x] PWA installabile
- [x] Empty states + error boundaries — vedi nota sotto
- [x] Admin dashboard
- [x] Onboarding flow
- [x] Privacy/GDPR (export + delete)
- [x] Structured logging + health endpoints
- [x] API v1 versioning con redirect 308
- [x] Data retention policy
- [x] Background jobs staggerati multi-user

### Nota sugli empty state (aggiornata il 2026-07-30)

Gli empty state **non** passano da un componente condiviso: una sezione senza dati **si nasconde**.
Il chart restituisce `null` e il genitore decide se mostrare o no il blocco — è la convenzione
scritta in `.claude/CLAUDE.md` («Empty sections: hide rather than showing "nessun dato
disponibile"») e in `.claude/skills/react-spotify-patterns/SKILL.md:116`, che vieta esplicitamente
l'empty state dentro i chart. Il comportamento è nel codice: `AudioRadar.jsx:28`,
`GenreDonut.jsx:29`, `MoodScatter.jsx:24`, `TrendTimeline.jsx:25`, `ListeningHeatmap.jsx:97`,
`ArtistNetwork.jsx:420`, `OverlapHeatmap.jsx:27`, `PlaylistComparison.jsx:24`,
`TasteOverlapBar.jsx:24`, `StreakDisplay.jsx:14`.

Un messaggio testuale di «nessun dato» esiste in **un solo punto** di tutto il frontend
(`AdminPage.jsx:442`). Quindi la voce qui sopra non va letta come «ogni pagina ha il suo empty
state»: la scelta di prodotto è l'opposto, cioè non mostrare nulla.

`components/ui/EmptyState.jsx`, previsto dalla Phase 3 di `RESTRUCTURING-PLAN.md:188`, è stato
creato e **mai importato da nessuno**: la convenzione è cambiata dopo. Rimosso il 2026-07-30 dal
loop di sviluppo (item 3 di `LOOP-BACKLOG.md`). Le righe di `RESTRUCTURING-PLAN.md` che lo citano
restano come traccia storica di ciò che era stato pianificato allora.

La metà «error boundaries» della voce è invece piena: `SectionErrorBoundary` avvolge le sezioni di
9 pagine (`DashboardPage`, `ProfilePage`, `TemporalPage`, `ArtistNetworkPage`, `DiscoveryPage`,
`TasteEvolutionPage`, `PlaylistAnalyticsPage`, `PlaylistComparePage`, `FriendsPage`).

---

## Step 2: Deploy Pipeline (ex Phase 6)

> **Riscritto il 2026-09-14 confrontando voce per voce con il repo.** Prima di questa revisione lo
> Step 2 chiedeva di creare quattro cose che nel repo c'erano già, e chi avesse seguito il piano
> alla lettera avrebbe riscritto file funzionanti credendo di partire da zero. Ora ogni voce dice
> prima che cosa esiste e poi che cosa manca davvero. **Quello che manca è il deploy vero e
> proprio**: la macchina, il dominio, il reverse proxy configurato e il workflow che pubblica.

### 2.1 VPS Setup — `[ ]` da fare, dipende da acquisti tuoi

- **Provider**: Hetzner CX22 (~5€/mese) — 2 vCPU, 4GB RAM, 40GB SSD
- **OS**: Ubuntu 24.04 LTS
- **Dominio**: acquistare dominio (es. `tuodominio.it`, ~10€/anno)
- **DNS**: A record → IP del VPS

Nessuna di queste quattro cose si può preparare dal repo: servono un acquisto e una decisione. Nel
backlog del loop di sviluppo è l'item 12, marcato `[BLOCKED_USER]` per questo motivo.

### 2.2 Docker Compose Production — `[x]` il file esiste, `[ ]` tre scostamenti

`docker/docker-compose.prod.yml` **c'è**, e copre quattro servizi: PostgreSQL 16, Redis 7, il
backend e il frontend. Ha già le cose che contano: controlli di salute su tutti e quattro,
`depends_on` condizionato a quei controlli, database e cache **senza porte esposte** all'esterno, le
credenziali lette da `../.env.production`, e un solo processo Uvicorn — scelta voluta, perché con
più processi i lavori pianificati (APScheduler) partirebbero in copia.

Restano tre scostamenti rispetto a questo piano, tutti veri sul file di oggi:

1. **`postgres` e `redis` non hanno `restart: unless-stopped`** (righe 4 e 23; il backend e il
   frontend ce l'hanno, righe 60 e 73). Dopo un riavvio del VPS i due servizi di stato non
   ripartono da soli, e l'app resta in piedi senza database sotto.
2. **Il servizio `caddy` è commentato**, insieme ai suoi due volumi (righe 77-91 e 96-97). Finché
   resta così non c'è HTTPS, e il punto 2.3 qui sotto non ha nulla che lo attivi.
3. **Backend e frontend pubblicano le porte sull'host** (`8001:8001` e `5173:80`). Senza Caddy è
   l'unico modo per raggiungerli, ma il giorno in cui Caddy entra in funzione quelle due porte
   diventano una scorciatoia che aggira l'HTTPS: vanno tolte nello stesso momento.

**Verifica**: `docker compose -f docker/docker-compose.prod.yml config` esce 0 e mostra i quattro
servizi; dopo la correzione del punto 1, `grep -c "restart: unless-stopped"` sul file dà 4.

### 2.3 Caddy (HTTPS automatico) — `[x]` il file esiste, `[ ]` è vuoto

`docker/caddy/Caddyfile` **c'è ma non contiene configurazione**: una riga di commento e nulla
altro. Non va creato, va riempito — e insieme al servizio commentato del punto 2.2, perché un file
di configurazione che nessuno monta non fa niente.

Due cose vanno corrette rispetto alla bozza che questo piano portava prima, perché non
corrispondevano al repo:

- **Il frontend ascolta sulla porta 80, non sulla 5173.** L'immagine è un nginx che serve il build
  statico (`docker/frontend.Dockerfile`), quindi dentro la rete Docker l'indirizzo è `frontend:80`.
  La 5173 è la porta del server di sviluppo Vite, e in produzione non esiste.
- **Il percorso del volume nel servizio commentato è sbagliato**: dice `./Caddyfile`, ma il file di
  composizione sta in `docker/`, quindi quel percorso punta a `docker/Caddyfile`, che non esiste.
  Va scritto `./caddy/Caddyfile`.

Da notare che nginx **già inoltra** `/api` e `/auth` al backend (`docker/frontend.Dockerfile`).
Caddy potrebbe quindi limitarsi a terminare l'HTTPS e passare tutto a `frontend:80`. Meglio però
inoltrare esplicitamente come qui sotto: in quel caso la regola di Caddy vince e quella di nginx
resta inerte, e l'instradamento sta in un posto solo invece che in due.

```
tuodominio.it {
    handle /api/* {
        reverse_proxy backend:8001
    }
    handle /auth/* {
        reverse_proxy backend:8001
    }
    handle /health* {
        reverse_proxy backend:8001
    }
    handle {
        reverse_proxy frontend:80
    }
}
```

**Verifica**: `docker compose -f docker/docker-compose.prod.yml exec caddy caddy validate --config
/etc/caddy/Caddyfile` esce 0, e `curl -I https://tuodominio.it/health` risponde 200 con certificato
valido.

### 2.4 CI/CD (GitHub Actions) — `[x]` lint, test e build ci sono; `[ ]` manca il deploy

**La metà che gira a ogni push esiste già**, in due workflow:

- `.github/workflows/ci.yml` — tre lavori su `push` e `pull_request` verso `master`: lint del
  backend (`ruff check app/`), test del backend (`pytest -q`, con un commento che spiega perché non
  servono i servizi Postgres e Redis), lint e build del frontend (`npm run lint`, `npm run build`).
- `.github/workflows/build.yml` — costruisce le due immagini Docker con i contesti giusti
  (`./backend` e `./frontend`, Dockerfile dentro `docker/`).

**Manca `.github/workflows/deploy.yml`**, e non è una dimenticanza: non c'è nulla su cui pubblicare
finché il punto 2.1 non è fatto. Quando ci sarà, il lavoro di deploy va agganciato ai due workflow
esistenti, non duplicato — riscrivere lint e test dentro il deploy significherebbe farli girare due
volte e poterli far divergere.

```yaml
# .github/workflows/deploy.yml — DA SCRIVERE dopo il punto 2.1
on:
  workflow_run:
    workflows: [CI, Build Docker Images]
    types: [completed]
    branches: [master]

jobs:
  deploy:
    if: github.event.workflow_run.conclusion == 'success'
    runs-on: ubuntu-latest
    steps:
      - SSH into VPS (chiave privata in un secret del repo)
      - git pull
      - docker compose -f docker/docker-compose.prod.yml up --build -d
      - Health check: curl -f https://tuodominio.it/health
```

**Verifica**: un push su `master` innesca i tre workflow nell'ordine giusto, e l'ultimo passo del
deploy riceve 200 dall'indirizzo di salute.

### 2.5 Backup PostgreSQL — `[x]` lo script c'è, manca solo la prova dal vivo

`docker/backup/pg-backup.sh` esiste dal 2026-09-14, con le istruzioni accanto in
`docker/backup/README.md`: rotazione di 7 copie giornaliere più 4 settimanali, riga di crontab
pronta da incollare, e il giro completo per rileggere una copia. Non c'è più niente da scrivere a
mano sul VPS.

La rotazione è coperta da 10 test che eseguono lo script vero nel suo ramo `--prune-only`
(`backend/tests/test_backup_rotation.py`), quindi gira anche in CI e non invecchia.

Quello che **resta aperto** è una prova sola: far girare lo script contro un database vero e
rileggere il `.sql.gz` che produce. Richiede il motore Docker avviato, che è un gesto umano — il
dettaglio sta nell'item 9 di `docs/LOOP-BACKLOG.md`, marcato `[BLOCKED_USER]` per quel motivo.

Il comando di partenza che il piano suggeriva è ormai dentro allo script, ma vale la pena
ricordarne la trappola: il nome del database è `spotify_intelligence`, mentre `spotify` è il nome
dell'utente — lo dice `docker/docker-compose.prod.yml:9`.

**Verifica**: sul VPS, `docker/backup/pg-backup.sh` produce un `.sql.gz` che `gzip -t` dichiara
integro, e dopo otto giorni la cartella `daily/` ne contiene sette, non otto.

### 2.6 Checklist deploy — tutte azioni sul VPS, nessuna nel repo

- [ ] VPS creato e SSH configurato
- [ ] Dominio acquistato, DNS configurato
- [ ] `.env.production` creato **nella radice del repo sul VPS** con i secret veri: è lì che il file
      di composizione lo cerca (`env_file: ../.env.production`, relativo a `docker/`)
- [ ] `SESSION_SECRET` e `ENCRYPTION_SALT` generati (`openssl rand -hex 32`)
- [ ] `POSTGRES_PASSWORD` valorizzato: senza, l'indirizzo del database si compone monco e il backend
      non si collega
- [ ] Spotify Developer Dashboard: aggiungere redirect URI produzione (`https://tuodominio.it/auth/spotify/callback`)
- [ ] Correzioni dei punti 2.2 e 2.3 applicate: riavvio automatico su Postgres e Redis, servizio
      Caddy scommentato col percorso giusto, porte 8001 e 5173 tolte dall'host
- [ ] `docker compose -f docker/docker-compose.prod.yml up --build -d`
- [ ] Verificare: `curl https://tuodominio.it/health` → 200
- [ ] Primo login come admin → verificare onboarding
- [ ] Generare inviti dalla pagina Admin

---

## Step 3: Spotify Extended Quota (opzionale per >5 utenti)

### Contesto

In dev mode Spotify limita a **25 utenti registrati** nella Developer Dashboard (di cui solo quelli aggiunti manualmente possono loggarsi). Con Extended Quota il limite viene rimosso.

### Requisiti per la submission

1. **App description**: spiegare cosa fa l'app, quali dati usa, perché
2. **Screenshot**: almeno 3-5 screenshot dell'app funzionante (Dashboard, Artist Network, Wrapped)
3. **Privacy Policy URL**: deve essere raggiungibile (`https://tuodominio.it/privacy`)
4. **Redirect URI produzione**: `https://tuodominio.it/auth/spotify/callback`
5. **Scopes richiesti**: `user-read-private`, `user-read-email`, `user-top-read`, `user-read-recently-played`, `playlist-read-private`, `playlist-read-collaborative`

### Procedura

1. Andare su [developer.spotify.com](https://developer.spotify.com) → App → Settings
2. Compilare tutti i campi richiesti
3. Submit per review
4. **Tempo di attesa**: 2-6 settimane (variabile)
5. Una volta approvato: rimuovere whitelist manuale, chiunque con il link invito può registrarsi

### Nota

Per il primo lancio tra amici (≤5 persone), Extended Quota NON serve. Basta aggiungere manualmente gli account Spotify degli amici nella Developer Dashboard. Extended Quota serve solo per scalare oltre.

---

## Step 4: Launch Day

### Checklist pre-lancio (giorno prima)

- [ ] App funzionante su VPS (`/health` → OK, `/health/detailed` → tutto verde)
- [ ] Testare login completo con il proprio account
- [ ] Testare onboarding flow
- [ ] Verificare che i dati appaiano dopo ~1 ora (sync background)
- [ ] Generare N inviti dalla pagina Admin
- [ ] Preparare messaggio con link invito

### Messaggi da inviare agli amici

**Messaggio tipo:**
> Ho creato un'app che analizza i tuoi ascolti Spotify — ti mostra pattern, evoluzione del gusto, ecosistema artisti e un "Wrapped" personalizzato.
>
> Per provarla:
> 1. Vai su https://tuodominio.it/login?invite=CODICE
> 2. Logga con Spotify (serve Premium)
> 3. I dati completi arrivano nelle prossime ore — intanto puoi esplorare
>
> Feedback benvenuto!

### Nota su dev mode

Se non hai Extended Quota, devi aggiungere **manualmente** l'email Spotify di ogni amico nella Developer Dashboard:
1. [developer.spotify.com](https://developer.spotify.com) → App → Settings → User Management
2. Aggiungere nome + email dell'account Spotify
3. Solo dopo l'amico potrà completare il login

### Monitoraggio post-lancio

- `/health/detailed` — stato generale (DB, Redis, jobs, Spotify reachability)
- Admin page → tab "Utilizzo API" — verificare che nessun utente monopolizzi il budget
- Admin page → tab "Jobs" — verificare che `sync_recent_plays` giri regolarmente
- Logs: `docker logs backend --tail 100 -f` — cercare 429, 500, errori auth
- Backup: verificare che il cron giri (`ls -la /backups/daily/`) e che l'ultima copia si rilegga
  (`gzip -t /backups/daily/spotify_*.sql.gz`)

### Primi giorni

- **Giorno 1**: i grafici saranno parziali (pochi dati storici). Spiegare agli amici che i dati si arricchiscono col tempo.
- **Giorno 2-3**: `sync_recent_plays` avrà accumulato ~48-72 ascolti per utente. Le heatmap e i trend inizieranno a popolarsi.
- **Settimana 1**: snapshot giornalieri permettono confronti temporali nella TasteEvolution.
- **Mese 1**: dati sufficienti per un Wrapped personalizzato significativo.

---

## Costi stimati

| Voce | Costo |
|------|-------|
| Hetzner CX22 | ~5€/mese |
| Dominio | ~10€/anno |
| **Totale** | **~6€/mese** |

Redis e PostgreSQL girano nello stesso VPS (Docker). Nessun servizio esterno a pagamento (Sentry saltato per la beta).

---

## Cose esplicitamente rinviate (non servono per la beta)

| Cosa | Motivo | Quando |
|------|--------|--------|
| Sentry (error tracking) | Costo, bassa utilità con 5 utenti — i log bastano | Post-beta se serve |
| i18n (internazionalizzazione) | Solo utenti italiani in beta, ROI zero | Se si apre a utenti non-IT |
| Job runner abstraction | APScheduler funziona per 5-20 utenti | Se si passa a multi-worker |
| Monetizzazione (tiers premium) | Infrastruttura pronta (User.tier), ma tutti "free" in beta | Post Extended Quota |
