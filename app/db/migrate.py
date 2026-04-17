from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import sys

from app.config import get_settings
from app.db.pool import close_connection_pool, create_connection_pool, open_connection_pool


SCHEMA_MIGRATIONS_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS schema_migrations (
    version text PRIMARY KEY,
    applied_at timestamptz NOT NULL DEFAULT now()
)
""".strip()

INSERT_SCHEMA_MIGRATION_SQL = """
INSERT INTO schema_migrations (version)
VALUES (%s)
""".strip()

SELECT_APPLIED_MIGRATIONS_SQL = """
SELECT version
FROM schema_migrations
ORDER BY version
""".strip()

DEFAULT_MIGRATIONS_DIR = Path(__file__).with_name("migrations")


@dataclass(frozen=True)
class Migration:
    version: str
    path: Path
    sql: str


def discover_migrations(migrations_dir: Path | None = None) -> list[Migration]:
    base_dir = migrations_dir or DEFAULT_MIGRATIONS_DIR
    migrations: list[Migration] = []

    for path in sorted(base_dir.glob("[0-9][0-9][0-9][0-9]_*.sql")):
        migrations.append(
            Migration(
                version=path.stem.split("_", 1)[0],
                path=path,
                sql=path.read_text(encoding="utf-8").strip(),
            )
        )

    return migrations


def ensure_schema_migrations_table(connection) -> None:
    with connection.cursor() as cursor:
        cursor.execute(SCHEMA_MIGRATIONS_TABLE_SQL)


def get_applied_versions(connection) -> set[str]:
    with connection.cursor() as cursor:
        cursor.execute(SELECT_APPLIED_MIGRATIONS_SQL)
        rows = cursor.fetchall()

    return {row[0] for row in rows}


def apply_migrations(connection, migrations_dir: Path | None = None) -> list[str]:
    ensure_schema_migrations_table(connection)
    applied_versions = get_applied_versions(connection)
    applied_now: list[str] = []

    for migration in discover_migrations(migrations_dir):
        if migration.version in applied_versions:
            continue

        with connection.transaction():
            with connection.cursor() as cursor:
                cursor.execute(migration.sql)
                cursor.execute(INSERT_SCHEMA_MIGRATION_SQL, (migration.version,))

        applied_now.append(migration.version)
        applied_versions.add(migration.version)

    return applied_now


def migrate_up() -> list[str]:
    settings = get_settings()
    pool = create_connection_pool(settings)
    open_connection_pool(pool)

    try:
        with pool.connection() as connection:
            return apply_migrations(connection)
    finally:
        close_connection_pool(pool)


def main(argv: list[str] | None = None) -> int:
    args = argv or sys.argv[1:]
    if args != ["up"]:
        print("Usage: python -m app.db.migrate up")
        return 1

    apply_migrations_result = migrate_up()
    print(f"Applied migrations: {', '.join(apply_migrations_result) or 'none'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
