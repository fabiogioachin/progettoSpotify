# Prompt: Test Autonomi — Spotify Listening Intelligence

## Obiettivo
Esegui una batteria di test autonomi sull'app (FastAPI + React + Docker) e produci
un report pass/fail per ogni check. NON modificare codice. Segnala solo i problemi trovati.

---

## Contesto architetturale
- **Backend**: FastAPI su `http://127.0.0.1:8001`, SQLite, APScheduler
- **Frontend**: nginx su `http://127.0.0.1:5173`, proxy `/auth` e `/api` → backend
- **Auth**: OAuth2 PKCE, HMAC-signed state, cookie di sessione (itsdangerous)
- **DB**: `./data/spotify_intelligence.db`
- **Env**: `.env` nella root — NON loggare i valori segreti

---

## Suite di test

### 1. Infrastructure (Docker)
```bash
docker compose ps
```
- [ ] `backend` UP e healthy
- [ ] `frontend` UP
- Verifica che le porte 8001 e 5173 siano in ascolto

### 2. Backend health
```bash
curl -s http://127.0.0.1:8001/health | python -m json.tool
```
- [ ] `status: ok`
- [ ] `database: ok`

### 3. Static analysis backend
```bash
cd backend
ruff check . --statistics 2>&1 | tail -20
python -m compileall app/ -q 2>&1
```
- [ ] Nessun errore ruff (warning accettabili)
- [ ] Nessun errore di compilazione Python

### 4. Import check backend
```bash
cd backend
python -c "from app.main import app; print('OK')" 2>&1
```
- [ ] App FastAPI importabile senza errori

### 5. Schema e modelli DB
```bash
cd backend
python -c "
from app.models.user import User, SpotifyToken
from app.models.listening_history import RecentPlay, UserSnapshot, ListeningSnapshot
print('Models OK')
" 2>&1
```
- [ ] Tutti i modelli importabili

### 6. API endpoints — risposta senza auth
Testa che gli endpoint restituiscano 401 (non 500) quando non autenticati:
```bash
for endpoint in /api/library/top /api/analytics/discovery /api/analytics/features \
  /api/temporal /api/artist-network /api/playlists /api/playlist-analytics \
  /api/taste-evolution; do
  status=$(curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:8001$endpoint)
  echo "$endpoint → $status"
done
```
- [ ] Tutti restituiscono `401` (non `500`, non `422`)

### 7. Auth/me senza cookie
```bash
curl -s http://127.0.0.1:8001/auth/me | python -m json.tool
```
- [ ] `{"authenticated": false}` con HTTP 200

### 8. Login redirect
```bash
curl -s -o /dev/null -w "%{http_code} %{redirect_url}" http://127.0.0.1:8001/auth/spotify/login
```
- [ ] HTTP 307
- [ ] URL di redirect contiene `accounts.spotify.com`
- [ ] URL contiene parametri: `client_id`, `redirect_uri`, `state`, `scope`

### 9. State HMAC integrity
Estrai il `state` dall'URL di redirect e verifica il formato `nonce.signature`:
```bash
state=$(curl -s -o /dev/null -w "%{redirect_url}" http://127.0.0.1:8001/auth/spotify/login \
  | grep -oP 'state=[^&]+' | cut -d= -f2)
echo "State: $state"
echo "$state" | grep -P '^[A-Za-z0-9_-]+\.[a-f0-9]{16}$' && echo "HMAC format OK" || echo "HMAC format FAIL"
```
- [ ] State ha formato `nonce.16hex`

### 10. Callback con state invalido
```bash
curl -s -o /dev/null -w "%{redirect_url}" \
  "http://127.0.0.1:8001/auth/spotify/callback?code=fake&state=invalid"
```
- [ ] Redirect a frontend con `?error=state_mismatch`

### 11. Callback con state valido ma code fake
```bash
state=$(curl -s -o /dev/null -w "%{redirect_url}" http://127.0.0.1:8001/auth/spotify/login \
  | grep -oP 'state=[^&]+' | cut -d= -f2)
curl -s -o /dev/null -w "%{redirect_url}" \
  "http://127.0.0.1:8001/auth/spotify/callback?code=fakecode&state=$state"
```
- [ ] Redirect a frontend con `?error=token_exchange_failed` (non `state_mismatch`)
- Questo conferma che HMAC è valido ma Spotify rifiuta il code

### 12. Rate limit endpoint
```bash
curl -s -w "\nHTTP: %{http_code}" http://127.0.0.1:8001/api/library/top
```
- [ ] HTTP 401 (non 429, non 500) — il rate limiter non deve bloccare richieste normali

### 13. Frontend statico
```bash
curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:5173/
```
- [ ] HTTP 200

### 14. Frontend proxy → backend
```bash
curl -s http://127.0.0.1:5173/auth/me
```
- [ ] `{"authenticated": false}` — nginx proxy funzionante

### 15. DB check (se esiste)
```bash
python -c "
import sqlite3, os
db = './data/spotify_intelligence.db'
if not os.path.exists(db):
    print('DB non trovato — atteso dopo il primo login')
else:
    conn = sqlite3.connect(db)
    tables = conn.execute(\"SELECT name FROM sqlite_master WHERE type='table'\").fetchall()
    print('Tabelle:', [t[0] for t in tables])
    conn.close()
"
```
- [ ] Se esiste: tabelle `users`, `spotify_tokens`, `recent_plays`, `user_snapshots`

### 16. Configurazione .env
```bash
python -c "
import os
required = ['SPOTIFY_CLIENT_ID','SPOTIFY_CLIENT_SECRET','SPOTIFY_REDIRECT_URI','SESSION_SECRET','ENCRYPTION_SALT']
missing = [k for k in required if not os.getenv(k)]
print('Missing:', missing if missing else 'nessuno')
for k in required:
    v = os.getenv(k, '')
    print(f'{k}: {\"SET (\" + str(len(v)) + \" chars)\" if v else \"MISSING\"}'  )
" 2>&1
```
Esegui dentro il container backend:
```bash
docker compose exec backend python -c "
import os
required = ['SPOTIFY_CLIENT_ID','SPOTIFY_CLIENT_SECRET','SPOTIFY_REDIRECT_URI','SESSION_SECRET','ENCRYPTION_SALT']
for k in required:
    v = os.getenv(k,'')
    print(f'{k}: {\"OK (\" + str(len(v)) + \" chars)\" if v else \"MISSING\"}'  )
"
```
- [ ] Tutte le variabili SET
- [ ] SPOTIFY_REDIRECT_URI = `http://127.0.0.1:5173/auth/spotify/callback`

### 17. Log backend — errori recenti
```bash
docker compose logs backend --tail=30 2>&1 | grep -iE "error|exception|traceback|critical" | head -20
```
- [ ] Nessun errore critico nei log recenti
- Eccezioni accettabili: `SpotifyAuthError` (atteso per richieste non auth)

---

## Report finale

Produci una tabella:
```
| Check | Status | Note |
|-------|--------|------|
| 1. Docker up | ✅/❌ | ... |
...
```

Se ci sono ❌: fornisci diagnosi e comando di fix per ognuno.

---

## Anti-pattern — NON fare
- Non eseguire login Spotify (richiede browser)
- Non modificare `.env`
- Non riavviare i container a meno di errori critici
- Non committare nulla
- Non fare chiamate dirette a `api.spotify.com`
