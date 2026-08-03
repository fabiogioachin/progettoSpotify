#!/usr/bin/env python3
"""Import listening history from a Spotify "Download your data" export.

Usage (from backend/ directory):
    python -m scripts.import_spotify_export <path-to-export>            # dry run
    python -m scripts.import_spotify_export <path-to-export> --apply    # write

<path-to-export> may be the downloaded .zip or the folder it was unpacked into.

Environment:
    DATABASE_URL  PostgreSQL DSN (default: the local Docker stack on port 5434)

Two export packages carry listening history, and only one of them is usable
without extra API calls:

  * "Cronologia di ascolto estesa" (Extended streaming history, ~30 days to
    prepare) — files named Streaming_History_Audio_*.json. Carries
    spotify_track_uri, so every play maps straight onto a track id.

  * "Dati dell'account" (Account data, ~5 days) — files named
    StreamingHistory*.json. Carries only track and artist NAMES. recent_plays
    requires a Spotify track id, and guessing one from a name would invent data,
    so those rows are counted and reported but not imported. Resolving them means
    one Spotify search per distinct track, under a 25-calls/30s throttle.

On duration_ms: the export reports ms_played — how long you actually listened —
while the hourly sync stores the track's full length. They are different
quantities. This script writes ms_played, because every consumer of the column
(daily minutes, session length, total listening time) treats it as time
listened, and ms_played is the truer answer for that question. Rows imported
here are therefore slightly more accurate than rows the sync collected, not less.
"""

import argparse
import json
import os
import sys
import zipfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import psycopg2
import psycopg2.extras

_DEFAULT_PG_URL = "postgresql://spotify:spotify_dev@localhost:5434/spotify_intelligence"

# Spotify counts a track as "played" past 30 seconds, and that is the threshold
# behind /me/player/recently-played. Using the same one keeps the imported
# history comparable with what the hourly sync collected.
MIN_MS_PLAYED = 30_000

# Two plays of the same track this close together are the same play seen twice:
# the export timestamps the end of a stream, the API timestamps its own way, and
# the two disagree by seconds over the window both cover.
DEDUP_WINDOW = timedelta(seconds=60)


def _normalise_pg_url(raw: str) -> str:
    return raw.replace("postgresql+asyncpg://", "postgresql://").replace(
        "postgresql+psycopg2://", "postgresql://"
    )


def _parse_pg_url(dsn: str) -> dict[str, Any]:
    parsed = urlparse(dsn)
    kwargs: dict[str, Any] = {
        "host": parsed.hostname,
        "port": parsed.port or 5432,
        "dbname": parsed.path.lstrip("/"),
        "user": parsed.username,
    }
    if parsed.password:
        kwargs["password"] = parsed.password
    return kwargs


# ---------------------------------------------------------------------------
# Reading the export
# ---------------------------------------------------------------------------


def _iter_json_files(source: Path) -> list[tuple[str, Any]]:
    """Return (filename, parsed json) for every .json in the zip or folder."""
    out: list[tuple[str, Any]] = []
    if source.is_file() and source.suffix.lower() == ".zip":
        with zipfile.ZipFile(source) as zf:
            for name in zf.namelist():
                if name.lower().endswith(".json"):
                    with zf.open(name) as fh:
                        out.append((Path(name).name, json.load(fh)))
    elif source.is_dir():
        for path in sorted(source.rglob("*.json")):
            out.append((path.name, json.loads(path.read_text(encoding="utf-8"))))
    else:
        print(f"ERROR: {source} is neither a .zip nor a folder", file=sys.stderr)
        sys.exit(1)
    return out


def _parse_ts(raw: str) -> datetime:
    """Parse an export timestamp into an aware UTC datetime.

    Extended history uses '2026-03-04T22:08:55Z'; account data uses
    '2026-03-04 22:08' with no zone, which Spotify documents as UTC.
    """
    text = raw.strip().replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        parsed = datetime.strptime(text, "%Y-%m-%d %H:%M")
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def collect_plays(source: Path) -> tuple[list[dict], int, list[str]]:
    """Return (importable plays, count lacking a track id, files read)."""
    plays: list[dict] = []
    senza_id = 0
    letti: list[str] = []

    for name, payload in _iter_json_files(source):
        if not isinstance(payload, list) or not payload:
            continue
        first = payload[0]
        if not isinstance(first, dict):
            continue

        if "spotify_track_uri" in first or "master_metadata_track_name" in first:
            letti.append(name)
            for row in payload:
                uri = row.get("spotify_track_uri")
                name_track = row.get("master_metadata_track_name")
                artist = row.get("master_metadata_album_artist_name")
                # Podcast episodes and local files have no track uri.
                if not uri or not name_track or not artist:
                    continue
                plays.append(
                    {
                        "track_spotify_id": uri.rsplit(":", 1)[-1],
                        "track_name": name_track,
                        "artist_name": artist,
                        "duration_ms": row.get("ms_played") or 0,
                        "played_at": _parse_ts(row["ts"]),
                    }
                )
        elif "trackName" in first and "endTime" in first:
            letti.append(name)
            senza_id += len(payload)

    return plays, senza_id, letti


# ---------------------------------------------------------------------------
# Writing
# ---------------------------------------------------------------------------


def _existing_index(cur, user_id: int) -> dict[str, list[datetime]]:
    """Map track id -> sorted play times already stored for this user."""
    cur.execute(
        "SELECT track_spotify_id, played_at FROM recent_plays WHERE user_id = %s",
        (user_id,),
    )
    index: dict[str, list[datetime]] = {}
    for track_id, played_at in cur.fetchall():
        index.setdefault(track_id, []).append(played_at)
    for times in index.values():
        times.sort()
    return index


def _is_duplicate(index: dict[str, list[datetime]], play: dict) -> bool:
    for known in index.get(play["track_spotify_id"], ()):
        if abs(known - play["played_at"]) <= DEDUP_WINDOW:
            return True
    return False


def run(source: Path, user_id: int, apply: bool, min_ms: int) -> None:
    plays, senza_id, letti = collect_plays(source)

    print("=" * 64)
    print(f"Export  : {source}")
    print(f"File letti: {len(letti)}")
    for name in letti:
        print(f"  - {name}")
    print("=" * 64)

    if senza_id:
        print(
            f"\n{senza_id} ascolti nel pacchetto 'Dati dell'account' non hanno "
            "l'identificativo del brano: non importabili senza una ricerca per "
            "nome su Spotify. Serve il pacchetto 'Cronologia di ascolto estesa'."
        )

    if not plays:
        print("\nNessun ascolto importabile trovato.")
        return

    troppo_corti = [p for p in plays if p["duration_ms"] < min_ms]
    plays = [p for p in plays if p["duration_ms"] >= min_ms]

    lo = min(p["played_at"] for p in plays)
    hi = max(p["played_at"] for p in plays)
    print(f"\nAscolti oltre {min_ms / 1000:.0f}s : {len(plays)}")
    print(f"Scartati perche' piu' corti: {len(troppo_corti)}")
    print(f"Periodo coperto            : {lo.date()} -> {hi.date()}")

    dsn = _normalise_pg_url(os.environ.get("DATABASE_URL", _DEFAULT_PG_URL))
    conn = psycopg2.connect(**_parse_pg_url(dsn))
    cur = conn.cursor()

    cur.execute("SELECT COUNT(*) FROM recent_plays WHERE user_id = %s", (user_id,))
    prima = cur.fetchone()[0]

    index = _existing_index(cur, user_id)
    nuovi = [p for p in plays if not _is_duplicate(index, p)]
    print(f"\nGia' presenti in archivio  : {len(plays) - len(nuovi)}")
    print(f"Da inserire                : {len(nuovi)}")

    if not apply:
        print("\nPROVA A VUOTO — nessuna scrittura. Aggiungi --apply per importare.")
        conn.close()
        return

    cols = [
        "user_id",
        "track_spotify_id",
        "track_name",
        "artist_name",
        "duration_ms",
        "played_at",
    ]
    psycopg2.extras.execute_batch(
        cur,
        f"INSERT INTO recent_plays ({', '.join(cols)}) "
        f"VALUES ({', '.join(['%s'] * len(cols))}) ON CONFLICT DO NOTHING",
        [tuple([user_id] + [p[c] for c in cols[1:]]) for p in nuovi],
        page_size=1000,
    )
    cur.execute(
        "SELECT setval(pg_get_serial_sequence('recent_plays','id'), "
        "COALESCE(MAX(id),0)+1, false) FROM recent_plays"
    )
    conn.commit()

    cur.execute("SELECT COUNT(*) FROM recent_plays WHERE user_id = %s", (user_id,))
    dopo = cur.fetchone()[0]
    cur.execute(
        "SELECT MIN(played_at), MAX(played_at) FROM recent_plays WHERE user_id = %s",
        (user_id,),
    )
    nuovo_lo, nuovo_hi = cur.fetchone()
    conn.close()

    print(f"\nrecent_plays: {prima} -> {dopo}  (+{dopo - prima})")
    print(f"Storico ora da {nuovo_lo} a {nuovo_hi}")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("source", type=Path, help="the .zip from Spotify, or its folder")
    ap.add_argument("--user-id", type=int, default=1)
    ap.add_argument("--apply", action="store_true", help="write (default: dry run)")
    ap.add_argument(
        "--min-ms",
        type=int,
        default=MIN_MS_PLAYED,
        help=f"skip plays shorter than this (default {MIN_MS_PLAYED})",
    )
    args = ap.parse_args()
    run(args.source, args.user_id, args.apply, args.min_ms)


if __name__ == "__main__":
    main()
