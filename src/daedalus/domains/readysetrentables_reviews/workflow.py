"""Deterministic ReadySetRentables review normalization workflow.

This module is the domain boundary for the Phase 0 review workflow. It performs
only deterministic parsing and artifact writing: no agents, model clients,
database writes, or graph orchestration live here yet.
"""

import logging
from collections.abc import Callable
from pathlib import Path
from typing import TypeVar
from uuid import UUID, uuid4

from pydantic import BaseModel

from daedalus.domains.readysetrentables_reviews.artifacts import (
    ReviewBatchArtifactMetadata,
    write_review_batch_json,
    write_review_batch_metadata_json,
    write_review_normalization_summary_markdown,
)
from daedalus.domains.readysetrentables_reviews.ingestion import load_airbnb_reviews_csv
from daedalus.orchestrator.artifact_type import ArtifactType
from daedalus.orchestrator.run_lifecycle import calculate_duration_ms, utc_now
from daedalus.orchestrator.run_record import (
    WorkflowRunRecord,
    write_workflow_run_record_json,
)
from daedalus.orchestrator.status import WorkflowStatus
from daedalus.orchestrator.step_record import WorkflowStepRecord
from daedalus.orchestrator.workflow_identity import WorkflowDomain, WorkflowName


logger = logging.getLogger(__name__)
WORKFLOW_NAME = WorkflowName.READYSETRENTABLES_REVIEW_NORMALIZATION
DOMAIN = WorkflowDomain.READYSETRENTABLES_REVIEWS
StepResult = TypeVar("StepResult")


class ReviewNormalizationWorkflowResult(BaseModel):
    """Result returned after normalizing review CSV data into a JSON artifact."""

    source_csv_path: Path
    output_json_path: Path
    metadata_json_path: Path
    summary_markdown_path: Path
    run_record_json_path: Path
    review_theme_summary_markdown_path: Path | None = None
    review_count: int
    run_id: UUID
    approval_required: bool
    approved: bool
    steps: list[WorkflowStepRecord]


def run_review_normalization_workflow(
    input_csv_path: Path,
    output_json_path: Path,
    *,
    approval_required: bool = False,
    approved: bool = False,
) -> ReviewNormalizationWorkflowResult:
    """Run the deterministic review normalization workflow and write artifacts.

    The workflow emits separate artifacts for separate audiences: normalized JSON
    for downstream machines, metadata for artifact tracing, markdown for human
    review, and a generic run record for future persistence. Approval status is
    carried through the result and summary, but Phase 0 deliberately does not
    create a persistent approval-record artifact or database row.
    """
    run_id = uuid4()
    started_at_utc = utc_now()

    logger.info(
        "Starting workflow run_id=%s workflow_name=%s domain=%s",
        run_id,
        WORKFLOW_NAME.value,
        DOMAIN.value,
    )
    logger.info(
        "Workflow input/output paths run_id=%s workflow_name=%s domain=%s input_csv_path=%s output_json_path=%s",
        run_id,
        WORKFLOW_NAME.value,
        DOMAIN.value,
        input_csv_path,
        output_json_path,
    )

    steps: list[WorkflowStepRecord] = []
    batch = _run_step(
        run_id=run_id,
        steps=steps,
        step_name="load_reviews",
        action=lambda: load_airbnb_reviews_csv(input_csv_path),
    )

    artifact_path = _run_step(
        run_id=run_id,
        steps=steps,
        step_name="write_normalized_artifact",
        action=lambda: write_review_batch_json(batch, output_json_path),
    )

    metadata_path = _metadata_path_for(artifact_path)

    def write_metadata_artifact() -> Path:
        metadata = ReviewBatchArtifactMetadata(
            run_id=run_id,
            workflow_name=WORKFLOW_NAME,
            artifact_type=ArtifactType.NORMALIZED_REVIEWS,
            source_csv_path=input_csv_path,
            output_json_path=artifact_path,
            created_at_utc=utc_now(),
            review_count=batch.review_count,
        )
        return write_review_batch_metadata_json(metadata, metadata_path)

    _run_step(
        run_id=run_id,
        steps=steps,
        step_name="write_metadata_artifact",
        action=write_metadata_artifact,
    )

    summary_path = _summary_path_for(artifact_path)

    _run_step(
        run_id=run_id,
        steps=steps,
        step_name="write_summary_artifact",
        action=lambda: write_review_normalization_summary_markdown(
            run_id=run_id,
            source_csv_path=input_csv_path,
            output_json_path=artifact_path,
            metadata_json_path=metadata_path,
            summary_markdown_path=summary_path,
            review_count=batch.review_count,
            approval_required=approval_required,
            approved=approved,
        ),
    )

    completed_at_utc = utc_now()
    run_record_path = _run_record_path_for(artifact_path)
    duration_ms = calculate_duration_ms(started_at_utc, completed_at_utc)
    run_record = WorkflowRunRecord(
        run_id=run_id,
        workflow_name=WORKFLOW_NAME,
        domain=DOMAIN,
        status=WorkflowStatus.COMPLETED,
        started_at_utc=started_at_utc,
        completed_at_utc=completed_at_utc,
        source_input_path=input_csv_path,
        output_artifact_path=artifact_path,
        metadata_artifact_path=metadata_path,
        summary_artifact_path=summary_path,
        run_record_artifact_path=run_record_path,
        duration_ms=duration_ms,
        review_count=batch.review_count,
        approval_required=approval_required,
        approved=approved,
    )
    _run_step(
        run_id=run_id,
        steps=steps,
        step_name="write_run_record_artifact",
        action=lambda: write_workflow_run_record_json(run_record, run_record_path),
    )

    logger.info(
        "Completed workflow run_id=%s workflow_name=%s domain=%s review_count=%s duration_ms=%s",
        run_id,
        WORKFLOW_NAME.value,
        DOMAIN.value,
        batch.review_count,
        duration_ms,
    )

    return ReviewNormalizationWorkflowResult(
        source_csv_path=input_csv_path,
        output_json_path=artifact_path,
        metadata_json_path=metadata_path,
        summary_markdown_path=summary_path,
        run_record_json_path=run_record_path,
        review_count=batch.review_count,
        run_id=run_id,
        approval_required=approval_required,
        approved=approved,
        steps=steps,
    )


def _metadata_path_for(output_json_path: Path) -> Path:
    return output_json_path.with_name(f"{output_json_path.stem}.metadata.json")


def _summary_path_for(output_json_path: Path) -> Path:
    return output_json_path.with_name(f"{output_json_path.stem}.summary.md")


def _run_record_path_for(output_json_path: Path) -> Path:
    return output_json_path.with_name(f"{output_json_path.stem}.run.json")


def _run_step(
    *,
    run_id: UUID,
    steps: list[WorkflowStepRecord],
    step_name: str,
    action: Callable[[], StepResult],
) -> StepResult:
    step = WorkflowStepRecord.start(run_id=run_id, step_name=step_name)
    _log_step_started(run_id=run_id, step=step)
    try:
        result = action()
    except Exception as exc:
        failed_step = step.fail(str(exc))
        steps.append(failed_step)
        logger.info(
            "Failed workflow step run_id=%s workflow_name=%s domain=%s step_name=%s duration_ms=%s error_type=%s",
            run_id,
            WORKFLOW_NAME.value,
            DOMAIN.value,
            failed_step.step_name,
            failed_step.duration_ms,
            type(exc).__name__,
        )
        raise

    steps.append(_complete_step(run_id=run_id, step=step))
    return result


def _log_step_started(*, run_id: UUID, step: WorkflowStepRecord) -> None:
    logger.info(
        "Starting workflow step run_id=%s workflow_name=%s domain=%s step_name=%s",
        run_id,
        WORKFLOW_NAME.value,
        DOMAIN.value,
        step.step_name,
    )


def _complete_step(*, run_id: UUID, step: WorkflowStepRecord) -> WorkflowStepRecord:
    completed_step = step.complete()
    logger.info(
        "Completed workflow step run_id=%s workflow_name=%s domain=%s step_name=%s duration_ms=%s",
        run_id,
        WORKFLOW_NAME.value,
        DOMAIN.value,
        completed_step.step_name,
        completed_step.duration_ms,
    )
    return completed_step
