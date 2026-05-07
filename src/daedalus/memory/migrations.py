"""SQL migration helpers for Daedalus Postgres persistence.

The migration runner applies committed SQL files without introducing a schema
management dependency yet. It uses the same safe Postgres settings and
connection helper as future repositories, and it only deals in file names and
paths so password-bearing connection strings never need to be logged or built.
"""

from pathlib import Path

from daedalus.config import PostgresSettings
from daedalus.memory.postgres import connect_postgres


def discover_migration_files(migrations_dir: Path) -> list[Path]:
    """Return committed SQL migration files sorted by filename."""
    return sorted(
        (path for path in migrations_dir.iterdir() if path.is_file() and path.suffix == ".sql"),
        key=lambda path: path.name,
    )


def apply_migrations(
    settings: PostgresSettings,
    migrations_dir: Path = Path("sql/migrations"),
) -> list[Path]:
    """Apply SQL migrations to Postgres and return the applied file paths."""
    migration_files = discover_migration_files(migrations_dir)
    connection = connect_postgres(settings)

    try:
        for migration_file in migration_files:
            migration_sql = migration_file.read_text(encoding="utf-8")
            connection.execute(migration_sql)
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()

    return migration_files
