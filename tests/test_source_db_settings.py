import os

import pytest
from pydantic import ValidationError

from daedalus.domains.readysetrentables_reviews.source_db_settings import (
    RSR_SOURCE_POSTGRES_ENV_VARS,
    RsrSourcePostgresSettings,
    load_rsr_source_postgres_settings,
)


RSR_SOURCE_POSTGRES_ENV = {
    "RSR_SOURCE_POSTGRES_HOST": "rsr-db.local",
    "RSR_SOURCE_POSTGRES_PORT": "5439",
    "RSR_SOURCE_POSTGRES_DB": "readysetrentables",
    "RSR_SOURCE_POSTGRES_USER": "rsr_readonly",
    "RSR_SOURCE_POSTGRES_PASSWORD": "super-secret-rsr-password",
}


def test_load_rsr_source_postgres_settings_success() -> None:
    settings = load_rsr_source_postgres_settings(RSR_SOURCE_POSTGRES_ENV)

    assert settings.host == "rsr-db.local"
    assert settings.port == 5439
    assert settings.database == "readysetrentables"
    assert settings.user == "rsr_readonly"
    assert settings.password == "super-secret-rsr-password"


@pytest.mark.parametrize(
    ("field_name", "kwargs"),
    [
        ("host", {"host": "   "}),
        ("database", {"database": "   "}),
        ("user", {"user": "   "}),
        ("password", {"password": "   "}),
    ],
)
def test_rsr_source_postgres_settings_required_strings_cannot_be_blank(
    field_name: str,
    kwargs: dict[str, object],
) -> None:
    settings_kwargs: dict[str, object] = {
        "host": "rsr-db.local",
        "port": 5439,
        "database": "readysetrentables",
        "user": "rsr_readonly",
        "password": "super-secret-rsr-password",
    }
    settings_kwargs.update(kwargs)

    with pytest.raises(ValidationError, match=field_name):
        RsrSourcePostgresSettings.model_validate(settings_kwargs)


def test_load_rsr_source_postgres_settings_rejects_non_integer_port() -> None:
    env = {**RSR_SOURCE_POSTGRES_ENV, "RSR_SOURCE_POSTGRES_PORT": "not-a-port"}

    with pytest.raises(ValueError, match="RSR_SOURCE_POSTGRES_PORT must be an integer") as exc_info:
        load_rsr_source_postgres_settings(env)

    assert "super-secret-rsr-password" not in str(exc_info.value)


@pytest.mark.parametrize("port", [0, -1])
def test_rsr_source_postgres_settings_port_must_be_at_least_one(port: int) -> None:
    with pytest.raises(ValidationError, match="port"):
        RsrSourcePostgresSettings(
            host="rsr-db.local",
            port=port,
            database="readysetrentables",
            user="rsr_readonly",
            password="super-secret-rsr-password",
        )


def test_rsr_source_postgres_settings_port_must_be_at_most_65535() -> None:
    with pytest.raises(ValidationError, match="port"):
        RsrSourcePostgresSettings(
            host="rsr-db.local",
            port=65536,
            database="readysetrentables",
            user="rsr_readonly",
            password="super-secret-rsr-password",
        )


def test_load_rsr_source_postgres_settings_missing_variable_raises() -> None:
    env = dict(RSR_SOURCE_POSTGRES_ENV)
    env.pop("RSR_SOURCE_POSTGRES_HOST")

    with pytest.raises(ValueError, match="RSR_SOURCE_POSTGRES_HOST") as exc_info:
        load_rsr_source_postgres_settings(env)

    assert "super-secret-rsr-password" not in str(exc_info.value)


def test_rsr_source_postgres_settings_redacted_dsn_includes_safe_connection_parts() -> None:
    settings = load_rsr_source_postgres_settings(RSR_SOURCE_POSTGRES_ENV)

    assert "rsr_readonly" in settings.redacted_dsn
    assert "rsr-db.local" in settings.redacted_dsn
    assert "5439" in settings.redacted_dsn
    assert "readysetrentables" in settings.redacted_dsn
    assert (
        settings.redacted_dsn == "postgresql://rsr_readonly:***@rsr-db.local:5439/readysetrentables"
    )


def test_rsr_source_postgres_settings_redacted_dsn_never_includes_password() -> None:
    settings = load_rsr_source_postgres_settings(RSR_SOURCE_POSTGRES_ENV)

    assert "super-secret-rsr-password" not in settings.redacted_dsn


def test_load_rsr_source_postgres_settings_uses_environ_argument(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    for env_var in RSR_SOURCE_POSTGRES_ENV_VARS:
        monkeypatch.setenv(env_var, f"os-{env_var.lower()}")

    settings = load_rsr_source_postgres_settings(RSR_SOURCE_POSTGRES_ENV)

    assert settings.host == "rsr-db.local"
    assert settings.port == 5439
    assert settings.database == "readysetrentables"
    assert settings.user == "rsr_readonly"
    assert settings.password == "super-secret-rsr-password"
    assert os.environ["RSR_SOURCE_POSTGRES_HOST"] != settings.host
