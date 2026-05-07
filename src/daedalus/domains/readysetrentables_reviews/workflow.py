"""Deterministic ReadySetRentables review normalization workflow.

This module is the domain boundary for the Phase 0 review workflow. It performs
only deterministic parsing and artifact writing: no agents, model clients,
database writes, or graph orchestration live here yet.
"""

import logging
from datetime import UTC, datetime
from pathlib import Path
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
from daedalus.orchestrator.run_record import (
    WorkflowRunRecord,
    write_workflow_run_record_json,
)
from daedalus.orchestrator.status import WorkflowStatus
from daedalus.orchestrator.workflow_identity import WorkflowDomain, WorkflowName


logger = logging.getLogger(__name__)
WORKFLOW_NAME = WorkflowName.READYSETRENTABLES_REVIEW_NORMALIZATION
DOMAIN = WorkflowDomain.READYSETRENTABLES_REVIEWS


class ReviewNormalizationWorkflowResult(BaseModel):
    """Result returned after normalizing review CSV data into a JSON artifact."""

    source_csv_path: Path
    output_json_path: Path
    metadata_json_path: Path
    summary_markdown_path: Path
    run_record_json_path: Path
    review_count: int
    run_id: UUID
    approval_required: bool
    approved: bool


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
    started_at_utc = datetime.now(UTC)

    logger.info("Starting review normalization workflow run_id=%s", run_id)
    logger.info("Input CSV path: %s run_id=%s", input_csv_path, run_id)
    logger.info("Output JSON path: %s run_id=%s", output_json_path, run_id)

    batch = load_airbnb_reviews_csv(input_csv_path)
    artifact_path = write_review_batch_json(batch, output_json_path)
    metadata_path = _metadata_path_for(artifact_path)
    metadata = ReviewBatchArtifactMetadata(
        run_id=run_id,
        workflow_name=WORKFLOW_NAME,
        artifact_type=ArtifactType.NORMALIZED_REVIEWS,
        source_csv_path=input_csv_path,
        output_json_path=artifact_path,
        created_at_utc=datetime.now(UTC),
        review_count=batch.review_count,
    )
    write_review_batch_metadata_json(metadata, metadata_path)
    summary_path = _summary_path_for(artifact_path)
    write_review_normalization_summary_markdown(
        run_id=run_id,
        source_csv_path=input_csv_path,
        output_json_path=artifact_path,
        metadata_json_path=metadata_path,
        summary_markdown_path=summary_path,
        review_count=batch.review_count,
        approval_required=approval_required,
        approved=approved,
    )
    completed_at_utc = datetime.now(UTC)
    run_record_path = _run_record_path_for(artifact_path)
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
        review_count=batch.review_count,
        approval_required=approval_required,
        approved=approved,
    )
    write_workflow_run_record_json(run_record, run_record_path)

    logger.info("Review count: %s run_id=%s", batch.review_count, run_id)
    logger.info("Metadata JSON path: %s run_id=%s", metadata_path, run_id)
    logger.info("Summary markdown path: %s run_id=%s", summary_path, run_id)
    logger.info("Run record JSON path: %s run_id=%s", run_record_path, run_id)
    logger.info("Completed review normalization workflow run_id=%s", run_id)

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
    )


def _metadata_path_for(output_json_path: Path) -> Path:
    return output_json_path.with_name(f"{output_json_path.stem}.metadata.json")


def _summary_path_for(output_json_path: Path) -> Path:
    return output_json_path.with_name(f"{output_json_path.stem}.summary.md")


def _run_record_path_for(output_json_path: Path) -> Path:
    return output_json_path.with_name(f"{output_json_path.stem}.run.json")
