from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast
from uuid import UUID, uuid4

import psycopg
import pytest

from daedalus.memory.workflow_run_repository import WorkflowRunRepository
from daedalus.orchestrator.run_record import WorkflowRunRecord
from daedalus.orchestrator.status import WorkflowStatus


def test_workflow_run_repository_save_inserts_record_with_parameterized_sql() -> None:
    connection = FakeConnection()
    repository = WorkflowRunRepository(cast(psycopg.Connection[Any], connection))
    record = _workflow_run_record()

    repository.save(record)

    assert connection.executed_sql is not None
    assert "insert into workflow_runs" in connection.executed_sql.lower()
    assert "%s" in connection.executed_sql
    assert connection.params is not None
    assert connection.params[0] == record.run_id
    assert connection.params[3] == "completed"
    assert connection.params[6] == str(record.source_input_path)
    assert connection.params[10] == str(record.run_record_artifact_path)
    assert connection.params[11] == record.review_count
    assert connection.committed is False


def test_workflow_run_repository_get_by_run_id_maps_row_to_record() -> None:
    run_id = uuid4()
    row = _workflow_run_row(run_id)
    connection = FakeConnection(row=row)
    repository = WorkflowRunRepository(cast(psycopg.Connection[Any], connection))

    record = repository.get_by_run_id(run_id)

    assert record is not None
    assert connection.params == (run_id,)
    assert record.run_id == run_id
    assert record.workflow_name == "readysetrentables_review_normalization"
    assert record.domain == "readysetrentables_reviews"
    assert record.status == WorkflowStatus.COMPLETED
    assert record.source_input_path == Path("sample.csv")
    assert record.output_artifact_path == Path("normalized_reviews.json")
    assert record.metadata_artifact_path == Path("normalized_reviews.metadata.json")
    assert record.summary_artifact_path == Path("normalized_reviews.summary.md")
    assert record.run_record_artifact_path == Path("normalized_reviews.run.json")
    assert record.review_count == 8
    assert record.approval_required is True
    assert record.approved is True


def test_workflow_run_repository_get_by_run_id_returns_none_when_missing() -> None:
    run_id = uuid4()
    connection = FakeConnection(row=None)
    repository = WorkflowRunRepository(cast(psycopg.Connection[Any], connection))

    assert repository.get_by_run_id(run_id) is None


def test_workflow_run_repository_list_recent_uses_parameterized_sql() -> None:
    first_run_id = uuid4()
    second_run_id = uuid4()
    connection = FakeConnection(
        rows=[
            _workflow_run_row(first_run_id),
            _workflow_run_row(second_run_id),
        ],
    )
    repository = WorkflowRunRepository(cast(psycopg.Connection[Any], connection))

    records = repository.list_recent(
        limit=5,
        domain="readysetrentables_reviews",
        status="completed",
    )

    assert connection.executed_sql is not None
    sql = connection.executed_sql.lower()
    assert "from workflow_runs" in sql
    assert "domain = %s" in sql
    assert "status = %s" in sql
    assert "order by created_at_utc desc" in sql
    assert "limit %s" in sql
    assert connection.params == ("readysetrentables_reviews", "completed", 5)
    assert [record.run_id for record in records] == [first_run_id, second_run_id]


def test_workflow_run_repository_list_recent_rejects_invalid_limit() -> None:
    connection = FakeConnection()
    repository = WorkflowRunRepository(cast(psycopg.Connection[Any], connection))

    with pytest.raises(ValueError):
        repository.list_recent(limit=0)


class FakeCursor:
    def __init__(
        self,
        *,
        row: tuple[Any, ...] | None,
        rows: list[tuple[Any, ...]],
    ) -> None:
        self._row = row
        self._rows = rows

    def fetchone(self) -> tuple[Any, ...] | None:
        return self._row

    def fetchall(self) -> list[tuple[Any, ...]]:
        return self._rows


class FakeConnection:
    def __init__(
        self,
        row: tuple[Any, ...] | None = None,
        rows: list[tuple[Any, ...]] | None = None,
    ) -> None:
        self._row = row
        self._rows = rows or []
        self.executed_sql: str | None = None
        self.params: tuple[object, ...] | None = None
        self.committed = False

    def execute(self, sql: str, params: tuple[object, ...]) -> FakeCursor:
        self.executed_sql = sql
        self.params = params
        return FakeCursor(row=self._row, rows=self._rows)

    def commit(self) -> None:
        self.committed = True


def _workflow_run_record() -> WorkflowRunRecord:
    return WorkflowRunRecord(
        run_id=uuid4(),
        workflow_name="readysetrentables_review_normalization",
        domain="readysetrentables_reviews",
        status=WorkflowStatus.COMPLETED,
        started_at_utc=datetime(2026, 5, 7, 10, 0, tzinfo=UTC),
        completed_at_utc=datetime(2026, 5, 7, 10, 1, tzinfo=UTC),
        source_input_path=Path("sample.csv"),
        output_artifact_path=Path("normalized_reviews.json"),
        metadata_artifact_path=Path("normalized_reviews.metadata.json"),
        summary_artifact_path=Path("normalized_reviews.summary.md"),
        run_record_artifact_path=Path("normalized_reviews.run.json"),
        review_count=8,
        approval_required=True,
        approved=True,
    )


def _workflow_run_row(run_id: UUID) -> tuple[Any, ...]:
    return (
        run_id,
        "readysetrentables_review_normalization",
        "readysetrentables_reviews",
        "completed",
        datetime(2026, 5, 7, 10, 0, tzinfo=UTC),
        datetime(2026, 5, 7, 10, 1, tzinfo=UTC),
        "sample.csv",
        "normalized_reviews.json",
        "normalized_reviews.metadata.json",
        "normalized_reviews.summary.md",
        "normalized_reviews.run.json",
        8,
        True,
        True,
    )
