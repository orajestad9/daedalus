"""Settings for the ReadySetRentables read-only source database boundary."""

import os
from collections.abc import Mapping

from pydantic import BaseModel, Field, field_validator


RSR_SOURCE_POSTGRES_ENV_VARS = (
    "RSR_SOURCE_POSTGRES_HOST",
    "RSR_SOURCE_POSTGRES_PORT",
    "RSR_SOURCE_POSTGRES_DB",
    "RSR_SOURCE_POSTGRES_USER",
    "RSR_SOURCE_POSTGRES_PASSWORD",
)


class RsrSourcePostgresSettings(BaseModel):
    """Typed settings for read-only RSR source Postgres access."""

    host: str
    port: int = Field(ge=1, le=65535)
    database: str
    user: str
    password: str

    @field_validator("host", "database", "user", "password")
    @classmethod
    def _required_string_cannot_be_blank(cls, value: str) -> str:
        stripped_value = value.strip()
        if not stripped_value:
            msg = "field cannot be blank"
            raise ValueError(msg)
        return stripped_value

    @property
    def redacted_dsn(self) -> str:
        """Return a display-safe DSN that never includes the password."""
        return f"postgresql://{self.user}:***@{self.host}:{self.port}/{self.database}"


def load_rsr_source_postgres_settings(
    environ: Mapping[str, str] | None = None,
) -> RsrSourcePostgresSettings:
    """Load required RSR source Postgres settings without connecting to a DB."""
    values = os.environ if environ is None else environ
    env_values = {
        env_var: _required_env(values, env_var) for env_var in RSR_SOURCE_POSTGRES_ENV_VARS
    }

    try:
        port = int(env_values["RSR_SOURCE_POSTGRES_PORT"])
    except ValueError as exc:
        msg = "RSR_SOURCE_POSTGRES_PORT must be an integer"
        raise ValueError(msg) from exc

    return RsrSourcePostgresSettings(
        host=env_values["RSR_SOURCE_POSTGRES_HOST"],
        port=port,
        database=env_values["RSR_SOURCE_POSTGRES_DB"],
        user=env_values["RSR_SOURCE_POSTGRES_USER"],
        password=env_values["RSR_SOURCE_POSTGRES_PASSWORD"],
    )


def _required_env(values: Mapping[str, str], name: str) -> str:
    value = values.get(name)
    if value is None or not value.strip():
        msg = f"Required environment variable {name} is missing or empty"
        raise ValueError(msg)

    return value
