"""Connection helper for the ReadySetRentables read-only source DB boundary."""

from collections.abc import Callable
from typing import Any

import psycopg

from daedalus.domains.readysetrentables_reviews.source_db_settings import (
    RsrSourcePostgresSettings,
)


def connect_rsr_source_postgres(
    settings: RsrSourcePostgresSettings,
    *,
    connect: Callable[..., Any] | None = None,
) -> Any:
    """Open an RSR source Postgres connection without running any SQL."""
    connect_fn = psycopg.connect if connect is None else connect

    try:
        return connect_fn(
            host=settings.host,
            port=settings.port,
            dbname=settings.database,
            user=settings.user,
            password=settings.password,
            application_name="daedalus_rsr_source_readonly",
        )
    except Exception as exc:
        msg = f"Unable to connect to RSR source Postgres using {settings.redacted_dsn}."
        raise RuntimeError(msg) from exc
