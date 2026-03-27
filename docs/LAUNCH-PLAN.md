# Launch Plan — Beta tra Amici

## Obiettivo

Primo lancio dell'app tra 5-20 amici con account Spotify Premium. L'app è funzionante in locale — servono: bug fix, polish UI, deploy su VPS, e (opzionale) Extended Quota per superare il limite di 5 utenti dev mode.

---

## Pre-requisiti completati

- [x] PostgreSQL + Redis (Docker Compose)
- [x] Auth invite-gated con PKCE + HMAC state
- [x] Rate limit 4 livelli (API, user quota, Spotify throttle, budget priority)
- [x] PWA installabile
- [x] Empty states + error boundaries
- [x] Admin dashboard
- [x] Onboarding flow
- [x] Privacy/GDPR (export + delete)
- [x] Structured logging + health endpoints
- [x] API v1 versioning con redirect 308
- [x] Data retention policy
- [x] Background jobs staggerati multi-user

---

## Step 2: Deploy Pipeline (ex Phase 6)

### 2.1 VPS Setup

- **Provider**: Hetzner CX22 (~5€/mese) — 2 vCPU, 4GB RAM, 40GB SSD
- **OS**: Ubuntu 24.04 LTS
- **Dominio**: acquistare dominio (es. `tuodominio.it`, ~10€/anno)
- **DNS**: A record → IP del VPS

### 2.2 Docker Compose Production

Creare `docker/docker-compose.prod.yml`:

```yaml
services:
  postgres:
    image: postgres:16-alpine
    volumes: [postgres_data:/var/lib/postgresql/data]
    environment: [POSTGRES_DB, POSTGRES_USER, POSTGRES_PASSWORD]
    healthcheck: ...
    restart: unless-stopped

  redis:
    image: redis:7-alpine
    volumes: [redis_data:/data]
    healthcheck: ...
    restart: unless-stopped

  backend:
    build: {context: .., dockerfile: docker/backend.Dockerfile}
    environment: [DATABASE_URL, REDIS_URL, SESSION_SECRET, ...]
    depends_on: [postgres: healthy, redis: healthy]
    restart: unless-stopped

  frontend:
    build: {context: .., dockerfile: docker/frontend.Dockerfile}
    restart: unless-stopped

  caddy:
    image: caddy:2-alpine
    ports: ["80:80", "443:443"]
    volumes: [./caddy/Caddyfile:/etc/caddy/Caddyfile, caddy_data:/data]
    depends_on: [backend, frontend]
    restart: unless-stopped
```

### 2.3 Caddy (HTTPS automatico)

`docker/caddy/Caddyfile`:
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
        reverse_proxy frontend:5173
    }
}
```

### 2.4 CI/CD (GitHub Actions)

```yaml
# .github/workflows/deploy.yml
on:
  push:
    branches: [master]

jobs:
  lint-test-build:
    runs-on: ubuntu-latest
    steps:
      - Backend: ruff check + pytest
      - Frontend: eslint + vite build
  deploy:
    needs: lint-test-build
    runs-on: ubuntu-latest
    steps:
      - SSH into VPS
      - git pull
      - docker compose -f docker/docker-compose.prod.yml up --build -d
      - Health check: curl https://tuodominio.it/health
```

### 2.5 Backup PostgreSQL

Cron job sul VPS:
```bash
# /etc/cron.d/pg-backup
0 4 * * * docker exec postgres pg_dump -U spotify spotify | gzip > /backups/spotify_$(date +\%Y\%m\%d).sql.gz
# Rotazione: 7 daily + 4 weekly
```

### 2.6 Checklist deploy

- [ ] VPS creato e SSH configurato
- [ ] Dominio acquistato, DNS configurato
- [ ] `.env.production` creato sul VPS con secrets reali
- [ ] `SESSION_SECRET` e `ENCRYPTION_SALT` generati (`openssl rand -hex 32`)
- [ ] Spotify Developer Dashboard: aggiungere redirect URI produzione (`https://tuodominio.it/auth/spotify/callback`)
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
- Backup: verificare che il cron `pg_dump` giri (`ls -la /backups/`)

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
