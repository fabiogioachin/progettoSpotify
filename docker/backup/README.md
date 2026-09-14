# Backup di PostgreSQL

`pg-backup.sh` fa una copia del database e tiene **7 copie giornaliere più 4 settimanali**,
cancellando da sé le più vecchie. Sostituisce la riga di crontab che il piano di lancio
(`docs/LAUNCH-PLAN.md`, § 2.5) chiedeva di incollare a mano sul server: stando nel repo, la
rotazione è coperta da un test (`backend/tests/test_backup_rotation.py`) e queste istruzioni
invecchiano insieme al codice invece che dentro un documento a parte.

## Come si usa

```bash
docker/backup/pg-backup.sh               # copia di oggi, poi rotazione
docker/backup/pg-backup.sh --prune-only  # solo rotazione, nessuna copia
docker/backup/pg-backup.sh --help
```

Lo script **non contiene segreti**. Il `pg_dump` gira dentro il container, dove la connessione è
locale e non chiede password: non serve né `PGPASSWORD` né leggere il file `.env`.

Esce diverso da zero quando la copia fallisce, così `cron` manda una mail all'amministratore. Un
fallimento non lascia mai un file a metà nella cartella: vedi «Come fa a non mentire», più sotto.

## Dove finiscono le copie

```
$BACKUP_DIR/
├── daily/   spotify_AAAAMMGG.sql.gz   ← le 7 più recenti
└── weekly/  spotify_AAAAMMGG.sql.gz   ← le 4 più recenti
```

Di domenica la copia del giorno entra **anche** in `weekly/`, come collegamento fisico: stesso
contenuto, nessun byte in più sul disco, e resta leggibile anche dopo che la copia giornaliera è
stata ruotata via.

## Le manopole

Tutte sono variabili d'ambiente, tutte hanno un valore di partenza che funziona sul server di
produzione descritto in `docker/docker-compose.prod.yml`.

| Variabile | Valore di partenza | A cosa serve |
|---|---|---|
| `BACKUP_DIR` | `/backups` | Cartella che contiene `daily/` e `weekly/` |
| `PG_CONTAINER` | `wrap-postgres-1` | Container su cui lanciare `pg_dump` |
| `POSTGRES_USER` | `spotify` | Utente del database — **non** è il nome del database |
| `POSTGRES_DB` | `spotify_intelligence` | Nome del database |
| `DAILY_KEEP` | `7` | Quante copie giornaliere tenere |
| `WEEKLY_KEEP` | `4` | Quante copie settimanali tenere |
| `WEEKLY_DOW` | `7` | Giorno della copia settimanale, come `date +%u`: 1 = lunedì, 7 = domenica |

Il nome del container dipende dal nome del progetto Compose, che è `wrap` sia in sviluppo sia in
produzione. Se non torna, chiedilo a Docker:

```bash
docker compose -f docker/docker-compose.prod.yml ps -q postgres
```

## Come si mette in cron

Sul server, una volta sola:

```bash
sudo mkdir -p /backups
sudo crontab -e
```

e la riga:

```cron
15 4 * * * BACKUP_DIR=/backups /percorso/del/repo/docker/backup/pg-backup.sh >> /var/log/pg-backup.log 2>&1
```

Le 4:15 stanno **dopo** la pulizia mensile dei dati, che il backend fa il primo del mese alle 3:00
(`cleanup_expired_data`, registrato in `backend/app/main.py:778`, codice in
`backend/app/services/data_retention.py`). L'ora non è scelta a caso: quel lavoro parte con un
ritardo casuale fino a dieci minuti, quindi un backup alle 3:15 rischierebbe di sorprenderlo a metà
strada. Un'ora dopo la copia riflette un database già potato, e non si porta dietro righe che
l'applicazione ha appena deciso di buttare.

## Come si rilegge una copia

Prima di tutto si guarda se il file è sano — e questo si può fare **senza toccare il database**:

```bash
gzip -t /backups/daily/spotify_20260914.sql.gz   # l'archivio è integro?
gzip -cd /backups/daily/spotify_20260914.sql.gz | head -n 5
```

Poi, il ripristino vero. **Cancella il database di destinazione**: fallo su un database nuovo, non
su quello in esercizio, a meno che tu non stia proprio rimediando a un disastro.

```bash
# 1. un database vuoto in cui rileggere la copia
docker exec wrap-postgres-1 createdb -U spotify spotify_restore

# 2. la copia ci entra dentro
gzip -cd /backups/daily/spotify_20260914.sql.gz \
  | docker exec -i wrap-postgres-1 psql -U spotify -d spotify_restore

# 3. la prova che è servito a qualcosa: le righe ci sono
docker exec wrap-postgres-1 psql -U spotify -d spotify_restore \
  -c "select count(*) from recent_plays;"
```

Un backup che nessuno ha mai riletto non è un backup: è un file. Vale la pena fare il giro dei tre
comandi qui sopra almeno una volta, il giorno in cui il server entra in funzione.

## Come fa a non mentire

Tre accortezze, che sono poi i tre modi in cui questo genere di script fallisce in silenzio.

**Un `pg_dump` fallito non produce un file valido.** `pg_dump | gzip` restituisce l'esito di
`gzip`, non quello di `pg_dump`: se il dump muore, `gzip` comprime allegramente zero byte e
consegna un `.gz` perfettamente valido. Lo script guarda l'esito di **entrambi** i comandi della
pipeline, e se il primo è andato storto non scrive niente.

**Il file compare solo quando è finito.** La copia si scrive con il suffisso `.part` e prende il
nome definitivo soltanto dopo i controlli. Chi guarda la cartella — o un `rsync` che la copia
altrove — non incontra mai un backup a metà.

**L'ordine della rotazione si legge dal nome, non dalla data del file.** Una copia, un ripristino o
un `rsync` riscrivono la data di modifica: bastano per far passare per recente un backup di un mese
fa, e per fargli scalzare quelli veri. Il nome `spotify_AAAAMMGG.sql.gz` non si può falsificare per
sbaglio. Per lo stesso motivo la rotazione tocca **solo** i file che rispettano quel nome: qualsiasi
altra cosa nella cartella resta dov'è.
