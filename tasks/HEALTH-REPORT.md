# Root Cause Analysis: Confronto Playlist — Dati Vuoti

Generated: 2026-03-11

## Diagnosi

### Il Problema
La pagina **Confronto Playlist** (`PlaylistComparePage`) mostra dati vuoti perché dipende interamente dalle **Audio Features API di Spotify**, che sono **deprecate** e restituiscono errori 403.

### Flusso del Bug

```
PlaylistComparePage
  → usePlaylistCompare hook
    → GET /api/playlists/compare?ids=id1,id2
      → playlists.py:compare_playlists()
        → get_or_fetch_features(db, client, track_ids)
          → client.get_audio_features(batch)   ← API DEPRECATA → 403
          → except Exception: logger.warning()  ← errore ingoiato silenziosamente
        → features = {}
        → analyzed_count = 0, averages = {}
      → Response: tutte le playlist con analyzed_count = 0
  → Frontend: hasFeatures = false
    → nasconde colonne Energia/Positività/Ballabilità
    → nasconde AudioRadar + PlaylistComparison charts
    → mostra solo "Profili audio non disponibili"
```

### File Coinvolti

| File | Ruolo | Problema |
|------|-------|----------|
| `backend/app/routers/playlists.py` | Router compare | Dipende solo da audio features |
| `backend/app/services/audio_analyzer.py:208-269` | `get_or_fetch_features()` | Chiama API deprecata, errore silente |
| `backend/app/services/spotify_client.py:151-153` | `get_audio_features()` | Wrapper per endpoint deprecato |
| `backend/app/schemas.py:82-90` | Schema risposta | Manca di campi alternativi |
| `frontend/src/pages/PlaylistComparePage.jsx` | UI confronto | Senza audio features = pagina vuota |
| `frontend/src/hooks/usePlaylistCompare.js` | Hook fetch | OK (nessun problema) |

### Nota: PlaylistAnalyticsPage è OK
La pagina **Analisi Playlist** (`PlaylistAnalyticsPage`) **non usa audio features** — lavora solo con metadati (conteggio tracce, artisti, overlap Jaccard, date). Non è affetta da questo bug.

---

## Piano di Fix

### Step 1 — Backend: arricchire `/api/playlists/compare` con dati sempre disponibili

**File: `backend/app/routers/playlists.py`**

Per ogni playlist, calcolare dati che **non dipendono da API deprecate**:

- **`popularity_stats`**: `{ avg, min, max }` da `track.popularity` (sempre disponibile)
- **`genre_distribution`**: top 10 generi (fetch dettagli artisti → conteggio generi) — riusare il pattern di `audio_analyzer._extract_genres()`
- **`top_tracks`**: top 5 tracce per popolarità `[{ name, artist, popularity }]`
- **`playlist_name`**: includere il nome dalla metadata (ora restituisce solo `playlist_id`)

Mantenere audio features come **bonus opzionale** (se già cachate nel DB, includerle; non chiamare l'API deprecata per nuovi fetch).

**File: `backend/app/schemas.py`** — aggiornare schema:

```python
class PlaylistComparisonItem(BaseModel):
    playlist_id: str
    playlist_name: str                    # NUOVO
    track_count: int
    analyzed_count: int                   # mantenuto per compat
    averages: dict[str, float]            # audio features (può essere vuoto)
    popularity_stats: dict[str, float]    # NUOVO: avg/min/max
    genre_distribution: dict[str, float]  # NUOVO: genere → percentuale
    top_tracks: list[dict]                # NUOVO: [{name, artist, popularity}]
```

### Step 2 — Backend: fetch nome playlist

Nella funzione `compare_playlists`, per ogni playlist:
- Chiamare `GET /playlists/{id}` (endpoint non deprecato) per ottenere nome e immagine
- Oppure: il frontend ha già i nomi in `playlistNames` — si possono passare come parametro

Approccio migliore: fetch nel backend con `client.get_playlist(pid)` — nessuna API deprecata, aggiunge solo 1 chiamata per playlist.

### Step 3 — Frontend: UI che funziona sempre

**File: `frontend/src/pages/PlaylistComparePage.jsx`**

Sostituire la UI audio-features-only con un confronto più ricco:

1. **Tabella riepilogo** — sempre visibile: nome playlist, n° brani, popolarità media, genere top
2. **Confronto popolarità** — bar chart che compara la popolarità media (sempre disponibile, usa Recharts già importato in altre pagine)
3. **Confronto generi** — distribuzione generi per playlist (tag/barre)
4. **Top tracks per playlist** — mini lista tracce con badge popolarità
5. **Audio radar** — mantenere `AudioRadar` + `PlaylistComparison` esistenti, mostrati solo se `hasFeatures` (nessuna modifica necessaria qui)

### Step 4 — Verifica

```bash
cd backend && ruff check app/ && pytest
cd frontend && npm run lint && npm run build
```

Test manuale: selezionare 2+ playlist → Confronta → verificare che popolarità, generi e top tracks si renderizzino anche senza audio features.

---

## Effort Stimato

| Step | Complessità | File modificati |
|------|-------------|-----------------|
| Step 1 | Media | `playlists.py`, `schemas.py` |
| Step 2 | Bassa | `playlists.py` o `spotify_client.py` |
| Step 3 | Media-Alta | `PlaylistComparePage.jsx` + eventuali nuovi componenti chart |
| Step 4 | Bassa | Nessun file — solo verifica |

## Comando per Procedere

```
Implementa il piano descritto in HEALTH-REPORT.md per fixare il confronto playlist con dati vuoti
```
