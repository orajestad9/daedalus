from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from uuid import UUID, uuid4

import pytest

from daedalus.config import PostgresSettings
from daedalus.domains.readysetrentables_reviews.workflow import (
    ReviewNormalizationWorkflowResult,
)
from daedalus.memory.workflow_persistence import (
    WorkflowPersistenceError,
    load_workflow_run_details,
    persist_review_normalization_workflow_result,
)
from daedalus.model_clients.invocation_record import ModelInvocationStatus
from daedalus.model_clients.types import ModelProvider
from daedalus.orchestrator.artifact_type import ArtifactType
from daedalus.orchestrator.run_record import (
    WorkflowRunRecord,
    write_workflow_run_record_json,
)
from daedalus.orchestrator.status import WorkflowStatus
from daedalus.orchestrator.step_record import WorkflowStepRecord


def test_persist_review_normalization_workflow_result_commits_transaction(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    connection = FakeConnection()
    result = _workflow_result(tmp_path)
    monkeypatch.setattr(
        "daedalus.memory.workflow_persistence.load_postgres_settings",
        _postgres_settings,
    )
    monkeypatch.setattr(
        "daedalus.memory.workflow_persistence.connect_postgres",
        lambda _: connection,
    )

    artifact_count = persist_review_normalization_workflow_result(result)

    assert artifact_count == 4
    assert len(connection.executed_sql) == 7
    assert _insert_count(connection.executed_sql, "workflow_steps") == 2
    assert connection.committed is True
    assert connection.rolled_back is False
    assert connection.closed is True


def test_persist_review_normalization_workflow_result_persists_review_theme_summary(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    connection = FakeConnection()
    result = _workflow_result(tmp_path).model_copy(
        update={
            "review_theme_summary_markdown_path": tmp_path / "review_theme_summary.md",
        }
    )
    monkeypatch.setattr(
        "daedalus.memory.workflow_persistence.load_postgres_settings",
        _postgres_settings,
    )
    monkeypatch.setattr(
        "daedalus.memory.workflow_persistence.connect_postgres",
        lambda _: connection,
    )

    artifact_count = persist_review_normalization_workflow_result(result)

    assert artifact_count == 5
    assert _insert_count(connection.executed_sql, "workflow_artifacts") == 5
    assert any(
        params[2] == ArtifactType.REVIEW_THEME_SUMMARY.value
        and params[3] == str(tmp_path / "review_theme_summary.md")
        for params in connection.executed_params
    )


def test_persist_review_normalization_workflow_result_rolls_back_on_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    connection = FakeConnection(fail_on_execute=True)
    result = _workflow_result(tmp_path)
    monkeypatch.setattr(
        "daedalus.memory.workflow_persistence.load_postgres_settings",
        _postgres_settings,
    )
    monkeypatch.setattr(
        "daedalus.memory.workflow_persistence.connect_postgres",
        lambda _: connection,
    )

    with pytest.raises(WorkflowPersistenceError):
        persist_review_normalization_workflow_result(result)

    assert connection.committed is False
    assert connection.rolled_back is True
    assert connection.closed is True


def test_load_workflow_run_details_includes_model_invocations(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    run_id = uuid4()
    connection = FakeReadConnection(run_id=run_id)
    monkeypatch.setattr(
        "daedalus.memory.workflow_persistence.load_postgres_settings",
        _postgres_settings,
    )
    monkeypatch.setattr(
        "daedalus.memory.workflow_persistence.connect_postgres",
        lambda _: connection,
    )

    details = load_workflow_run_details(run_id)

    assert details.run_record.run_id == run_id
    assert len(details.artifact_records) == 1
    assert len(details.step_records) == 1
    assert len(details.model_invocation_records) == 1
    invocation = details.model_invocation_records[0]
    assert invocation.provider == ModelProvider.FAKE
    assert invocation.status == ModelInvocationStatus.SUCCEEDED
    assert any("from model_invocations" in sql.lower() for sql in connection.executed_sql)
    assert connection.closed is True


class FakeConnection:
    def __init__(self, *, fail_on_execute: bool = False) -> None:
        self._fail_on_execute = fail_on_execute
        self.executed_sql: list[str] = []
        self.executed_params: list[tuple[object, ...]] = []
        self.committed = False
        self.rolled_back = False
        self.closed = False

    def execute(self, sql: str, params: tuple[object, ...]) -> None:
        self.executed_sql.append(sql)
        self.executed_params.append(params)
        if self._fail_on_execute:
            msg = "simulated persistence failure"
            raise RuntimeError(msg)

    def commit(self) -> None:
        self.committed = True

    def rollback(self) -> None:
        self.rolled_back = True

    def close(self) -> None:
        self.closed = True


class FakeReadCursor:
    def __init__(
        self,
        *,
        row: tuple[object, ...] | None = None,
        rows: list[tuple[object, ...]] | None = None,
    ) -> None:
        self._row = row
        self._rows = rows or []

    def fetchone(self) -> tuple[object, ...] | None:
        return self._row

    def fetchall(self) -> list[tuple[object, ...]]:
        return self._rows


class FakeReadConnection:
    def __init__(self, *, run_id: UUID) -> None:
        self._run_id = run_id
        self.executed_sql: list[str] = []
        self.closed = False

    def execute(self, sql: str, params: tuple[object, ...]) -> FakeReadCursor:
        self.executed_sql.append(sql)
        lower_sql = sql.lower()
        if "from workflow_runs" in lower_sql:
            return FakeReadCursor(row=_workflow_run_row(self._run_id))
        if "from workflow_artifacts" in lower_sql:
            return FakeReadCursor(rows=[_artifact_row(self._run_id)])
        if "from workflow_steps" in lower_sql:
            return FakeReadCursor(rows=[_workflow_step_row(self._run_id)])
        if "from model_invocations" in lower_sql:
            return FakeReadCursor(rows=[_model_invocation_row(self._run_id)])

        msg = f"Unexpected SQL in fake read connection: {sql}"
        raise AssertionError(msg)

    def close(self) -> None:
        self.closed = True


def _workflow_result(tmp_path: Path) -> ReviewNormalizationWorkflowResult:
    run_id = uuid4()
    output_path = tmp_path / "normalized_reviews.json"
    metadata_path = tmp_path / "normalized_reviews.metadata.json"
    summary_path = tmp_path / "normalized_reviews.summary.md"
    run_record_path = tmp_path / "normalized_reviews.run.json"
    _write_run_record(
        run_id=run_id,
        run_record_path=run_record_path,
        output_path=output_path,
        metadata_path=metadata_path,
        summary_path=summary_path,
    )
    return ReviewNormalizationWorkflowResult(
        source_csv_path=Path("sample.csv"),
        output_json_path=output_path,
        metadata_json_path=metadata_path,
        summary_markdown_path=summary_path,
        run_record_json_path=run_record_path,
        review_count=8,
        run_id=run_id,
        approval_required=False,
        approved=False,
        steps=[
            _workflow_step_record(run_id=run_id, step_name="load_reviews"),
            _workflow_step_record(run_id=run_id, step_name="write_normalized_artifact"),
        ],
    )


def _write_run_record(
    *,
    run_id: UUID,
    run_record_path: Path,
    output_path: Path,
    metadata_path: Path,
    summary_path: Path,
) -> None:
    record = WorkflowRunRecord(
        run_id=run_id,
        workflow_name="readysetrentables_review_normalization",
        domain="readysetrentables_reviews",
        status=WorkflowStatus.COMPLETED,
        started_at_utc=datetime(2026, 5, 7, 10, 0, tzinfo=UTC),
        completed_at_utc=datetime(2026, 5, 7, 10, 1, tzinfo=UTC),
        source_input_path=Path("sample.csv"),
        output_artifact_path=output_path,
        metadata_artifact_path=metadata_path,
        summary_artifact_path=summary_path,
        run_record_artifact_path=run_record_path,
        duration_ms=60_000,
        review_count=8,
        approval_required=False,
        approved=False,
    )
    write_workflow_run_record_json(record, run_record_path)


def _postgres_settings() -> PostgresSettings:
    return PostgresSettings(
        host="placeholder-host",
        port=5433,
        database="placeholder-db",
        user="placeholder-user",
        password="placeholder-password",
    )


def _insert_count(executed_sql: list[str], table_name: str) -> int:
    return sum(1 for sql in executed_sql if f"insert into {table_name}" in sql.lower())


def _workflow_step_record(
    *,
    run_id: UUID,
    step_name: str,
) -> WorkflowStepRecord:
    return WorkflowStepRecord(
        step_id=uuid4(),
        run_id=run_id,
        step_name=step_name,
        status=WorkflowStatus.COMPLETED,
        started_at_utc=datetime(2026, 5, 7, 10, 0, tzinfo=UTC),
        completed_at_utc=datetime(2026, 5, 7, 10, 1, tzinfo=UTC),
        duration_ms=60_000,
        error_message=None,
    )


def _workflow_run_row(run_id: UUID) -> tuple[object, ...]:
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
        60_000,
        8,
        False,
        False,
    )


def _artifact_row(run_id: UUID) -> tuple[object, ...]:
    return (
        uuid4(),
        run_id,
        ArtifactType.NORMALIZED_REVIEWS.value,
        "normalized_reviews.json",
        datetime(2026, 5, 7, 10, 1, tzinfo=UTC),
    )


def _workflow_step_row(run_id: UUID) -> tuple[object, ...]:
    return (
        uuid4(),
        run_id,
        "load_reviews",
        "completed",
        datetime(2026, 5, 7, 10, 0, tzinfo=UTC),
        datetime(2026, 5, 7, 10, 0, 1, tzinfo=UTC),
        1_000,
        None,
    )


def _model_invocation_row(run_id: UUID) -> tuple[object, ...]:
    return (
        uuid4(),
        run_id,
        uuid4(),
        "review_summarizer",
        "fake",
        "fake-local-model",
        "summarize_reviews",
        "v1",
        10,
        5,
        15,
        Decimal("0.001"),
        "succeeded",
        datetime(2026, 5, 7, 10, 0, tzinfo=UTC),
        datetime(2026, 5, 7, 10, 0, 1, tzinfo=UTC),
        1_000,
        "artifacts/input.json",
        "artifacts/output.json",
        None,
    )
