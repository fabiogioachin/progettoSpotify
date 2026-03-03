# Guida Setup Spotify Developer App

## Prerequisiti
- Un account Spotify (gratuito o Premium)
- Un browser web

## Passi

1. Vai su [Spotify Developer Dashboard](https://developer.spotify.com/dashboard)
2. Accedi con il tuo account Spotify (o creane uno se non ce l'hai)
3. Clicca **"Create App"**
4. Compila i campi:
   - **App name**: `Listening Intelligence` (o il nome che preferisci)
   - **App description**: `Dashboard analisi musicale personale`
   - **Redirect URI**: `http://127.0.0.1:8001/auth/spotify/callback`
   - Seleziona **"Web API"** come API da usare
5. Clicca **"Save"**
6. Nella pagina dell'app, vai su **"Settings"**
7. Copia **Client ID** e **Client Secret**
8. Nella root del progetto, copia `.env.example` in `.env`:
   ```bash
   cp .env.example .env
   ```
9. Apri `.env` e incolla i valori di Client ID e Client Secret
10. Genera un session secret sicuro:
    ```bash
    # Linux/Mac:
    openssl rand -hex 32
    # Windows (PowerShell):
    python -c "import secrets; print(secrets.token_hex(32))"
    ```
    e incollalo come valore di `SESSION_SECRET`

## Note Importanti

- Finche' l'app e' in **"Development Mode"**, solo il tuo account Spotify puo' autenticarsi
- Per aggiungere altri utenti, vai su **"User Management"** nel dashboard Spotify e aggiungi le loro email Spotify
- Il redirect URI deve corrispondere ESATTAMENTE a quello configurato nel `.env`
- Non condividere mai il Client Secret pubblicamente
