import pytest

from daedalus.config import POSTGRES_ENV_VARS, load_postgres_settings


POSTGRES_ENV = {
    "POSTGRES_HOST": "localhost",
    "POSTGRES_PORT": "5433",
    "POSTGRES_DB": "daedalus_local",
    "POSTGRES_USER": "daedalus_user",
    "POSTGRES_PASSWORD": "super-secret-test-password",
}


def test_load_postgres_settings_success(monkeypatch: pytest.MonkeyPatch) -> None:
    _set_postgres_env(monkeypatch)

    settings = load_postgres_settings()

    assert settings.host == "localhost"
    assert settings.database == "daedalus_local"
    assert settings.user == "daedalus_user"
    assert settings.password == "super-secret-test-password"


def test_load_postgres_settings_parses_port_as_int(monkeypatch: pytest.MonkeyPatch) -> None:
    _set_postgres_env(monkeypatch)

    settings = load_postgres_settings()

    assert settings.port == 5433


def test_load_postgres_settings_missing_required_variable_raises(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _set_postgres_env(monkeypatch)
    monkeypatch.delenv("POSTGRES_HOST")

    with pytest.raises(ValueError, match="POSTGRES_HOST"):
        load_postgres_settings()


def test_load_postgres_settings_empty_required_variable_raises(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _set_postgres_env(monkeypatch)
    monkeypatch.setenv("POSTGRES_PASSWORD", "   ")

    with pytest.raises(ValueError, match="POSTGRES_PASSWORD"):
        load_postgres_settings()


def test_load_postgres_settings_rejects_non_integer_port(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _set_postgres_env(monkeypatch)
    monkeypatch.setenv("POSTGRES_PORT", "not-a-port")

    with pytest.raises(ValueError, match="POSTGRES_PORT must be an integer"):
        load_postgres_settings()


def test_postgres_settings_redacted_dsn_never_includes_password(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _set_postgres_env(monkeypatch)

    settings = load_postgres_settings()

    assert "super-secret-test-password" not in settings.redacted_dsn
    assert settings.redacted_dsn == "postgresql://daedalus_user:***@localhost:5433/daedalus_local"


def _set_postgres_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for env_var in POSTGRES_ENV_VARS:
        monkeypatch.setenv(env_var, POSTGRES_ENV[env_var])
