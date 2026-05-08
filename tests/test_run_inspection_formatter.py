from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from uuid import UUID, uuid4

from daedalus.model_clients.invocation_record import (
    ModelInvocationRecord,
    ModelInvocationStatus,
)
from daedalus.model_clients.types import ModelProvider
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
    assert "No model invocations recorded." in output


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


def test_format_run_inspection_includes_model_invocation_records() -> None:
    record = _workflow_run_record()

    output = format_run_inspection(
        record=record,
        artifacts=[],
        steps=[],
        model_invocations=[
            _model_invocation_record(
                run_id=record.run_id,
                status=ModelInvocationStatus.SUCCEEDED,
            )
        ],
    )

    assert "Model Invocations:" in output
    assert "provider=fake" in output
    assert "model_name=fake-local-model" in output
    assert "prompt_name=summarize_reviews" in output
    assert "prompt_version=v1" in output
    assert "status=succeeded" in output
    assert "input_tokens=10" in output
    assert "output_tokens=5" in output
    assert "total_tokens=15" in output
    assert "estimated_cost_usd=0.001" in output
    assert "duration_ms=1000" in output
    assert "agent_name=review_summarizer" in output


def test_format_run_inspection_includes_failed_model_invocation_error_message() -> None:
    record = _workflow_run_record()

    output = format_run_inspection(
        record=record,
        artifacts=[],
        steps=[],
        model_invocations=[
            _model_invocation_record(
                run_id=record.run_id,
                status=ModelInvocationStatus.FAILED,
                error_message="budget exceeded",
            )
        ],
    )

    assert "status=failed" in output
    assert "error_message=budget exceeded" in output


def test_format_run_inspection_does_not_include_raw_prompt_or_response_text() -> None:
    record = _workflow_run_record()

    output = format_run_inspection(
        record=record,
        artifacts=[],
        steps=[],
        model_invocations=[
            _model_invocation_record(
                run_id=record.run_id,
                status=ModelInvocationStatus.SUCCEEDED,
            )
        ],
    )

    assert "sensitive raw prompt text" not in output
    assert "sensitive raw response text" not in output


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


def _model_invocation_record(
    *,
    run_id: UUID,
    status: ModelInvocationStatus,
    error_message: str | None = None,
) -> ModelInvocationRecord:
    return ModelInvocationRecord(
        invocation_id=uuid4(),
        run_id=run_id,
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
        status=status,
        started_at_utc=datetime(2026, 5, 7, 10, 0, tzinfo=UTC),
        completed_at_utc=datetime(2026, 5, 7, 10, 0, 1, tzinfo=UTC),
        duration_ms=1_000,
        input_artifact_path=Path("artifacts/input.json"),
        output_artifact_path=Path("artifacts/output.json"),
        error_message=error_message,
    )
