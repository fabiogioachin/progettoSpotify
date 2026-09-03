# Card "I brani più ascoltati" — piano finale

Piano prodotto da `/plan-hardened`. Solo pianificazione: nessun codice scritto, nessun file del progetto modificato.

**Revisione**: revisione fatta da Gemini+Opus (quest'ultimo interno, solo ripiego). Non disponibili: Codex (limite d'uso raggiunto fino al 10/09/2026, verificato con sonda fresca il 02/09). Cinque giri di revisione iterativa, 27 rilievi, tutti accolti — cronologia in `PLAN-REVIEW-LOG.md`, nessun rilievo respinto (`REJECTED-SUGGESTIONS.md`), diff rispetto alla bozza in `CHANGES-FROM-DRAFT.md`.

**Decisione presa dall'utente il 03/09/2026: Opzione A** — la card mostra la classifica globale vera di Spotify. Le alternative valutate e scartate sono in coda a questo documento.

---

## Obiettivo

Aggiungere nella Dashboard una card "I brani più ascoltati", identica per stile a "I tuoi brani più ascoltati" e affiancata ad essa, che mostri la **classifica globale di Spotify** — la playlist editoriale pubblica "Top 50 - Global".

## La conseguenza principale della scelta, da accettare prima di partire

**La card non seguirà il selettore di periodo della dashboard**, e deve dirlo in UI.

La richiesta originale chiedeva la classifica mondiale *nell'arco temporale definito nella dashboard*. I due vincoli non sono soddisfacibili insieme: Spotify pubblica quella playlist aggiornata quotidianamente e non espone finestre storiche — non esiste un "Top 50 Global di 90 giorni fa" da interrogare. Scegliendo la classifica mondiale vera si rinuncia necessariamente al periodo.

Non è una scorciatoia inventata qui: è esattamente il conflitto che il progetto ha già risolto una volta, nella sezione "Top 50 secondo Spotify" ([DashboardPage.jsx:311-345](../../../frontend/src/pages/DashboardPage.jsx)), che ha un proprio selettore disaccoppiato e dichiara in UI perché non segue quello in cima alla pagina. La card nuova fa lo stesso, dichiarando "aggiornata al [data]".

## ⚠️ Primo step, prima di scrivere qualsiasi codice

Tutta l'Opzione A poggia su un'assunzione **mai verificata**: che l'ID `37i9dQZEVXbMDoHDwVN2tF` ("Top 50 - Global") sia valido e raggiungibile in dev mode. Spotify non ne garantisce contrattualmente la stabilità, e ha già rimosso endpoint dalla dev mode senza preavviso (vedi `CLAUDE.md`, § Spotify API Constraints).

**Se questa chiamata di prova fallisce, il piano non parte** e la scelta A/B va riaperta. Va eseguita per prima, non a implementazione avviata.

---

## Step di implementazione

1. **Verifica preliminare dell'ID playlist.** Chiamata di prova a `get_playlist_items("37i9dQZEVXbMDoHDwVN2tF")` con un utente autenticato reale. Confermare due cose: che l'ID risponda, e se la risposta include già le copertine (`album.images`) per ogni brano — da cui dipende se le immagini si leggono direttamente dalla risposta o dalla cache DB. **Da ripetere con `market` esplicito** dopo lo step 3: un ID raggiungibile senza `market` non garantisce lo stesso comportamento una volta vincolato a un mercato.

2. **Nuovo servizio** `backend/app/services/global_chart_cache.py`, stesso pattern architetturale di `genre_cache.py`: legge da tabella DB con TTL (12-24h, il chart si aggiorna al più quotidianamente), fallback a Spotify con `retry_with_backoff` solo su cache miss, **mai una chiave di cache per-utente** — il dato è identico per tutti gli utenti, e la skill `spotify-api-budget` impone la cache condivisa per i dati indipendenti dall'utente. Deve inoltre:
   - **scartare gli item con `track` assente/null** (brani rimossi dal catalogo, o elementi non-track) prima di costruire la risposta, altrimenti producono nome/artista `None` o un errore di parsing;
   - se la cache è scaduta ma il refresh fallisce, **continuare a servire l'ultimo payload valido** col suo `updated_at` originale, invece di propagare l'errore o svuotare la card.

3. **Estendere `SpotifyClient.get_playlist_items`** con un parametro `market` (oggi non esiste — verificato in [spotify_client.py:674-686](../../../backend/app/services/spotify_client.py)), da includere anche nella chiave di cache per-utente esistente del metodo, altrimenti risposte di mercati diversi collidono nella stessa chiave. Serve perché la chiamata usa il token di un utente qualsiasi: senza `market` esplicito Spotify applica il paese di quell'utente, e la cache condivisa finirebbe a contenere un relinking valido per un solo paese. Usare un valore fisso e deterministico (es. `US`, coerente con una playlist "Global").

4. **Migrazione Alembic** per la tabella di cache.

5. **Nuovo endpoint** `GET /api/v1/library/top-global` in `library.py`: nessun parametro `range`, risposta con `updated_at` e `source` (pattern `*_source` già in uso, invariante 5).

6. **Aggiornamento della cache — opportunistico, senza nuovi job.** Il refresh si aggancia al job `sync_recent_plays` già esistente (gira per ogni utente ogni ora): quando gira per un utente, se la cache globale è scaduta la rinfresca col token di quell'utente — esattamente come già avviene per il warmup dei generi. Niente job APScheduler dedicato: ne servirebbe uno solo per questa card, e comunque un job isolato non avrebbe un token da usare, perché il progetto non ha un flusso client-credentials.
   - **Limite dichiarato, non risolto**: questo elimina il punto singolo di rottura solo *quando ci saranno più utenti*. Con l'unico utente registrato oggi, se quell'account perde l'accesso a Spotify nessun altro rinfresca la cache. Non è "risolto", è "auto-risolvente in futuro". Per rendere visibile uno stallo, aggiungere il campo `global_chart_cache_age_hours` a `GET /health/detailed`, che già riporta job e raggiungibilità di Spotify.
   - **Primo popolamento**: senza un trigger d'avvio la card resterebbe invisibile per un'ora dopo il deploy. Fallback dentro l'endpoint stesso: se non esiste ancora nessuna riga di cache, la richiesta prova ad acquisire il lock (step 7). **Nessuna delle due richieste attende Spotify dentro il ciclo richiesta/risposta**: chi non prende il lock ritorna subito senza dati; chi lo prende lancia la fetch come task in background e ritorna anch'esso subito. Il primo caricamento dopo il deploy non mostra la card, quello successivo — secondi dopo, non ore — sì.
   - 🔴 **Il task in background deve costruire un proprio `SpotifyClient` con una propria sessione DB**, mai catturare per closure quello dell'handler. Quel client viene chiuso nel `finally` non appena l'handler ritorna, che qui accade subito per design. Un task che riusasse il client del genitore fallirebbe **in silenzio** — nessuno lo attende — e il difetto resterebbe invisibile, perché il refresh orario popola comunque la cache più tardi. (Invariante 4 di `CLAUDE.md` per la sessione DB; il client è la metà che l'invariante non nomina.)

7. **Lock condiviso (Redis `SET NX`)** attorno al refresh, per impedire che più utenti in finestre vicine — o la prima richiesta lazy — scatenino fetch duplicate verso Spotify.
   - **TTL con margine ampio** sopra il caso peggiore reale di `retry_with_backoff` (indicativamente 90-120s), oppure rinnovato a ogni tentativo: un TTL troppo corto scade a fetch in corso e riapre proprio lo stampede che il lock doveva chiudere.
   - **Fail-closed su Redis irraggiungibile**, a differenza del rate limiter esistente che è fail-open per policy dichiarata: qui un fail-open silenzioso riaprirebbe lo stampede. Il refresh salta il ciclo corrente (riprova il prossimo utente del giro orario), mentre l'endpoint continua comunque a servire l'ultimo payload valido.

8. **Frontend** — `frontend/src/pages/DashboardPage.jsx`:
   - la card usa lo stesso markup di quella esistente (`glow-card bg-surface rounded-xl p-5`, `<h3>`, `<p>` di sottotitolo, `TrackCard` dentro `StaggerContainer`/`StaggerItem`), dentro `SectionErrorBoundary` con il suo `sectionName`;
   - **non passa `range`** alla chiamata dati, e il sottotitolo dichiara "Classifica globale di Spotify, aggiornata al [data]";
   - **card vuota = card nascosta**, mai un messaggio di "nessun dato" (convenzione di progetto);
   - `TrackCard.jsx` non richiede modifiche: è già generico e gestisce l'assenza di copertina, `play_count` e `features`.

9. **Layout.** La card personale vive oggi in una griglia a 2 colonne insieme ad `AudioRadar` ([DashboardPage.jsx:256](../../../frontend/src/pages/DashboardPage.jsx)). Proposta: griglia a 3 colonne su schermi larghi, ordine `AudioRadar | I tuoi brani più ascoltati | I brani più ascoltati`, senza spostare `AudioRadar` altrove. **Il numero di colonne va calcolato in base a quante card hanno davvero dati**, non fissato in una classe CSS: la card nuova può essere legittimamente assente a lungo (ogni deploy, ogni stallo del refresh), e una griglia rigida lascerebbe una colonna vuota visibile.

10. **Revisione del copy delle tre sezioni.** Con la card nuova la Dashboard avrà *tre* classifiche, e due si richiamano entrambe a Spotify con scope opposto: la nuova (mondiale, editoriale) e "Top 50 secondo Spotify" (che è **personale** per quell'utente, calcolata dal suo algoritmo — [DashboardPage.jsx:65-67](../../../frontend/src/pages/DashboardPage.jsx)). I nomi sono simili e il rischio di confusione è concreto: differenziare i sottotitoli esplicitamente, eventualmente ritoccando anche quello della sezione esistente per chiarire che è personale.

11. **Test** — `backend/tests/test_top_global.py` (nuovo): cache hit/miss; nessuna chiamata Spotify a cache calda; ID irraggiungibile al primo utilizzo (card nascosta) *e* con cache già popolata (si continua a servire il dato vecchio, non si nasconde); item `track: null` scartati; due richieste lazy concorrenti (una sola prende il lock, nessuna attende Spotify); **fetch in background che completa dopo che la risposta HTTP è già partita**, con un client distinto da quello dell'handler; fail-closed quando Redis non risponde.

---

## Trade-off accettati esplicitamente

- **La card non segue il periodo della dashboard.** Conseguenza diretta della scelta A, non un compromesso implementativo — vedi in cima.
- **Nessun tetto massimo di staleness**: se il refresh fallisce sistematicamente la card può mostrare un dato vecchio anche per settimane, invece di tornare a nascondersi. Mitigato solo dal timestamp "aggiornato al …" visibile in UI e dal campo in `/health/detailed`. Se in futuro serve un tetto, va aggiunto come soglia esplicita.
- **Il primo caricamento dopo un deploy non mostra la card**: conseguenza voluta del non bloccare la richiesta sulla chiamata Spotify.
- **La classifica non è calcolata sugli ascolti di nessuno.** È una playlist editoriale di Spotify. Il progetto ha già deciso una volta (commit `1c47e68`, 04/08/2026) di preferire gli ascolti reali alle classifiche di Spotify per la sezione principale, dopo aver misurato che condividevano 3 brani su 50. La card va dichiarata in UI per quello che è, mantenendo la stessa onestà.

## Assunzioni

| Assunzione | Verdetto |
|---|---|
| **L'ID `37i9dQZEVXbMDoHDwVN2tF` è stabile e raggiungibile in dev mode** | 🔴 **NON VERIFICATA E PORTANTE** — regge da sola tutto il piano. È lo step 1, non un presupposto |
| Un solo utente registrato oggi (`users` = 1, `recent_plays` = 874, 465 brani distinti) | **Verificata** — query diretta su `wrap-postgres-1`/`spotify_intelligence`, 02/09/2026. Rilevante per il limite dichiarato allo step 6 |
| `TrackCard.jsx` riusabile senza modifiche | **Verificata** — lettura diretta del componente |
| Il selettore di periodo governa oggi solo la card personale; "Top 50 secondo Spotify" ha già un selettore suo disaccoppiato | **Verificata** — lettura diretta di `DashboardPage.jsx` |
| `get_playlist_items` esiste, chiama `/playlists/{id}/items`, ha cache per-utente e **non** accetta `market` | **Verificata** — lettura diretta di `spotify_client.py:665-686` |
| Non esiste un flusso Spotify client-credentials: ogni chiamata passa dal token OAuth di un utente | **Verificata** — nessun riferimento in `spotify_client.py` né in `CLAUDE.md` |
| Regola di progetto: i dati indipendenti dall'utente si cachano cross-user | **Verificata** — skill `spotify-api-budget` |

## File impattati

**Backend**: `backend/app/services/global_chart_cache.py` (nuovo); nuovo modello + migrazione in `backend/app/models/` e `backend/alembic/versions/`; `backend/app/routers/library.py` (nuovo endpoint); `backend/app/schemas.py` (`TopGlobalResponse`); `backend/app/services/spotify_client.py` (parametro `market`); il router di `/health/detailed` (campo `global_chart_cache_age_hours`); `backend/tests/test_top_global.py` (nuovo).

**Frontend**: `frontend/src/pages/DashboardPage.jsx`. `TrackCard.jsx` non va toccato.

## Verifica

```bash
cd frontend && npm run lint
cd frontend && npm run build
cd backend && pytest -q
```

Più il giro a mano nel browser: aprire la Dashboard, verificare che le due card di classifica stiano affiancate, che quella nuova mostri la classifica globale col suo timestamp e **non** reagisca al selettore di periodo (comportamento corretto, da confermare a vista), e che **sparisca** invece di lasciare un riquadro vuoto quando non ha dati — incluso il primo caricamento dopo il deploy.

---

## Alternative valutate e scartate (03/09/2026)

**Opzione B — aggregato fra tutti gli utenti della piattaforma.** Stessa query della card personale senza il filtro sull'utente: avrebbe rispettato l'arco temporale chiesto, con zero chiamate a Spotify e nessuna tabella nuova. Scartata perché oggi la piattaforma ha **un solo utente registrato**: la card sarebbe stata una copia esatta di quella accanto. E non sarebbe stata "mondiale" nemmeno in futuro — al più "la community di questa app" — richiedendo un nome diverso. Avrebbe inoltre richiesto due soglie di privacy sommate (minimo di utenti sulla piattaforma **e** minimo di contributori per brano) per non rivelare cosa ascoltano gli altri: con 2-3 utenti totali, una classifica aggregata smaschera i singoli invece di proteggerli. Il ragionamento completo è in `PLAN.draft.md` e `PLAN-REVIEW-LOG.md`.

**Opzione C — fonte esterna (Last.fm, Billboard…).** Scartata senza approfondimento: nuova dipendenza esterna, nuove credenziali e rate limit da gestire, fuori da ogni pattern del progetto. Costo sproporzionato rispetto alla richiesta.

## Prossimo passo

`/feature` con questo file come input. Il primo step eseguibile è la verifica dell'ID playlist: se fallisce, si torna alla scelta A/B.
