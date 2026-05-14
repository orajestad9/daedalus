import pytest

from daedalus.domains.readysetrentables_reviews.source_extraction_models import (
    RsrSourceExtractionRequest,
)
from daedalus.domains.readysetrentables_reviews.source_readonly_repository import (
    RsrSourceReadOnlyRepository,
    ensure_read_only_query,
)


class FakeConnection:
    def __init__(self) -> None:
        self.cursor_calls = 0
        self.execute_calls: list[str] = []
        self.commit_calls = 0
        self.rollback_calls = 0

    def cursor(self) -> "FakeConnection":
        self.cursor_calls += 1
        return self

    def execute(self, query: str) -> None:
        self.execute_calls.append(query)

    def commit(self) -> None:
        self.commit_calls += 1

    def rollback(self) -> None:
        self.rollback_calls += 1


def test_repository_stores_injected_connection() -> None:
    connection = FakeConnection()

    repository = RsrSourceReadOnlyRepository(connection)

    assert repository.connection is connection


def test_constructor_does_not_call_connection_methods() -> None:
    connection = FakeConnection()

    RsrSourceReadOnlyRepository(connection)

    assert connection.cursor_calls == 0
    assert connection.execute_calls == []
    assert connection.commit_calls == 0
    assert connection.rollback_calls == 0


def test_extract_source_data_raises_not_implemented() -> None:
    repository = RsrSourceReadOnlyRepository(FakeConnection())

    with pytest.raises(NotImplementedError, match="not implemented"):
        repository.extract_source_data(request=_request())


def test_extract_source_data_does_not_execute_sql() -> None:
    connection = FakeConnection()
    repository = RsrSourceReadOnlyRepository(connection)

    with pytest.raises(NotImplementedError):
        repository.extract_source_data(request=_request())

    assert connection.cursor_calls == 0
    assert connection.execute_calls == []
    assert connection.commit_calls == 0
    assert connection.rollback_calls == 0


def test_extract_source_data_error_message_is_safe() -> None:
    repository = RsrSourceReadOnlyRepository(FakeConnection())
    request = RsrSourceExtractionRequest(
        market_name="Synthetic Secret Market",
        neighborhood_name="Synthetic Private Neighborhood",
    )

    with pytest.raises(NotImplementedError) as exc_info:
        repository.extract_source_data(request=request)

    error_message = str(exc_info.value)
    assert "Synthetic Secret Market" not in error_message
    assert "Synthetic Private Neighborhood" not in error_message
    assert "Synthetic review text" not in error_message
    assert "super-secret" not in error_message


@pytest.mark.parametrize(
    "query",
    [
        "SELECT 1",
        "select 1",
        "  SELECT 1",
        "\n\tselect 1",
    ],
)
def test_ensure_read_only_query_allows_select(query: str) -> None:
    ensure_read_only_query(query)


@pytest.mark.parametrize(
    "query",
    [
        "WITH rows AS (SELECT 1) SELECT * FROM rows",
        "with rows as (select 1) select * from rows",
        "  WITH rows AS (SELECT 1) SELECT * FROM rows",
    ],
)
def test_ensure_read_only_query_allows_with(query: str) -> None:
    ensure_read_only_query(query)


@pytest.mark.parametrize(
    "query",
    [
        "INSERT INTO synthetic_table VALUES (1)",
        "UPDATE synthetic_table SET value = 1",
        "DELETE FROM synthetic_table",
        "DROP TABLE synthetic_table",
        "ALTER TABLE synthetic_table ADD COLUMN value integer",
        "CREATE TABLE synthetic_table (id integer)",
        "TRUNCATE synthetic_table",
        "COPY synthetic_table TO STDOUT",
    ],
)
def test_ensure_read_only_query_rejects_write_or_schema_queries(query: str) -> None:
    with pytest.raises(ValueError, match="SELECT or WITH|non-read-only"):
        ensure_read_only_query(query)


def test_ensure_read_only_query_rejects_forbidden_keyword_case_insensitively() -> None:
    with pytest.raises(ValueError, match="non-read-only"):
        ensure_read_only_query("select * from synthetic_table for update")


def test_ensure_read_only_query_handles_leading_whitespace() -> None:
    ensure_read_only_query("   \n\tSELECT 1")


def test_ensure_read_only_query_rejects_empty_query() -> None:
    with pytest.raises(ValueError, match="must not be empty"):
        ensure_read_only_query("   ")


def _request() -> RsrSourceExtractionRequest:
    return RsrSourceExtractionRequest(market_name="Synthetic Market")
