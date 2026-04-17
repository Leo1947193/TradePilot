from __future__ import annotations

from app.db.migrate import (
    DEFAULT_MIGRATIONS_DIR,
    INSERT_SCHEMA_MIGRATION_SQL,
    SCHEMA_MIGRATIONS_TABLE_SQL,
    SELECT_APPLIED_MIGRATIONS_SQL,
    apply_migrations,
    discover_migrations,
)


class FakeCursor:
    def __init__(self, connection: "FakeConnection") -> None:
        self.connection = connection
        self._results: list[tuple[str]] = []

    def execute(self, sql: str, params=None) -> None:
        normalized = " ".join(sql.split())
        self.connection.executed.append((normalized, params))

        if normalized == " ".join(SELECT_APPLIED_MIGRATIONS_SQL.split()):
            self._results = [(version,) for version in sorted(self.connection.applied_versions)]
        elif normalized == " ".join(INSERT_SCHEMA_MIGRATION_SQL.split()):
            self.connection.applied_versions.add(params[0])

    def fetchall(self) -> list[tuple[str]]:
        return list(self._results)

    def __enter__(self) -> "FakeCursor":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        return None


class FakeTransaction:
    def __init__(self, connection: "FakeConnection") -> None:
        self.connection = connection

    def __enter__(self) -> None:
        self.connection.transaction_entries += 1
        return None

    def __exit__(self, exc_type, exc, tb) -> None:
        return None


class FakeConnection:
    def __init__(self, applied_versions: set[str] | None = None) -> None:
        self.applied_versions = set(applied_versions or set())
        self.executed: list[tuple[str, tuple[str, ...] | None]] = []
        self.transaction_entries = 0

    def cursor(self) -> FakeCursor:
        return FakeCursor(self)

    def transaction(self) -> FakeTransaction:
        return FakeTransaction(self)


def test_discover_migrations_and_apply_in_order(tmp_path) -> None:
    (tmp_path / "0002_second.sql").write_text("SELECT 2;", encoding="utf-8")
    (tmp_path / "0001_first.sql").write_text("SELECT 1;", encoding="utf-8")

    migrations = discover_migrations(tmp_path)
    assert [migration.version for migration in migrations] == ["0001", "0002"]

    connection = FakeConnection()
    applied = apply_migrations(connection, tmp_path)

    assert applied == ["0001", "0002"]
    assert connection.transaction_entries == 2
    executed_sql = [sql for sql, _ in connection.executed]
    assert "SELECT 1;" in executed_sql
    assert "SELECT 2;" in executed_sql


def test_apply_migrations_skips_already_applied_versions(tmp_path) -> None:
    (tmp_path / "0001_first.sql").write_text("SELECT 1;", encoding="utf-8")
    (tmp_path / "0002_second.sql").write_text("SELECT 2;", encoding="utf-8")

    connection = FakeConnection(applied_versions={"0001"})
    applied = apply_migrations(connection, tmp_path)

    assert applied == ["0002"]
    executed_sql = [sql for sql, _ in connection.executed]
    assert "SELECT 1;" not in executed_sql
    assert "SELECT 2;" in executed_sql


def test_schema_migrations_table_creation_runs_before_tracking_checks(tmp_path) -> None:
    (tmp_path / "0001_first.sql").write_text("SELECT 1;", encoding="utf-8")
    connection = FakeConnection()

    apply_migrations(connection, tmp_path)

    executed_sql = [sql for sql, _ in connection.executed]
    assert executed_sql[0] == " ".join(SCHEMA_MIGRATIONS_TABLE_SQL.split())
    assert executed_sql[1] == " ".join(SELECT_APPLIED_MIGRATIONS_SQL.split())


def test_default_migrations_directory_includes_init_and_indexes() -> None:
    migrations = discover_migrations(DEFAULT_MIGRATIONS_DIR)

    assert [migration.version for migration in migrations] == ["0001", "0002"]
    assert migrations[1].path.name == "0002_add_indexes.sql"
