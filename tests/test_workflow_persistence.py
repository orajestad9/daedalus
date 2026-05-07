from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID, uuid4

import pytest

from daedalus.config import PostgresSettings
from daedalus.domains.readysetrentables_reviews.workflow import (
    ReviewNormalizationWorkflowResult,
)
from daedalus.memory.workflow_persistence import (
    WorkflowPersistenceError,
    persist_review_normalization_workflow_result,
)
from daedalus.orchestrator.run_record import (
    WorkflowRunRecord,
    write_workflow_run_record_json,
)
from daedalus.orchestrator.status import WorkflowStatus


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
    assert len(connection.executed_sql) == 5
    assert connection.committed is True
    assert connection.rolled_back is False
    assert connection.closed is True


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


class FakeConnection:
    def __init__(self, *, fail_on_execute: bool = False) -> None:
        self._fail_on_execute = fail_on_execute
        self.executed_sql: list[str] = []
        self.committed = False
        self.rolled_back = False
        self.closed = False

    def execute(self, sql: str, params: tuple[object, ...]) -> None:
        self.executed_sql.append(sql)
        if self._fail_on_execute:
            msg = "simulated persistence failure"
            raise RuntimeError(msg)

    def commit(self) -> None:
        self.committed = True

    def rollback(self) -> None:
        self.rolled_back = True

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
