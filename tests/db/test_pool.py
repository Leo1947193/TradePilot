from __future__ import annotations

from types import SimpleNamespace

from app.config import Settings
from app.db import pool as pool_module


def test_settings_load_expected_env_vars(monkeypatch) -> None:
    monkeypatch.setenv("POSTGRES_DSN", "postgresql://user:pass@localhost:5432/tradepilot")
    monkeypatch.setenv("POSTGRES_MIN_POOL_SIZE", "2")
    monkeypatch.setenv("POSTGRES_MAX_POOL_SIZE", "8")
    monkeypatch.setenv("POSTGRES_CONNECT_TIMEOUT_SECONDS", "7.5")

    settings = Settings()

    assert settings.postgres_dsn == "postgresql://user:pass@localhost:5432/tradepilot"
    assert settings.postgres_min_pool_size == 2
    assert settings.postgres_max_pool_size == 8
    assert settings.postgres_connect_timeout_seconds == 7.5


def test_settings_build_postgres_dsn_from_container_env_vars(monkeypatch) -> None:
    monkeypatch.delenv("POSTGRES_DSN", raising=False)
    monkeypatch.setenv("POSTGRES_HOST", "db")
    monkeypatch.setenv("POSTGRES_PORT", "5432")
    monkeypatch.setenv("POSTGRES_USER", "tradepilot")
    monkeypatch.setenv("POSTGRES_PASSWORD", "tradepilot")
    monkeypatch.setenv("POSTGRES_DB", "tradepilot")

    settings = Settings()

    assert settings.postgres_dsn == "postgresql://tradepilot:tradepilot@db:5432/tradepilot"


def test_explicit_postgres_dsn_takes_precedence_over_container_fields() -> None:
    settings = Settings(
        postgres_dsn="postgresql://override:secret@postgres.internal:5433/analytics",
        postgres_host="db",
        postgres_port=5432,
        postgres_user="tradepilot",
        postgres_password="tradepilot",
        postgres_db="tradepilot",
    )

    assert settings.postgres_dsn == "postgresql://override:secret@postgres.internal:5433/analytics"


def test_create_connection_pool_passes_expected_arguments(monkeypatch) -> None:
    captured_kwargs: dict[str, object] = {}

    class FakeConnectionPool:
        def __init__(self, **kwargs):
            captured_kwargs.update(kwargs)

    monkeypatch.setattr(pool_module, "ConnectionPool", FakeConnectionPool)

    settings = Settings(
        postgres_dsn="postgresql://user:pass@localhost:5432/tradepilot",
        postgres_min_pool_size=3,
        postgres_max_pool_size=9,
        postgres_connect_timeout_seconds=4.5,
    )

    pool = pool_module.create_connection_pool(settings)

    assert isinstance(pool, FakeConnectionPool)
    assert captured_kwargs == {
        "conninfo": "postgresql://user:pass@localhost:5432/tradepilot",
        "min_size": 3,
        "max_size": 9,
        "timeout": 4.5,
        "kwargs": {"connect_timeout": 4.5},
        "open": False,
    }


def test_close_connection_pool_closes_pool() -> None:
    fake_pool = SimpleNamespace(closed=False)

    def close() -> None:
        fake_pool.closed = True

    fake_pool.close = close

    pool_module.close_connection_pool(fake_pool)

    assert fake_pool.closed is True
