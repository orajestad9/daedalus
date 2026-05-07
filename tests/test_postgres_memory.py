from daedalus.config import PostgresSettings
from daedalus.memory.postgres import build_postgres_connection_kwargs


def test_build_postgres_connection_kwargs_maps_settings() -> None:
    settings = _postgres_settings()

    kwargs = build_postgres_connection_kwargs(settings)

    assert kwargs == {
        "host": "localhost",
        "port": 5433,
        "dbname": "daedalus_local",
        "user": "daedalus_user",
        "password": "super-secret-test-password",
    }


def test_build_postgres_connection_kwargs_includes_password_for_internal_use() -> None:
    settings = _postgres_settings()

    kwargs = build_postgres_connection_kwargs(settings)

    assert kwargs["password"] == "super-secret-test-password"


def test_redacted_dsn_does_not_expose_password() -> None:
    settings = _postgres_settings()

    assert "super-secret-test-password" not in settings.redacted_dsn
    assert settings.redacted_dsn == "postgresql://daedalus_user:***@localhost:5433/daedalus_local"


def test_postgres_helper_does_not_require_environment_variables() -> None:
    settings = _postgres_settings()

    kwargs = build_postgres_connection_kwargs(settings)

    assert kwargs["host"] == "localhost"


def _postgres_settings() -> PostgresSettings:
    return PostgresSettings(
        host="localhost",
        port=5433,
        database="daedalus_local",
        user="daedalus_user",
        password="super-secret-test-password",
    )
