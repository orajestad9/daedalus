from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast
from uuid import uuid4

import pytest

from daedalus.memory.artifact_repository import ArtifactRepository
from daedalus.memory.workflow_persistence import WorkflowPersistenceService
from daedalus.memory.workflow_run_repository import WorkflowRunRepository
from daedalus.memory.workflow_step_repository import WorkflowStepRepository
from daedalus.orchestrator.artifact_record import ArtifactRecord
from daedalus.orchestrator.artifact_type import ArtifactType
from daedalus.orchestrator.run_record import WorkflowRunRecord
from daedalus.orchestrator.status import WorkflowStatus
from daedalus.orchestrator.step_record import WorkflowStepRecord


def test_save_review_normalization_run_saves_run_and_artifacts() -> None:
    run_repository = FakeWorkflowRunRepository()
    artifact_repository = FakeArtifactRepository()
    service = WorkflowPersistenceService(
        workflow_run_repository=cast(WorkflowRunRepository, run_repository),
        artifact_repository=cast(ArtifactRepository, artifact_repository),
    )
    record = _workflow_run_record()

    artifact_records = service.save_review_normalization_run(record)

    assert run_repository.saved_records == [record]
    assert artifact_repository.saved_records == artifact_records
    assert len(artifact_records) == 4


def test_save_review_normalization_run_creates_expected_artifact_types() -> None:
    service = WorkflowPersistenceService(
        workflow_run_repository=cast(WorkflowRunRepository, FakeWorkflowRunRepository()),
        artifact_repository=cast(ArtifactRepository, FakeArtifactRepository()),
    )

    artifact_records = service.save_review_normalization_run(_workflow_run_record())

    assert [record.artifact_type for record in artifact_records] == [
        ArtifactType.NORMALIZED_REVIEWS,
        ArtifactType.REVIEW_METADATA,
        ArtifactType.WORKFLOW_SUMMARY,
        ArtifactType.WORKFLOW_RUN_RECORD,
    ]


def test_save_review_normalization_run_saves_all_steps_when_repository_configured() -> None:
    step_repository = FakeWorkflowStepRepository()
    service = WorkflowPersistenceService(
        workflow_run_repository=cast(WorkflowRunRepository, FakeWorkflowRunRepository()),
        artifact_repository=cast(ArtifactRepository, FakeArtifactRepository()),
        workflow_step_repository=cast(WorkflowStepRepository, step_repository),
    )
    record = _workflow_run_record()
    steps = [
        _workflow_step_record(run_id=record.run_id, step_name="load_csv"),
        _workflow_step_record(run_id=record.run_id, step_name="write_artifacts"),
    ]

    service.save_review_normalization_run(record, steps=steps)

    assert step_repository.saved_records == steps


def test_save_review_normalization_run_rejects_steps_without_step_repository() -> None:
    service = WorkflowPersistenceService(
        workflow_run_repository=cast(WorkflowRunRepository, FakeWorkflowRunRepository()),
        artifact_repository=cast(ArtifactRepository, FakeArtifactRepository()),
    )
    record = _workflow_run_record()
    steps = [_workflow_step_record(run_id=record.run_id, step_name="load_csv")]

    with pytest.raises(ValueError, match="WorkflowStepRepository"):
        service.save_review_normalization_run(record, steps=steps)


class FakeWorkflowRunRepository:
    def __init__(self) -> None:
        self.saved_records: list[WorkflowRunRecord] = []

    def save(self, record: WorkflowRunRecord) -> None:
        self.saved_records.append(record)


class FakeArtifactRepository:
    def __init__(self) -> None:
        self.saved_records: list[ArtifactRecord] = []

    def save(self, record: ArtifactRecord) -> None:
        self.saved_records.append(record)


class FakeWorkflowStepRepository:
    def __init__(self) -> None:
        self.saved_records: list[WorkflowStepRecord] = []

    def save(self, record: WorkflowStepRecord) -> None:
        self.saved_records.append(record)


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
        duration_ms=60_000,
        review_count=8,
        approval_required=False,
        approved=False,
    )


def _workflow_step_record(
    *,
    run_id: Any,
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
