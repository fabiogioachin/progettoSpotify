"""Allow running the package with: python -m scripts"""
from scripts.migrate_sqlite_to_pg import run_migration

run_migration()
