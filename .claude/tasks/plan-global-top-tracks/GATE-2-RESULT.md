# Seconda scoperta: anche `popularity` è sparita dalla dev mode

Data: 2026-09-03, durante l'implementazione dell'Opzione D. Sonde dirette con l'utente reale.

## Esito in una riga

L'Opzione D **non può funzionare con la fonte che le era stata assegnata**: Spotify in dev mode non
restituisce più il campo `popularity`, da nessun endpoint. Non è `null`, è **assente dalla
risposta**.

## Evidenza

`GET /tracks/4hFDFmMnSYZ32ssqNUOCjt` — chiavi restituite:

```
album, artists, disc_number, duration_ms, explicit, external_ids, external_urls,
href, id, is_local, is_playable, name, track_number, type, uri
```

Nessun `popularity`. Idem per `/me/player/recently-played` e `/me/top/tracks`: `popularity` non
compare fra le chiavi dei brani.

Conferma dal database: la tabella `track_popularity` ha **0 righe**, a fronte di **469 brani
distinti** in `recent_plays`. Il giro orario che dovrebbe riempirla
([background_tasks.py:285-315](../../../backend/app/services/background_tasks.py)) legge
`track.get("popularity")` dalla risposta di `recently-played` e trova sempre `None`, quindi salta
ogni riga. Gira da mesi e non ha mai scritto nulla: il difetto era invisibile perché nessuna card
lo mostrava.

## Va corretta la documentazione di progetto

`.claude/CLAUDE.md`, § Spotify API Constraints, dichiara oggi:

> «**Always available**: popularity, genres, track/artist metadata, user profile»

Per `popularity` **non è più vero**. (Per `genres` era già noto che la dev mode torna vuoto, ed è
scritto altrove nello stesso file.)

## Conseguenza sul lavoro

Sopravvive una sola fonte: **Last.fm**. Diventa il motore di entrambe le card, che restano due cose
diverse:

- **Card D** — i brani *dell'utente*, ordinati per quanto il mondo li ascolta. La misura non è più
  la popolarità Spotify ma il `playcount` mondiale di Last.fm. Il significato della card non cambia,
  cambia il righello. Continua a seguire il selettore di periodo.
- **Card C** — la classifica mondiale vera, `chart.getTopTracks`. Non segue il periodo, e lo dichiara.
