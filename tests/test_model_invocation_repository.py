from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any, cast
from uuid import UUID, uuid4

import psycopg

from daedalus.memory.model_invocation_repository import ModelInvocationRepository
from daedalus.model_clients.invocation_record import (
    ModelInvocationRecord,
    ModelInvocationStatus,
)
from daedalus.model_clients.types import ModelProvider


def test_model_invocation_repository_save_uses_parameterized_sql() -> None:
    connection = FakeConnection()
    repository = ModelInvocationRepository(cast(psycopg.Connection[Any], connection))
    record = _model_invocation_record()

    repository.save(record)

    assert connection.executed_sql is not None
    assert "insert into model_invocations" in connection.executed_sql.lower()
    assert "%s" in connection.executed_sql
    assert connection.params is not None
    assert connection.committed is False


def test_model_invocation_repository_save_maps_all_fields() -> None:
    connection = FakeConnection()
    repository = ModelInvocationRepository(cast(psycopg.Connection[Any], connection))
    record = _model_invocation_record()

    repository.save(record)

    assert connection.params == (
        record.invocation_id,
        record.run_id,
        record.step_id,
        record.agent_name,
        "fake",
        record.model_name,
        record.prompt_name,
        record.prompt_version,
        record.input_tokens,
        record.output_tokens,
        record.total_tokens,
        record.estimated_cost_usd,
        "succeeded",
        record.started_at_utc,
        record.completed_at_utc,
        record.duration_ms,
        str(record.input_artifact_path),
        str(record.output_artifact_path),
        record.error_message,
    )


def test_model_invocation_repository_save_does_not_insert_raw_prompt_or_response() -> None:
    connection = FakeConnection()
    repository = ModelInvocationRepository(cast(psycopg.Connection[Any], connection))

    repository.save(_model_invocation_record())

    assert connection.executed_sql is not None
    sql = connection.executed_sql.lower()
    assert "raw_prompt" not in sql
    assert "raw_response" not in sql
    assert "input_text" not in sql
    assert "output_text" not in sql


def test_model_invocation_repository_list_for_run_queries_by_run_id() -> None:
    run_id = uuid4()
    connection = FakeConnection(rows=[_model_invocation_row(run_id=run_id)])
    repository = ModelInvocationRepository(cast(psycopg.Connection[Any], connection))

    repository.list_for_run(run_id)

    assert connection.params == (run_id,)
    assert connection.executed_sql is not None
    sql = connection.executed_sql.lower()
    assert "from model_invocations" in sql
    assert "where run_id = %s" in sql
    assert "order by started_at_utc asc" in sql


def test_model_invocation_repository_list_for_run_maps_rows_to_records() -> None:
    run_id = uuid4()
    invocation_id = uuid4()
    step_id = uuid4()
    rows = [
        _model_invocation_row(
            invocation_id=invocation_id,
            run_id=run_id,
            step_id=step_id,
            provider="fake",
            status="succeeded",
        )
    ]
    connection = FakeConnection(rows=rows)
    repository = ModelInvocationRepository(cast(psycopg.Connection[Any], connection))

    records = repository.list_for_run(run_id)

    assert len(records) == 1
    record = records[0]
    assert record.invocation_id == invocation_id
    assert record.run_id == run_id
    assert record.step_id == step_id
    assert record.agent_name == "review_summarizer"
    assert record.provider == ModelProvider.FAKE
    assert record.model_name == "fake-local-model"
    assert record.prompt_name == "summarize_reviews"
    assert record.prompt_version == "v1"
    assert record.input_tokens == 10
    assert record.output_tokens == 5
    assert record.total_tokens == 15
    assert record.estimated_cost_usd == Decimal("0.001")
    assert record.status == ModelInvocationStatus.SUCCEEDED
    assert record.input_artifact_path == Path("artifacts/input.json")
    assert record.output_artifact_path == Path("artifacts/output.json")
    assert record.error_message is None


def test_model_invocation_repository_list_for_step_queries_by_step_id() -> None:
    step_id = uuid4()
    connection = FakeConnection(rows=[_model_invocation_row(step_id=step_id)])
    repository = ModelInvocationRepository(cast(psycopg.Connection[Any], connection))

    repository.list_for_step(step_id)

    assert connection.params == (step_id,)
    assert connection.executed_sql is not None
    sql = connection.executed_sql.lower()
    assert "from model_invocations" in sql
    assert "where step_id = %s" in sql
    assert "order by started_at_utc asc" in sql


class FakeCursor:
    def __init__(self, rows: list[tuple[Any, ...]]) -> None:
        self._rows = rows

    def fetchall(self) -> list[tuple[Any, ...]]:
        return self._rows


class FakeConnection:
    def __init__(self, rows: list[tuple[Any, ...]] | None = None) -> None:
        self._rows = rows or []
        self.executed_sql: str | None = None
        self.params: tuple[object, ...] | None = None
        self.committed = False

    def execute(self, sql: str, params: tuple[object, ...]) -> FakeCursor:
        self.executed_sql = sql
        self.params = params
        return FakeCursor(self._rows)

    def commit(self) -> None:
        self.committed = True


def _model_invocation_record() -> ModelInvocationRecord:
    return ModelInvocationRecord(
        invocation_id=uuid4(),
        run_id=uuid4(),
        step_id=uuid4(),
        agent_name="review_summarizer",
        provider=ModelProvider.FAKE,
        model_name="fake-local-model",
        prompt_name="summarize_reviews",
        prompt_version="v1",
        input_tokens=10,
        output_tokens=5,
        total_tokens=15,
        estimated_cost_usd=Decimal("0.001"),
        status=ModelInvocationStatus.SUCCEEDED,
        started_at_utc=datetime(2026, 5, 8, 10, 0, tzinfo=UTC),
        completed_at_utc=datetime(2026, 5, 8, 10, 0, 1, tzinfo=UTC),
        duration_ms=1_000,
        input_artifact_path=Path("artifacts/input.json"),
        output_artifact_path=Path("artifacts/output.json"),
        error_message=None,
    )


def _model_invocation_row(
    *,
    invocation_id: UUID | None = None,
    run_id: UUID | None = None,
    step_id: UUID | None = None,
    provider: str = "fake",
    status: str = "succeeded",
) -> tuple[Any, ...]:
    return (
        invocation_id or uuid4(),
        run_id or uuid4(),
        step_id,
        "review_summarizer",
        provider,
        "fake-local-model",
        "summarize_reviews",
        "v1",
        10,
        5,
        15,
        Decimal("0.001"),
        status,
        datetime(2026, 5, 8, 10, 0, tzinfo=UTC),
        datetime(2026, 5, 8, 10, 0, 1, tzinfo=UTC),
        1_000,
        "artifacts/input.json",
        "artifacts/output.json",
        None,
    )
