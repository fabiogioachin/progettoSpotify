# Step 1 — verifica preliminare dell'ID playlist: **FALLITA**

Data: 2026-09-03. Eseguita con l'utente reale registrato (`user_id=1`, account `IT`, `premium`),
token valido, chiamate dirette all'API Spotify dal container `wrap-backend-1`.

## Esito in una riga

L'Opzione A non è realizzabile: **in dev mode Spotify nasconde tutte le playlist editoriali**, non
solo quella che il piano aveva scelto. Non è un ID sbagliato da correggere, è una porta chiusa.

## Cosa dicono le chiamate

| Chiamata | Esito |
|---|---|
| `GET /me` | **OK** — token valido, account `IT`/`premium`. La sonda è sana |
| `GET /playlists/{playlist dell'utente}/items` | **OK** — 83 brani. L'endpoint funziona |
| `GET /playlists/{playlist di un altro utente}/items` | **403 Forbidden** |
| `GET /playlists/37i9dQZEVXbMDoHDwVN2tF` (Top 50 - Global), meta e `/items` | **404 Not Found** |
| idem con `market=US` esplicito | **404 Not Found** |
| Top 50 - Italy, Viral 50 - Global, Today's Top Hits (meta e `/items`) | **404 Not Found**, tutte |
| `GET /search?q=Top 50 Global&type=playlist` | OK, ma **3 risultati su 5 tornano `null`**: sono le voci editoriali, che l'API svuota invece di restituirle |
| fetch del primo risultato non-null (playlist pubblica di terzi) | **403 Forbidden** |

Le playlist di proprietà di Spotify rispondono `404`, quelle pubbliche di altri utenti `403`.
**Leggibili restano solo le playlist dell'utente stesso.** Nessun parametro, nessun mercato e
nessun ID alternativo aggira la cosa: è la restrizione dev-mode di Spotify, coerente con le altre
già registrate in `CLAUDE.md` § Spotify API Constraints.

Il piano lo aveva previsto come rischio portante ed è quello che si è avverato:
> «Se questa chiamata di prova fallisce, il piano non parte e la scelta A/B va riaperta.»

## Cosa questo NON invalida

Il resto del piano (cache condivisa, lock Redis, refresh opportunistico, card nascosta quando
vuota, revisione del copy) resta valido come impianto: cambia solo **da dove arriva il dato**.

## Nota emersa durante la verifica

Il progetto ha già un ponte verso una fonte esterna — `backend/app/services/rapidapi_bridge.py`,
usato come ripiego per le audio features — quindi l'Opzione C non sarebbe più "fuori da ogni
pattern del progetto" come il piano assumeva. Però **la chiave RapidAPI oggi non è configurata**
(`settings.rapidapi_key` vuota): servirebbe un gesto umano per ottenerla.
