"""Safe environment-based configuration for Daedalus.

This module deliberately reads database settings from process environment only.
Committed files may contain placeholders, but real local or production secrets
must stay in ignored environment files or secret stores.
"""

import os

from pydantic import BaseModel


POSTGRES_ENV_VARS = (
    "POSTGRES_HOST",
    "POSTGRES_PORT",
    "POSTGRES_DB",
    "POSTGRES_USER",
    "POSTGRES_PASSWORD",
)


class PostgresSettings(BaseModel):
    """Typed Postgres settings loaded from environment variables."""

    host: str
    port: int
    database: str
    user: str
    password: str

    @property
    def redacted_dsn(self) -> str:
        """Return a display-safe DSN that never includes the password."""
        return f"postgresql://{self.user}:***@{self.host}:{self.port}/{self.database}"


def load_postgres_settings() -> PostgresSettings:
    """Load required Postgres settings from environment variables."""
    values = {env_var: _required_env(env_var) for env_var in POSTGRES_ENV_VARS}

    try:
        port = int(values["POSTGRES_PORT"])
    except ValueError as exc:
        msg = "POSTGRES_PORT must be an integer"
        raise ValueError(msg) from exc

    return PostgresSettings(
        host=values["POSTGRES_HOST"],
        port=port,
        database=values["POSTGRES_DB"],
        user=values["POSTGRES_USER"],
        password=values["POSTGRES_PASSWORD"],
    )


def _required_env(name: str) -> str:
    value = os.environ.get(name)
    if value is None or not value.strip():
        msg = f"Required environment variable {name} is missing or empty"
        raise ValueError(msg)

    return value
