#!/usr/bin/env python3
"""One-time migration: SQLite -> PostgreSQL.

Usage (from backend/ directory):
    python -m scripts.migrate_sqlite_to_pg

Environment:
    DATABASE_URL  PostgreSQL DSN (default: postgresql+asyncpg://spotify:spotify_dev@localhost:5434/spotify_intelligence)
                  The script accepts both asyncpg and psycopg2 URL schemes and normalises to psycopg2.
"""

import os
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import psycopg2
import psycopg2.extras

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

# Project root is two levels up from this file (backend/scripts/ -> backend/ -> project_root/)
_BACKEND_DIR = Path(__file__).resolve().parent.parent
_PROJECT_ROOT = _BACKEND_DIR.parent

SQLITE_PATH = _PROJECT_ROOT / "data" / "spotify_intelligence.db"

_DEFAULT_PG_URL = "postgresql+asyncpg://spotify:spotify_dev@localhost:5434/spotify_intelligence"

BATCH_SIZE = 1000

# ---------------------------------------------------------------------------
# Table definitions
# Migration order respects FK dependencies:
#   users -> spotify_tokens -> everything else
# Each entry: (table_name, datetime_columns)
# ---------------------------------------------------------------------------

TABLE_ORDER: list[tuple[str, list[str]]] = [
    ("users", ["created_at", "updated_at"]),
    ("spotify_tokens", ["expires_at", "updated_at"]),
    ("listening_snapshots", ["snapshot_date"]),
    ("recent_plays", ["played_at"]),
    ("user_snapshots", []),
    ("daily_listening_stats", []),
    ("user_profile_metrics", ["updated_at"]),
    ("audio_features", ["cached_at"]),
    ("track_popularity", ["cached_at"]),
    ("friendships", ["created_at"]),
    ("friend_invite_links", ["created_at", "expires_at"]),
]

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _normalise_pg_url(raw: str) -> str:
    """Convert an asyncpg or sqlalchemy DSN to a plain psycopg2 DSN.

    Handles:
      - postgresql+asyncpg://...  -> postgresql://...
      - postgresql+psycopg2://... -> postgresql://...
    """
    raw = raw.replace("postgresql+asyncpg://", "postgresql://")
    raw = raw.replace("postgresql+psycopg2://", "postgresql://")
    return raw


def _parse_pg_url(dsn: str) -> dict[str, Any]:
    """Parse a postgresql:// DSN into psycopg2 connect kwargs."""
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


def _to_utc(value: Any) -> Any:
    """Attach UTC timezone to a naive datetime; return non-datetime values unchanged."""
    if not isinstance(value, datetime):
        return value
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


def _make_utc_aware(row: dict[str, Any], dt_columns: list[str]) -> dict[str, Any]:
    """Return a new dict with all specified datetime columns made UTC-aware."""
    if not dt_columns:
        return row
    result = dict(row)
    for col in dt_columns:
        if col in result and result[col] is not None:
            result[col] = _to_utc(result[col])
    return result


# ---------------------------------------------------------------------------
# Core migration
# ---------------------------------------------------------------------------


def _get_columns(sqlite_cur: sqlite3.Cursor, table: str) -> list[str]:
    sqlite_cur.execute(f"PRAGMA table_info({table})")
    return [row[1] for row in sqlite_cur.fetchall()]


def _pg_row_count(pg_cur: psycopg2.extensions.cursor, table: str) -> int:
    pg_cur.execute(f"SELECT COUNT(*) FROM {table}")
    result = pg_cur.fetchone()
    return result[0] if result else 0


def _reset_sequence(pg_cur: psycopg2.extensions.cursor, table: str) -> None:
    """Reset the PG serial sequence to MAX(id)+1 to avoid PK conflicts on future inserts."""
    pg_cur.execute(
        f"""
        SELECT setval(
            pg_get_serial_sequence('{table}', 'id'),
            COALESCE(MAX(id), 0) + 1,
            false
        )
        FROM {table}
        """
    )


def migrate_table(
    sqlite_conn: sqlite3.Connection,
    pg_conn: psycopg2.extensions.connection,
    table: str,
    dt_columns: list[str],
) -> int:
    """Migrate a single table. Returns the number of rows inserted (0 if skipped)."""
    sqlite_cur = sqlite_conn.cursor()
    pg_cur = pg_conn.cursor()

    # Idempotency check — skip if PG already has data.
    existing = _pg_row_count(pg_cur, table)
    if existing > 0:
        print(f"  [SKIP] {table}: already has {existing} rows in PostgreSQL — skipping.")
        return 0

    columns = _get_columns(sqlite_cur, table)
    if not columns:
        print(f"  [WARN] {table}: table not found in SQLite — skipping.")
        return 0

    sqlite_cur.execute(f"SELECT COUNT(*) FROM {table}")
    total_result = sqlite_cur.fetchone()
    total = total_result[0] if total_result else 0

    if total == 0:
        print(f"  {table}: 0 rows (empty table — nothing to migrate).")
        _reset_sequence(pg_cur, table)
        pg_conn.commit()
        return 0

    col_list = ", ".join(columns)
    placeholders = ", ".join(["%s"] * len(columns))
    insert_sql = (
        f"INSERT INTO {table} ({col_list}) VALUES ({placeholders}) ON CONFLICT DO NOTHING"
    )

    inserted_total = 0
    offset = 0

    while True:
        sqlite_cur.execute(
            f"SELECT {col_list} FROM {table} LIMIT {BATCH_SIZE} OFFSET {offset}"
        )
        raw_rows = sqlite_cur.fetchall()
        if not raw_rows:
            break

        rows_to_insert = []
        for raw in raw_rows:
            row_dict = dict(zip(columns, raw))
            row_dict = _make_utc_aware(row_dict, dt_columns)
            rows_to_insert.append(tuple(row_dict[c] for c in columns))

        psycopg2.extras.execute_batch(pg_cur, insert_sql, rows_to_insert, page_size=BATCH_SIZE)
        inserted_total += len(rows_to_insert)
        offset += BATCH_SIZE

    _reset_sequence(pg_cur, table)
    pg_conn.commit()

    print(f"  {table}: {inserted_total}/{total} rows migrated.")
    return inserted_total


def run_migration() -> None:
    """Entry point: open connections, iterate over tables, report summary."""
    # Resolve the SQLite path
    if not SQLITE_PATH.exists():
        print(f"ERROR: SQLite database not found at {SQLITE_PATH}", file=sys.stderr)
        sys.exit(1)

    # Resolve the PG DSN
    raw_pg_url = os.environ.get("DATABASE_URL", _DEFAULT_PG_URL)
    pg_dsn = _normalise_pg_url(raw_pg_url)
    pg_kwargs = _parse_pg_url(pg_dsn)

    print("=" * 60)
    print("SQLite -> PostgreSQL migration")
    print(f"  SQLite : {SQLITE_PATH}")
    print(f"  PG host: {pg_kwargs['host']}:{pg_kwargs['port']}  db={pg_kwargs['dbname']}")
    print("=" * 60)

    sqlite_conn = sqlite3.connect(str(SQLITE_PATH), detect_types=sqlite3.PARSE_DECLTYPES)
    sqlite_conn.row_factory = sqlite3.Row

    try:
        pg_conn = psycopg2.connect(**pg_kwargs)
    except psycopg2.OperationalError as exc:
        print(f"ERROR: cannot connect to PostgreSQL: {exc}", file=sys.stderr)
        sqlite_conn.close()
        sys.exit(1)

    total_rows = 0
    skipped_tables = 0

    try:
        for table, dt_cols in TABLE_ORDER:
            inserted = migrate_table(sqlite_conn, pg_conn, table, dt_cols)
            if inserted == 0:
                skipped_tables += 1
            else:
                total_rows += inserted
    except Exception as exc:
        pg_conn.rollback()
        print(f"\nFATAL ERROR during migration: {exc}", file=sys.stderr)
        raise
    finally:
        sqlite_conn.close()
        pg_conn.close()

    print("=" * 60)
    print(
        f"Migration complete. "
        f"{total_rows} rows inserted across {len(TABLE_ORDER) - skipped_tables} table(s). "
        f"{skipped_tables} table(s) skipped (already had data)."
    )
    print("=" * 60)


# ---------------------------------------------------------------------------
# __main__ entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    run_migration()
