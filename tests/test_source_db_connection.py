from typing import Any

import pytest

from daedalus.domains.readysetrentables_reviews.source_db_connection import (
    connect_rsr_source_postgres,
)
from daedalus.domains.readysetrentables_reviews.source_db_settings import (
    RsrSourcePostgresSettings,
)


class FakeConnection:
    def __init__(self) -> None:
        self.queries: list[object] = []

    def execute(self, query: object) -> None:
        self.queries.append(query)


class RecordingConnect:
    def __init__(self, *, connection: FakeConnection | None = None) -> None:
        self.connection = connection or FakeConnection()
        self.calls: list[tuple[tuple[Any, ...], dict[str, Any]]] = []

    def __call__(self, *args: Any, **kwargs: Any) -> FakeConnection:
        self.calls.append((args, kwargs))
        return self.connection


def test_connect_rsr_source_postgres_calls_injected_connect() -> None:
    connect = RecordingConnect()

    connect_rsr_source_postgres(_settings(), connect=connect)

    assert len(connect.calls) == 1


def test_connect_rsr_source_postgres_passes_connection_kwargs() -> None:
    connect = RecordingConnect()

    connect_rsr_source_postgres(_settings(), connect=connect)

    args, kwargs = connect.calls[0]
    assert args == ()
    assert kwargs["host"] == "rsr-db.local"
    assert kwargs["port"] == 5439
    assert kwargs["dbname"] == "readysetrentables"
    assert kwargs["user"] == "rsr_readonly"
    assert kwargs["password"] == "super-secret-rsr-password"
    assert kwargs["application_name"] == "daedalus_rsr_source_readonly"


def test_connect_rsr_source_postgres_returns_connection_object() -> None:
    expected_connection = FakeConnection()
    connect = RecordingConnect(connection=expected_connection)

    connection = connect_rsr_source_postgres(_settings(), connect=connect)

    assert connection is expected_connection


def test_connect_rsr_source_postgres_does_not_pass_password_bearing_dsn() -> None:
    connect = RecordingConnect()

    connect_rsr_source_postgres(_settings(), connect=connect)

    args, _kwargs = connect.calls[0]
    assert args == ()


def test_connect_rsr_source_postgres_failure_raises_safe_runtime_error() -> None:
    def failing_connect(*_args: Any, **_kwargs: Any) -> object:
        msg = "driver-level failure"
        raise OSError(msg)

    with pytest.raises(RuntimeError) as exc_info:
        connect_rsr_source_postgres(_settings(), connect=failing_connect)

    error_message = str(exc_info.value)
    assert "postgresql://rsr_readonly:***@rsr-db.local:5439/readysetrentables" in error_message
    assert "super-secret-rsr-password" not in error_message


def test_connect_rsr_source_postgres_does_not_execute_queries() -> None:
    expected_connection = FakeConnection()
    connect = RecordingConnect(connection=expected_connection)

    connection = connect_rsr_source_postgres(_settings(), connect=connect)

    assert connection.queries == []


def _settings() -> RsrSourcePostgresSettings:
    return RsrSourcePostgresSettings(
        host="rsr-db.local",
        port=5439,
        database="readysetrentables",
        user="rsr_readonly",
        password="super-secret-rsr-password",
    )
