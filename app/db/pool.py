from __future__ import annotations

from psycopg_pool import ConnectionPool

from app.config import Settings


def create_connection_pool(settings: Settings) -> ConnectionPool:
    return ConnectionPool(
        conninfo=settings.postgres_dsn,
        min_size=settings.postgres_min_pool_size,
        max_size=settings.postgres_max_pool_size,
        timeout=settings.postgres_connect_timeout_seconds,
        kwargs={
            "connect_timeout": settings.postgres_connect_timeout_seconds,
        },
        open=False,
    )


def open_connection_pool(pool: ConnectionPool) -> ConnectionPool:
    pool.open()
    return pool


def close_connection_pool(pool: ConnectionPool) -> None:
    pool.close()
