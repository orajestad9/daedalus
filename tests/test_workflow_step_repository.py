from datetime import UTC, datetime
from typing import Any, cast
from uuid import UUID, uuid4

import psycopg

from daedalus.memory.workflow_step_repository import WorkflowStepRepository
from daedalus.orchestrator.status import WorkflowStatus
from daedalus.orchestrator.step_record import WorkflowStepRecord


def test_workflow_step_repository_save_uses_parameterized_sql() -> None:
    connection = FakeConnection()
    repository = WorkflowStepRepository(cast(psycopg.Connection[Any], connection))
    record = _workflow_step_record()

    repository.save(record)

    assert connection.executed_sql is not None
    assert "insert into workflow_steps" in connection.executed_sql.lower()
    assert "%s" in connection.executed_sql
    assert connection.params is not None
    assert connection.params[0] == record.step_id
    assert connection.params[1] == record.run_id
    assert connection.params[2] == record.step_name
    assert connection.params[3] == "completed"
    assert connection.params[4] == record.started_at_utc
    assert connection.params[5] == record.completed_at_utc
    assert connection.params[6] == record.duration_ms
    assert connection.params[7] == record.error_message
    assert connection.committed is False


def test_workflow_step_repository_list_for_run_queries_by_run_id() -> None:
    run_id = uuid4()
    rows = [_workflow_step_row(run_id=run_id, step_name="load_csv")]
    connection = FakeConnection(rows=rows)
    repository = WorkflowStepRepository(cast(psycopg.Connection[Any], connection))

    repository.list_for_run(run_id)

    assert connection.params == (run_id,)
    assert connection.executed_sql is not None
    sql = connection.executed_sql.lower()
    assert "from workflow_steps" in sql
    assert "where run_id = %s" in sql
    assert "order by started_at_utc asc" in sql


def test_workflow_step_repository_list_for_run_maps_rows_to_records() -> None:
    run_id = uuid4()
    first_step_id = uuid4()
    second_step_id = uuid4()
    rows = [
        _workflow_step_row(
            step_id=first_step_id,
            run_id=run_id,
            step_name="load_csv",
            status="completed",
            duration_ms=50,
        ),
        _workflow_step_row(
            step_id=second_step_id,
            run_id=run_id,
            step_name="write_artifact",
            status="failed",
            duration_ms=75,
            error_message="write failed",
        ),
    ]
    connection = FakeConnection(rows=rows)
    repository = WorkflowStepRepository(cast(psycopg.Connection[Any], connection))

    records = repository.list_for_run(run_id)

    assert [record.step_id for record in records] == [first_step_id, second_step_id]
    assert [record.run_id for record in records] == [run_id, run_id]
    assert records[0].step_name == "load_csv"
    assert records[0].status == WorkflowStatus.COMPLETED
    assert records[0].duration_ms == 50
    assert records[0].error_message is None
    assert records[1].step_name == "write_artifact"
    assert records[1].status == WorkflowStatus.FAILED
    assert records[1].duration_ms == 75
    assert records[1].error_message == "write failed"


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


def _workflow_step_record() -> WorkflowStepRecord:
    return WorkflowStepRecord(
        step_id=uuid4(),
        run_id=uuid4(),
        step_name="load_csv",
        status=WorkflowStatus.COMPLETED,
        started_at_utc=datetime(2026, 5, 7, 10, 0, tzinfo=UTC),
        completed_at_utc=datetime(2026, 5, 7, 10, 0, 1, tzinfo=UTC),
        duration_ms=1_000,
        error_message=None,
    )


def _workflow_step_row(
    *,
    run_id: UUID,
    step_name: str,
    step_id: UUID | None = None,
    status: str = "completed",
    duration_ms: int | None = 1_000,
    error_message: str | None = None,
) -> tuple[Any, ...]:
    return (
        step_id or uuid4(),
        run_id,
        step_name,
        status,
        datetime(2026, 5, 7, 10, 0, tzinfo=UTC),
        datetime(2026, 5, 7, 10, 0, 1, tzinfo=UTC),
        duration_ms,
        error_message,
    )
