"""Postgres connection helpers for Daedalus persistence.

This module is intentionally small: it converts safe typed settings into the
keyword arguments psycopg needs. It does not build or log password-bearing DSNs,
which keeps secret handling explicit before persistence repositories are added.
"""

from typing import Any

import psycopg

from daedalus.config import PostgresSettings


def build_postgres_connection_kwargs(settings: PostgresSettings) -> dict[str, object]:
    """Build psycopg connection keyword arguments from typed settings."""
    return {
        "host": settings.host,
        "port": settings.port,
        "dbname": settings.database,
        "user": settings.user,
        "password": settings.password,
    }


def connect_postgres(settings: PostgresSettings) -> psycopg.Connection[Any]:
    """Open a Postgres connection using keyword arguments, never a secret-bearing DSN."""
    connection_kwargs = build_postgres_connection_kwargs(settings)
    port = connection_kwargs["port"]
    if not isinstance(port, int):
        msg = "Postgres connection port must be an integer"
        raise TypeError(msg)

    return psycopg.connect(
        host=str(connection_kwargs["host"]),
        port=port,
        dbname=str(connection_kwargs["dbname"]),
        user=str(connection_kwargs["user"]),
        password=str(connection_kwargs["password"]),
    )
