from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast
from uuid import UUID, uuid4

import psycopg

from daedalus.memory.artifact_repository import ArtifactRepository
from daedalus.orchestrator.artifact_record import ArtifactRecord
from daedalus.orchestrator.artifact_type import ArtifactType


def test_artifact_repository_save_inserts_record_with_parameterized_sql() -> None:
    connection = FakeConnection()
    repository = ArtifactRepository(cast(psycopg.Connection[Any], connection))
    record = _artifact_record()

    repository.save(record)

    assert connection.executed_sql is not None
    assert "insert into workflow_artifacts" in connection.executed_sql.lower()
    assert "%s" in connection.executed_sql
    assert connection.params is not None
    assert connection.params[0] == record.artifact_id
    assert connection.params[1] == record.run_id
    assert connection.params[2] == "workflow_summary"
    assert connection.params[3] == str(record.artifact_path)
    assert connection.params[4] == record.created_at_utc
    assert connection.committed is False


def test_artifact_repository_list_for_run_maps_rows_to_records() -> None:
    run_id = uuid4()
    first_artifact_id = uuid4()
    second_artifact_id = uuid4()
    rows = [
        _artifact_row(
            artifact_id=first_artifact_id,
            run_id=run_id,
            artifact_type="normalized_reviews",
            artifact_path="normalized_reviews.json",
        ),
        _artifact_row(
            artifact_id=second_artifact_id,
            run_id=run_id,
            artifact_type="workflow_summary",
            artifact_path="normalized_reviews.summary.md",
        ),
    ]
    connection = FakeConnection(rows=rows)
    repository = ArtifactRepository(cast(psycopg.Connection[Any], connection))

    records = repository.list_for_run(run_id)

    assert connection.params == (run_id,)
    assert connection.executed_sql is not None
    assert "order by created_at_utc asc" in connection.executed_sql.lower()
    assert [record.artifact_id for record in records] == [first_artifact_id, second_artifact_id]
    assert [record.run_id for record in records] == [run_id, run_id]
    assert records[0].artifact_type == ArtifactType.NORMALIZED_REVIEWS
    assert records[0].artifact_path == Path("normalized_reviews.json")
    assert records[1].artifact_type == ArtifactType.WORKFLOW_SUMMARY
    assert records[1].artifact_path == Path("normalized_reviews.summary.md")


def test_artifact_repository_list_for_run_returns_empty_list_when_missing() -> None:
    run_id = uuid4()
    connection = FakeConnection(rows=[])
    repository = ArtifactRepository(cast(psycopg.Connection[Any], connection))

    assert repository.list_for_run(run_id) == []


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


def _artifact_record() -> ArtifactRecord:
    return ArtifactRecord(
        artifact_id=uuid4(),
        run_id=uuid4(),
        artifact_type=ArtifactType.WORKFLOW_SUMMARY,
        artifact_path=Path("normalized_reviews.summary.md"),
        created_at_utc=datetime(2026, 5, 7, 10, 0, tzinfo=UTC),
    )


def _artifact_row(
    *,
    artifact_id: UUID,
    run_id: UUID,
    artifact_type: str,
    artifact_path: str,
) -> tuple[Any, ...]:
    return (
        artifact_id,
        run_id,
        artifact_type,
        artifact_path,
        datetime(2026, 5, 7, 10, 0, tzinfo=UTC),
    )
