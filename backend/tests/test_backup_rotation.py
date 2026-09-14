"""Prova la rotazione di `docker/backup/pg-backup.sh`.

La parte del backup che si puo' sbagliare in silenzio e' la rotazione: se tiene i
file sbagliati te ne accorgi il giorno del ripristino, non prima. Per questo gira
lo **script vero** — non una riscrittura in Python dello stesso ragionamento, che
proverebbe solo se stessa — nel suo ramo `--prune-only`, che non tocca nessun
database.

I file su cui gira sono archivi gzip veri, creati qui: la rotazione ragiona sui
nomi e non legge il contenuto, quindi il contenuto e' solo un segnaposto
dichiarato, non un dato inventato che finge di essere una misura.
"""

import gzip
import os
import shutil
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "docker" / "backup" / "pg-backup.sh"

# Git Bash su Windows, /bin/bash ovunque altrove. In CI (ubuntu) c'e' sempre.
BASH = shutil.which("bash")


def _write_dump(path: Path, stamp: str) -> None:
    """Scrive un .sql.gz vero: archivio gzip valido, intestazione di un dump."""
    path.parent.mkdir(parents=True, exist_ok=True)
    body = f"-- PostgreSQL database dump\n-- segnaposto del test, giorno {stamp}\n"
    path.write_bytes(gzip.compress(body.encode()))


def _run_prune(backup_dir: Path, **env_extra: str) -> subprocess.CompletedProcess:
    env = {"BACKUP_DIR": str(backup_dir), "PATH": os.environ.get("PATH", "")}
    env.update(env_extra)
    return subprocess.run(
        [BASH, str(SCRIPT), "--prune-only"],
        capture_output=True,
        text=True,
        env=env,
        timeout=60,
    )


def _names(directory: Path) -> list[str]:
    return sorted(p.name for p in directory.iterdir())


pytestmark = pytest.mark.skipif(
    BASH is None, reason="serve bash per eseguire lo script di backup"
)


def test_lo_script_esiste_ed_e_eseguibile():
    assert SCRIPT.is_file(), f"manca {SCRIPT}"


def test_tiene_le_sette_giornaliere_piu_recenti(tmp_path):
    daily = tmp_path / "daily"
    giorni = [f"202609{d:02d}" for d in range(1, 11)]  # 10 copie, dal 01 al 10
    for giorno in giorni:
        _write_dump(daily / f"spotify_{giorno}.sql.gz", giorno)

    result = _run_prune(tmp_path)

    assert result.returncode == 0, result.stderr
    assert _names(daily) == [f"spotify_{g}.sql.gz" for g in giorni[-7:]]


def test_tiene_le_quattro_settimanali_piu_recenti(tmp_path):
    weekly = tmp_path / "weekly"
    domeniche = ["20260802", "20260809", "20260816", "20260823", "20260830", "20260906"]
    for giorno in domeniche:
        _write_dump(weekly / f"spotify_{giorno}.sql.gz", giorno)

    result = _run_prune(tmp_path)

    assert result.returncode == 0, result.stderr
    assert _names(weekly) == [f"spotify_{g}.sql.gz" for g in domeniche[-4:]]


def test_sotto_soglia_non_cancella_niente(tmp_path):
    daily = tmp_path / "daily"
    giorni = ["20260912", "20260913", "20260914"]
    for giorno in giorni:
        _write_dump(daily / f"spotify_{giorno}.sql.gz", giorno)

    result = _run_prune(tmp_path)

    assert result.returncode == 0, result.stderr
    assert _names(daily) == [f"spotify_{g}.sql.gz" for g in giorni]


def test_l_ordine_si_legge_dal_nome_non_dalla_data_di_modifica(tmp_path):
    """Il file piu' vecchio di nome, ma toccato per ultimo, deve comunque sparire.

    E' il caso che rompe la rotazione scritta con `ls -t` o `find -mtime`: un
    ripristino o un rsync riscrivono la data di modifica, e un backup di settimane
    fa si presenta come il piu' fresco della cartella.
    """
    daily = tmp_path / "daily"
    giorni = [f"202609{d:02d}" for d in range(1, 11)]
    for giorno in giorni:
        _write_dump(daily / f"spotify_{giorno}.sql.gz", giorno)

    # Il piu' vecchio diventa il piu' recente per data di modifica.
    piu_vecchio = daily / "spotify_20260901.sql.gz"
    piu_recente = daily / "spotify_20260910.sql.gz"
    mtime_recente = piu_recente.stat().st_mtime
    os.utime(piu_vecchio, (mtime_recente + 10_000, mtime_recente + 10_000))

    result = _run_prune(tmp_path)

    assert result.returncode == 0, result.stderr
    assert not piu_vecchio.exists(), "la rotazione ha guardato la data invece del nome"
    assert _names(daily) == [f"spotify_{g}.sql.gz" for g in giorni[-7:]]


def test_non_tocca_i_file_che_non_sono_suoi(tmp_path):
    daily = tmp_path / "daily"
    for giorno in [f"202609{d:02d}" for d in range(1, 11)]:
        _write_dump(daily / f"spotify_{giorno}.sql.gz", giorno)

    estranei = ["LEGGIMI.txt", "spotify_manuale.sql.gz", "spotify_2026090.sql.gz"]
    for nome in estranei:
        (daily / nome).write_text("roba di qualcun altro")

    result = _run_prune(tmp_path)

    assert result.returncode == 0, result.stderr
    for nome in estranei:
        assert (daily / nome).exists(), f"la rotazione ha cancellato {nome}"


def test_le_soglie_si_possono_cambiare(tmp_path):
    daily = tmp_path / "daily"
    giorni = [f"202609{d:02d}" for d in range(1, 11)]
    for giorno in giorni:
        _write_dump(daily / f"spotify_{giorno}.sql.gz", giorno)

    result = _run_prune(tmp_path, DAILY_KEEP="2")

    assert result.returncode == 0, result.stderr
    assert _names(daily) == [f"spotify_{g}.sql.gz" for g in giorni[-2:]]


def test_cartella_mancante_non_e_un_errore(tmp_path):
    """Il primo giro sul server trova `/backups` vuoto: non deve morire li'."""
    result = _run_prune(tmp_path)

    assert result.returncode == 0, result.stderr


def test_argomento_sconosciuto_esce_diverso_da_zero(tmp_path):
    env = {"BACKUP_DIR": str(tmp_path), "PATH": os.environ.get("PATH", "")}
    result = subprocess.run(
        [BASH, str(SCRIPT), "--rotazione-totale"],
        capture_output=True,
        text=True,
        env=env,
        timeout=60,
    )

    assert result.returncode != 0
    assert "argomento sconosciuto" in result.stderr


def test_l_aiuto_stampa_solo_il_commento_di_testa(tmp_path):
    """--help non deve lasciar scappare il codice che sta sotto il commento.

    L'aiuto si ricava dal blocco di commento in cima al file. Scritto come
    intervallo di righe fisso, basta aggiungere una riga perche' cominci a
    stampare `set -euo pipefail` in coda: e' successo, ed e' il motivo di questo
    test.
    """
    env = {"BACKUP_DIR": str(tmp_path), "PATH": os.environ.get("PATH", "")}
    result = subprocess.run(
        [BASH, str(SCRIPT), "--help"],
        capture_output=True,
        text=True,
        env=env,
        timeout=60,
    )

    assert result.returncode == 0, result.stderr
    assert "rotazione: 7 copie giornaliere" in result.stdout
    assert "--prune-only" in result.stdout
    assert "set -euo pipefail" not in result.stdout
    assert "BACKUP_DIR=" not in result.stdout
