#!/usr/bin/env bash
#
# Backup di PostgreSQL con rotazione: 7 copie giornaliere + 4 settimanali.
#
# Sostituisce la riga di crontab che il piano di lancio chiedeva di incollare a
# mano sul VPS. Qui sta nel repo, quindi la rotazione e' provata da un test e le
# istruzioni stanno accanto al codice: README.md, in questa stessa cartella.
#
# Uso:
#   ./pg-backup.sh               dump + rotazione
#   ./pg-backup.sh --prune-only  solo rotazione, nessun dump (usato dal test)
#   ./pg-backup.sh --help
#
# La configurazione passa da variabili d'ambiente, elencate qui sotto: nessun
# segreto e' scritto in questo file. Il dump gira DENTRO il container, dove la
# connessione e' locale e non chiede password, quindi non serve nemmeno
# esportare PGPASSWORD.

set -euo pipefail

BACKUP_DIR="${BACKUP_DIR:-/backups}"
PG_CONTAINER="${PG_CONTAINER:-wrap-postgres-1}"
POSTGRES_USER="${POSTGRES_USER:-spotify}"
POSTGRES_DB="${POSTGRES_DB:-spotify_intelligence}"
DAILY_KEEP="${DAILY_KEEP:-7}"
WEEKLY_KEEP="${WEEKLY_KEEP:-4}"
# Giorno in cui la copia del giorno diventa anche copia della settimana.
# Numerazione di `date +%u`: 1 = lunedi', 7 = domenica.
WEEKLY_DOW="${WEEKLY_DOW:-7}"

DAILY_DIR="$BACKUP_DIR/daily"
WEEKLY_DIR="$BACKUP_DIR/weekly"

log() {
    printf '%s  %s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$*" >&2
}

usage() {
    sed -n '3,20p' "$0" | sed 's/^# \{0,1\}//'
}

# Tiene i $2 file piu' recenti in $1 e cancella il resto.
#
# L'ordine si legge dal NOME (spotify_AAAAMMGG.sql.gz), non dalla data di
# modifica: una copia, un ripristino o un rsync riscrivono la data di modifica e
# farebbero passare per nuovo un backup vecchio. Il nome no.
prune_dir() {
    local dir="$1" keep="$2" removed=0 victim

    [ -d "$dir" ] || return 0

    while IFS= read -r victim; do
        [ -n "$victim" ] || continue
        rm -f -- "$dir/$victim"
        removed=$((removed + 1))
        log "rotazione: tolto $dir/$victim"
    done <<EOF
$(ls -1 "$dir" 2>/dev/null | grep -E '^spotify_[0-9]{8}\.sql\.gz$' | sort -r | tail -n +"$((keep + 1))")
EOF

    log "rotazione: $dir tiene $keep copie, ne ha tolte $removed"
}

# Verifica che il file sia un archivio integro E un dump vero, non il messaggio
# d'errore di pg_dump compresso — che sarebbe a sua volta un gzip valido.
verify_dump() {
    local file="$1"

    if ! gzip -t -- "$file" 2>/dev/null; then
        log "ERRORE: $file non e' un gzip integro"
        return 1
    fi

    # `grep -q` chiude la pipe al primo riscontro e farebbe morire gunzip di
    # SIGPIPE: con `pipefail` attivo sarebbe un falso fallimento. Per questo il
    # confronto avviene su una variabile, non dentro una pipeline.
    local head_lines
    head_lines="$(gzip -cd -- "$file" | head -n 20 || true)"
    case "$head_lines" in
        *"PostgreSQL database dump"*) ;;
        *)
            log "ERRORE: $file non contiene l'intestazione di un dump PostgreSQL"
            return 1
            ;;
    esac

    return 0
}

do_dump() {
    local stamp part final
    stamp="$(date -u +%Y%m%d)"
    final="$DAILY_DIR/spotify_${stamp}.sql.gz"
    part="$final.part"

    mkdir -p "$DAILY_DIR" "$WEEKLY_DIR"

    log "dump di $POSTGRES_DB dal container $PG_CONTAINER"

    # Senza PIPESTATUS un pg_dump fallito resterebbe invisibile: l'uscita della
    # pipeline sarebbe quella di gzip, che comprime felicemente zero byte e
    # produce un .gz valido. E' il modo classico di accorgersi che i backup sono
    # vuoti il giorno del ripristino.
    set +e
    docker exec "$PG_CONTAINER" pg_dump -U "$POSTGRES_USER" "$POSTGRES_DB" | gzip -c > "$part"
    local codes=("${PIPESTATUS[@]}")
    set -e

    if [ "${codes[0]}" -ne 0 ] || [ "${codes[1]}" -ne 0 ]; then
        rm -f -- "$part"
        log "ERRORE: pg_dump uscito ${codes[0]}, gzip uscito ${codes[1]} — niente file scritto"
        return 1
    fi

    if ! verify_dump "$part"; then
        rm -f -- "$part"
        return 1
    fi

    # Il nome definitivo compare solo dopo la verifica: chi guarda la cartella
    # non trova mai un backup a meta'.
    mv -- "$part" "$final"
    log "scritto $final ($(wc -c < "$final") byte)"

    if [ "$(date -u +%u)" = "$WEEKLY_DOW" ]; then
        local weekly="$WEEKLY_DIR/spotify_${stamp}.sql.gz"
        # Collegamento fisico: stesso contenuto, nessun byte in piu' su disco, e
        # la copia settimanale sopravvive alla rotazione di quella giornaliera.
        ln -- "$final" "$weekly" 2>/dev/null || cp -- "$final" "$weekly"
        log "copia settimanale: $weekly"
    fi
}

main() {
    local prune_only=0

    case "${1:-}" in
        --help|-h) usage; return 0 ;;
        --prune-only) prune_only=1 ;;
        "") ;;
        *) log "ERRORE: argomento sconosciuto '$1'"; usage; return 2 ;;
    esac

    if [ "$prune_only" -eq 0 ]; then
        do_dump
    fi

    prune_dir "$DAILY_DIR" "$DAILY_KEEP"
    prune_dir "$WEEKLY_DIR" "$WEEKLY_KEEP"
}

main "$@"
