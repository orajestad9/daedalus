from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import datetime, timezone
import re
from types import TracebackType
from typing import Any, Self

import pytest
from pytest import MonkeyPatch

import daedalus.domains.readysetrentables_reviews.source_readonly_repository as repository_module
from daedalus.domains.readysetrentables_reviews.source_extraction_models import (
    RsrSourceExtractionRequest,
    RsrSourceExtractionResult,
)
from daedalus.domains.readysetrentables_reviews.source_readonly_repository import (
    RsrSourceReadOnlyRepository,
    ensure_read_only_query,
)


@dataclass(frozen=True)
class ExecutedQuery:
    query: str
    params: dict[str, object]


class FakeCursor:
    def __init__(self, connection: "FakeConnection") -> None:
        self._connection = connection
        self._rows: list[Mapping[str, Any]] = []

    def __enter__(self) -> Self:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        _ = exc_type
        _ = exc
        _ = traceback

    def execute(self, query: str, params: Mapping[str, object]) -> None:
        if self._connection.on_execute is not None:
            self._connection.on_execute()
        self._connection.execute_calls.append(ExecutedQuery(query=query, params=dict(params)))
        self._rows = self._connection.next_rows()

    def fetchall(self) -> list[Mapping[str, Any]]:
        return self._rows


class FakeConnection:
    def __init__(
        self,
        results: list[list[Mapping[str, Any]]] | None = None,
        *,
        on_execute: Callable[[], None] | None = None,
    ) -> None:
        self.cursor_calls = 0
        self.cursor_kwargs: list[dict[str, object]] = []
        self.execute_calls: list[ExecutedQuery] = []
        self.commit_calls = 0
        self.rollback_calls = 0
        self._results = list(results or [])
        self.on_execute = on_execute

    def cursor(self, **kwargs: object) -> FakeCursor:
        self.cursor_calls += 1
        self.cursor_kwargs.append(dict(kwargs))
        return FakeCursor(self)

    def next_rows(self) -> list[Mapping[str, Any]]:
        if not self._results:
            return []
        return self._results.pop(0)

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


def test_extract_source_data_maps_rows_into_source_result() -> None:
    connection = _connection_with_rows()
    repository = RsrSourceReadOnlyRepository(connection)

    result = repository.extract_source_data(
        request=RsrSourceExtractionRequest(
            market_name="Synthetic Market",
            neighborhood_name="Synthetic District",
            property_type="House",
            max_reviews=5,
        )
    )

    assert isinstance(result, RsrSourceExtractionResult)
    assert result.source_name == "readysetrentables"
    assert result.source_version == "v0"
    assert result.metadata["extraction_mode"] == "read_only"
    assert result.metadata["repository"] == "RsrSourceReadOnlyRepository"

    review = result.reviews[0]
    assert review.review_id == "101"
    assert review.listing_id == "201"
    assert review.rating is None
    assert review.review_text == "Synthetic review text."
    assert review.created_at == datetime(2024, 1, 2, tzinfo=timezone.utc)
    assert review.metadata == {
        "source_table": "public.reviews",
        "market": "Synthetic Market",
        "market_id": "7",
    }

    listing = result.listings[0]
    assert listing.listing_id == "201"
    assert listing.listing_name == "Synthetic Listing"
    assert listing.property_type == "House"
    assert listing.bedrooms == 3
    assert listing.bathrooms == 2.5
    assert listing.accommodates == 6
    assert listing.average_rating == 4.8
    assert listing.metadata["room_type"] == "Entire home/apt"
    assert listing.metadata["review_scores_cleanliness"] == "4.9"

    assert result.neighborhood is not None
    assert result.neighborhood.market_name == "Synthetic Market Name"
    assert result.neighborhood.neighborhood_name == "Synthetic District"
    assert result.neighborhood.city is None
    assert result.neighborhood.metadata == {
        "market_id": "7",
        "market_key": "synthetic-market",
        "neighborhood_id": "301",
    }


def test_extract_source_data_executes_select_only_queries() -> None:
    connection = _connection_with_rows()

    RsrSourceReadOnlyRepository(connection).extract_source_data(request=_request())

    assert connection.execute_calls
    for call in connection.execute_calls:
        ensure_read_only_query(call.query)


def test_ensure_read_only_query_is_applied_before_execution(monkeypatch: MonkeyPatch) -> None:
    events: list[str] = []

    def fake_guard(query: str) -> None:
        _ = query
        events.append("guard")

    connection = _connection_with_rows(on_execute=lambda: events.append("execute"))
    monkeypatch.setattr(repository_module, "ensure_read_only_query", fake_guard)

    RsrSourceReadOnlyRepository(connection).extract_source_data(request=_request())

    assert events == ["guard", "execute", "guard", "execute", "guard", "execute"]


def test_guard_failure_prevents_execution(monkeypatch: MonkeyPatch) -> None:
    def fake_guard(query: str) -> None:
        _ = query
        raise ValueError("blocked")

    connection = _connection_with_rows()
    monkeypatch.setattr(repository_module, "ensure_read_only_query", fake_guard)

    with pytest.raises(ValueError, match="blocked"):
        RsrSourceReadOnlyRepository(connection).extract_source_data(request=_request())

    assert connection.execute_calls == []


def test_review_query_filters_are_parameterized() -> None:
    connection = _connection_with_rows()
    request = RsrSourceExtractionRequest(
        market_name="Synthetic Market",
        neighborhood_name="Synthetic District",
        property_type="House",
        max_reviews=3,
    )

    RsrSourceReadOnlyRepository(connection).extract_source_data(request=request)

    review_call = connection.execute_calls[0]
    assert "%(market_name)s" in review_call.query
    assert "%(neighborhood_name)s" in review_call.query
    assert "%(property_type)s" in review_call.query
    assert "LIMIT %(max_reviews)s" in review_call.query
    assert review_call.params["market_name"] == "Synthetic Market"
    assert review_call.params["neighborhood_name"] == "Synthetic District"
    assert review_call.params["property_type"] == "House"
    assert review_call.params["max_reviews"] == 3
    assert "Synthetic Market" not in review_call.query
    assert "Synthetic District" not in review_call.query
    assert "House" not in review_call.query


def test_listing_query_uses_selected_review_listing_ids_when_reviews_exist() -> None:
    connection = _connection_with_rows()

    RsrSourceReadOnlyRepository(connection).extract_source_data(request=_request(max_reviews=1))

    listing_call = connection.execute_calls[1]
    assert "ANY(%(listing_ids)s)" in listing_call.query
    assert listing_call.params["listing_ids"] == ["201"]
    assert listing_call.params["listing_limit"] == 1


def test_listing_query_falls_back_to_filtered_market_rows_when_no_reviews_exist() -> None:
    connection = _connection_with_rows(review_rows=[], neighborhood_rows=[])
    request = RsrSourceExtractionRequest(
        market_name="Synthetic Market",
        neighborhood_name="Synthetic District",
        property_type="House",
    )

    result = RsrSourceReadOnlyRepository(connection).extract_source_data(request=request)

    assert result.reviews == []
    assert result.listings[0].listing_id == "201"
    listing_call = connection.execute_calls[1]
    assert "l.market = %(market_name)s" in listing_call.query
    assert "l.neighbourhood = %(neighborhood_name)s" in listing_call.query
    assert "l.property_type = %(property_type)s" in listing_call.query
    assert listing_call.params["listing_limit"] == 25


def test_extract_source_data_handles_no_neighborhood_row() -> None:
    connection = _connection_with_rows(neighborhood_rows=[])

    result = RsrSourceReadOnlyRepository(connection).extract_source_data(request=_request())

    assert result.neighborhood is None


def test_sensitive_review_and_listing_fields_are_not_mapped_to_metadata() -> None:
    result = RsrSourceReadOnlyRepository(_connection_with_rows()).extract_source_data(
        request=_request()
    )

    assert "reviewer_name" not in result.reviews[0].metadata
    assert "listing_url" not in result.listings[0].metadata
    assert "latitude" not in result.listings[0].metadata
    assert "longitude" not in result.listings[0].metadata
    assert "price" not in result.listings[0].metadata
    assert "estimated_revenue_l365d" not in result.listings[0].metadata
    assert "estimated_occupancy_l365d" not in result.listings[0].metadata


def test_no_write_sql_is_executed_and_no_transaction_methods_are_called() -> None:
    connection = _connection_with_rows()

    RsrSourceReadOnlyRepository(connection).extract_source_data(request=_request())

    forbidden_words = ("insert", "update", "delete", "drop", "alter", "create", "truncate")
    for call in connection.execute_calls:
        lowered_query = call.query.lower()
        assert lowered_query.strip().startswith("select")
        assert all(re.search(rf"\b{word}\b", lowered_query) is None for word in forbidden_words)
    assert connection.commit_calls == 0
    assert connection.rollback_calls == 0


def test_raw_review_text_is_not_in_mapping_exception_message() -> None:
    connection = _connection_with_rows(
        review_rows=[
            {
                **_raw_review_row(),
                "review_id": "   ",
                "review_text": "Synthetic private review body should stay hidden.",
            }
        ]
    )

    with pytest.raises(RuntimeError) as exc_info:
        RsrSourceReadOnlyRepository(connection).extract_source_data(request=_request())

    assert "Synthetic private review body should stay hidden." not in str(exc_info.value)


def test_connection_is_not_opened_internally() -> None:
    connection = _connection_with_rows()
    repository = RsrSourceReadOnlyRepository(connection)

    repository.extract_source_data(request=_request())

    assert repository.connection is connection
    assert connection.cursor_calls == 3


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


def _connection_with_rows(
    *,
    review_rows: list[Mapping[str, Any]] | None = None,
    listing_rows: list[Mapping[str, Any]] | None = None,
    neighborhood_rows: list[Mapping[str, Any]] | None = None,
    on_execute: Callable[[], None] | None = None,
) -> FakeConnection:
    review_result: list[Mapping[str, Any]] = (
        [_raw_review_row()] if review_rows is None else review_rows
    )
    listing_result: list[Mapping[str, Any]] = (
        [_raw_listing_row()] if listing_rows is None else listing_rows
    )
    neighborhood_result: list[Mapping[str, Any]] = (
        [_raw_neighborhood_row()] if neighborhood_rows is None else neighborhood_rows
    )
    return FakeConnection(
        [review_result, listing_result, neighborhood_result],
        on_execute=on_execute,
    )


def _request(max_reviews: int | None = None) -> RsrSourceExtractionRequest:
    return RsrSourceExtractionRequest(market_name="Synthetic Market", max_reviews=max_reviews)


def _raw_review_row() -> dict[str, object]:
    return {
        "review_id": "101",
        "listing_id": "201",
        "rating": None,
        "review_text": "Synthetic review text.",
        "created_at": datetime(2024, 1, 2, tzinfo=timezone.utc),
        "market": "Synthetic Market",
        "market_id": 7,
        "reviewer_name": "Synthetic Person",
    }


def _raw_listing_row() -> dict[str, object]:
    return {
        "listing_id": "201",
        "listing_name": "Synthetic Listing",
        "property_type": "House",
        "bedrooms": 3,
        "bathrooms": 2.5,
        "accommodates": 6,
        "average_rating": 4.8,
        "room_type": "Entire home/apt",
        "neighbourhood": "Synthetic District",
        "market": "Synthetic Market",
        "market_id": 7,
        "review_scores_accuracy": 4.7,
        "review_scores_cleanliness": 4.9,
        "review_scores_checkin": 4.6,
        "review_scores_communication": 4.8,
        "review_scores_location": 4.5,
        "review_scores_value": 4.4,
        "listing_url": "https://example.invalid/private",
        "latitude": 30.0,
        "longitude": -97.0,
        "price": 999,
        "estimated_revenue_l365d": 12345,
        "estimated_occupancy_l365d": 0.42,
    }


def _raw_neighborhood_row() -> dict[str, object]:
    return {
        "market_name": "Synthetic Market Name",
        "neighborhood_name": "Synthetic District",
        "city": None,
        "state": None,
        "country": None,
        "market_id": 7,
        "market_key": "synthetic-market",
        "neighborhood_id": 301,
    }
