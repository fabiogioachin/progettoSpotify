# Rilievi respinti — nessuno

Cinque giri di revisione avversariale, **27 rilievi in totale**, **zero respinti come falsi positivi**. Tutti sono stati accolti e applicati al piano.

| Revisore | Giri | Rilievi | Accolti | Respinti |
|---|---|---|---|---|
| Codex | — | — | — | non disponibile (limite d'uso fino al 10/09/2026, sonda fresca del 02/09) |
| Gemini | 2 | 6 | 6 | 0 |
| Opus (interno, ripiego) | 3 | 21 | 21 | 0 |

## Perché nessun respinto, e perché non è un buon segno di per sé

Un tasso di accettazione del 100% di solito indica un revisore compiacente. Qui non è il caso, e vale la pena scriverlo perché la prossima pianificazione non lo legga come "il piano era buono":

- **Un rilievo era un BLOCKER reale trovato solo al quinto giro** (R2O-F-01): un task in background che avrebbe riusato un client Spotify già chiuso, fallendo in silenzio. Sarebbe sopravvissuto all'implementazione e ai test manuali, perché il refresh orario avrebbe comunque popolato la cache più tardi, mascherando il difetto.
- **Due rilievi hanno corretto correzioni precedenti**, non il piano originale: la soglia di privacy dell'Opzione B è stata riscritta due volte, e la seconda versione (soglia solo per brano) era *peggiore* della prima — con 2-3 utenti totali deanonimizzava invece di proteggere. Senza il giro successivo sarebbe passata così.
- **Ogni giro di delta review ha trovato difetti nelle correzioni del giro precedente, mai negli step originali.** È la prova diretta a favore della regola del protocollo per cui "il secondo giro non è facoltativo".

## Note su rilievi accolti con riformulazione

Due rilievi sono stati accolti nella sostanza ma non alla lettera:

- **R2G-02** (Gemini, MAJOR, scope creep): «non introdurre APScheduler, è sproporzionato». APScheduler **esiste già** nel progetto con quattro job documentati — la premessa era sbagliata. Il punto valido sotto era un altro: non introdurre *un nuovo job* apposta per una card. Risolto agganciandosi a un job esistente. Accolto per la conclusione, non per il ragionamento.
- **R2G-2-01** (Gemini, MINOR): chiedeva di passare `market` a `get_playlist_items`. Corretto come intento, ma il metodo non accetta quel parametro — l'ha scoperto Opus due giri dopo (R2O-2-03) leggendo il codice reale. Il rilievo è stato accolto insieme alla modifica al client che rende possibile applicarlo.
