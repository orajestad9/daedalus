from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID, uuid4

from daedalus.orchestrator.artifact_record import ArtifactRecord
from daedalus.orchestrator.artifact_type import ArtifactType
from daedalus.orchestrator.run_inspection_formatter import format_run_inspection
from daedalus.orchestrator.run_record import WorkflowRunRecord
from daedalus.orchestrator.status import WorkflowStatus
from daedalus.orchestrator.step_record import WorkflowStepRecord


def test_format_run_inspection_includes_run_details() -> None:
    record = _workflow_run_record()

    output = format_run_inspection(record=record, artifacts=[], steps=[])

    assert str(record.run_id) in output
    assert "workflow_name: readysetrentables_review_normalization" in output
    assert "domain: readysetrentables_reviews" in output
    assert "status: completed" in output
    assert "duration_ms: 60000" in output
    assert "review_count: 8" in output
    assert "run_record_artifact_path: normalized_reviews.run.json" in output


def test_format_run_inspection_includes_artifact_records() -> None:
    record = _workflow_run_record()

    output = format_run_inspection(
        record=record,
        artifacts=[
            ArtifactRecord.create(
                run_id=record.run_id,
                artifact_type=ArtifactType.NORMALIZED_REVIEWS,
                artifact_path=Path("normalized_reviews.json"),
            )
        ],
        steps=[],
    )

    assert "- normalized_reviews: normalized_reviews.json" in output


def test_format_run_inspection_includes_workflow_steps() -> None:
    record = _workflow_run_record()

    output = format_run_inspection(
        record=record,
        artifacts=[],
        steps=[
            _workflow_step_record(
                run_id=record.run_id,
                step_name="load_reviews",
                status=WorkflowStatus.COMPLETED,
                duration_ms=50,
            )
        ],
    )

    assert "steps:" in output
    assert "- load_reviews: status=completed duration_ms=50" in output


def test_format_run_inspection_includes_empty_messages() -> None:
    output = format_run_inspection(record=_workflow_run_record(), artifacts=[], steps=[])

    assert "No artifact records found." in output
    assert "No workflow steps recorded." in output


def test_format_run_inspection_includes_failed_step_error_message() -> None:
    record = _workflow_run_record()

    output = format_run_inspection(
        record=record,
        artifacts=[],
        steps=[
            _workflow_step_record(
                run_id=record.run_id,
                step_name="write_artifact",
                status=WorkflowStatus.FAILED,
                duration_ms=75,
                error_message="write failed",
            )
        ],
    )

    assert "- write_artifact: status=failed duration_ms=75 error_message=write failed" in output


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
    run_id: UUID,
    step_name: str,
    status: WorkflowStatus,
    duration_ms: int,
    error_message: str | None = None,
) -> WorkflowStepRecord:
    return WorkflowStepRecord(
        step_id=uuid4(),
        run_id=run_id,
        step_name=step_name,
        status=status,
        started_at_utc=datetime(2026, 5, 7, 10, 0, tzinfo=UTC),
        completed_at_utc=datetime(2026, 5, 7, 10, 1, tzinfo=UTC),
        duration_ms=duration_ms,
        error_message=error_message,
    )
