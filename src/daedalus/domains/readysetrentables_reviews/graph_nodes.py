"""LangGraph-oriented nodes for the ReadySetRentables review workflow.

These functions are deterministic graph nodes: they reuse the same ingestion
and artifact helpers as the trusted workflow while carrying run_id, approval
state, and WorkflowStepRecord data through LangGraph state.
"""

from pathlib import Path

from daedalus.domains.readysetrentables_reviews.artifacts import (
    ReviewBatchArtifactMetadata,
    write_review_batch_json,
    write_review_batch_metadata_json,
    write_review_normalization_summary_markdown,
)
from daedalus.domains.readysetrentables_reviews.graph_state import (
    ReadySetRentablesReviewGraphState,
)
from daedalus.domains.readysetrentables_reviews.ingestion import load_airbnb_reviews_csv
from daedalus.domains.readysetrentables_reviews.theme_summary_input_builder import (
    build_review_theme_summary_input,
)
from daedalus.orchestrator.artifact_type import ArtifactType
from daedalus.orchestrator.run_lifecycle import calculate_duration_ms, utc_now
from daedalus.orchestrator.run_record import (
    WorkflowRunRecord,
    write_workflow_run_record_json,
)
from daedalus.orchestrator.status import WorkflowStatus
from daedalus.orchestrator.step_record import WorkflowStepRecord
from daedalus.orchestrator.workflow_identity import WorkflowDomain, WorkflowName


def load_reviews_node(
    state: ReadySetRentablesReviewGraphState,
) -> ReadySetRentablesReviewGraphState:
    """Load review CSV data and return graph state with a populated batch."""
    step = WorkflowStepRecord.start(run_id=state.run_id, step_name="load_reviews")
    try:
        batch = load_airbnb_reviews_csv(state.input_csv_path)
    except Exception as exc:
        state.steps.append(step.fail(str(exc)))
        raise

    return state.model_copy(
        update={
            "batch": batch,
            "steps": [*state.steps, step.complete()],
        }
    )


def write_normalized_artifact_node(
    state: ReadySetRentablesReviewGraphState,
) -> ReadySetRentablesReviewGraphState:
    """Write normalized review JSON from a loaded batch."""
    if state.batch is None:
        msg = "Cannot write normalized artifact before review batch is loaded."
        raise ValueError(msg)

    step = WorkflowStepRecord.start(
        run_id=state.run_id,
        step_name="write_normalized_artifact",
    )
    try:
        output_json_path = write_review_batch_json(state.batch, state.output_json_path)
    except Exception as exc:
        state.steps.append(step.fail(str(exc)))
        raise

    return state.model_copy(
        update={
            "output_json_path": output_json_path,
            "steps": [*state.steps, step.complete()],
        }
    )


def write_metadata_artifact_node(
    state: ReadySetRentablesReviewGraphState,
) -> ReadySetRentablesReviewGraphState:
    """Write review metadata JSON next to the normalized artifact."""
    if state.batch is None:
        msg = "Cannot write metadata artifact before review batch is loaded."
        raise ValueError(msg)

    metadata_json_path = _metadata_path_for(state.output_json_path)
    step = WorkflowStepRecord.start(
        run_id=state.run_id,
        step_name="write_metadata_artifact",
    )
    metadata = ReviewBatchArtifactMetadata(
        run_id=state.run_id,
        workflow_name=WorkflowName.READYSETRENTABLES_REVIEW_NORMALIZATION,
        artifact_type=ArtifactType.NORMALIZED_REVIEWS,
        source_csv_path=state.input_csv_path,
        output_json_path=state.output_json_path,
        created_at_utc=utc_now(),
        review_count=state.batch.review_count,
    )
    try:
        written_metadata_path = write_review_batch_metadata_json(
            metadata,
            metadata_json_path,
        )
    except Exception as exc:
        state.steps.append(step.fail(str(exc)))
        raise

    return state.model_copy(
        update={
            "metadata_json_path": written_metadata_path,
            "steps": [*state.steps, step.complete()],
        }
    )


def _metadata_path_for(output_json_path: Path) -> Path:
    return output_json_path.with_name(f"{output_json_path.stem}.metadata.json")


def build_review_theme_summary_input_node(
    state: ReadySetRentablesReviewGraphState,
) -> ReadySetRentablesReviewGraphState:
    """Build compact review theme summary input from a loaded review batch."""
    if state.batch is None:
        msg = "Cannot build review theme summary input before review batch is loaded."
        raise ValueError(msg)

    step = WorkflowStepRecord.start(
        run_id=state.run_id,
        step_name="build_review_theme_summary_input",
    )
    try:
        review_theme_summary_input = build_review_theme_summary_input(
            run_id=state.run_id,
            batch=state.batch,
        )
    except Exception as exc:
        state.steps.append(step.fail(str(exc)))
        raise

    return state.model_copy(
        update={
            "review_theme_summary_input": review_theme_summary_input,
            "steps": [*state.steps, step.complete()],
        }
    )


def write_summary_artifact_node(
    state: ReadySetRentablesReviewGraphState,
) -> ReadySetRentablesReviewGraphState:
    """Write human-readable summary markdown from graph state."""
    if state.batch is None:
        msg = "Cannot write summary artifact before review batch is loaded."
        raise ValueError(msg)
    if state.metadata_json_path is None:
        msg = "Cannot write summary artifact before metadata artifact is written."
        raise ValueError(msg)

    summary_markdown_path = _summary_path_for(state.output_json_path)
    step = WorkflowStepRecord.start(
        run_id=state.run_id,
        step_name="write_summary_artifact",
    )
    try:
        written_summary_path = write_review_normalization_summary_markdown(
            run_id=state.run_id,
            source_csv_path=state.input_csv_path,
            output_json_path=state.output_json_path,
            metadata_json_path=state.metadata_json_path,
            summary_markdown_path=summary_markdown_path,
            review_count=state.batch.review_count,
            approval_required=state.approval_required,
            approved=state.approved,
            steps=state.steps,
        )
    except Exception as exc:
        state.steps.append(step.fail(str(exc)))
        raise

    return state.model_copy(
        update={
            "summary_markdown_path": written_summary_path,
            "steps": [*state.steps, step.complete()],
        }
    )


def _summary_path_for(output_json_path: Path) -> Path:
    return output_json_path.with_name(f"{output_json_path.stem}.summary.md")


def write_run_record_artifact_node(
    state: ReadySetRentablesReviewGraphState,
) -> ReadySetRentablesReviewGraphState:
    """Write the generic workflow run record JSON artifact from graph state."""
    if state.batch is None:
        msg = "Cannot write run record artifact before review batch is loaded."
        raise ValueError(msg)
    if state.metadata_json_path is None:
        msg = "Cannot write run record artifact before metadata artifact is written."
        raise ValueError(msg)
    if state.summary_markdown_path is None:
        msg = "Cannot write run record artifact before summary artifact is written."
        raise ValueError(msg)

    completed_at_utc = utc_now()
    run_record_json_path = _run_record_path_for(state.output_json_path)
    run_record = WorkflowRunRecord(
        run_id=state.run_id,
        workflow_name=WorkflowName.READYSETRENTABLES_REVIEW_NORMALIZATION,
        domain=WorkflowDomain.READYSETRENTABLES_REVIEWS,
        status=WorkflowStatus.COMPLETED,
        started_at_utc=state.started_at_utc,
        completed_at_utc=completed_at_utc,
        source_input_path=state.input_csv_path,
        output_artifact_path=state.output_json_path,
        metadata_artifact_path=state.metadata_json_path,
        summary_artifact_path=state.summary_markdown_path,
        run_record_artifact_path=run_record_json_path,
        duration_ms=calculate_duration_ms(state.started_at_utc, completed_at_utc),
        review_count=state.batch.review_count,
        approval_required=state.approval_required,
        approved=state.approved,
    )
    step = WorkflowStepRecord.start(
        run_id=state.run_id,
        step_name="write_run_record_artifact",
    )
    try:
        written_run_record_path = write_workflow_run_record_json(
            run_record,
            run_record_json_path,
        )
    except Exception as exc:
        state.steps.append(step.fail(str(exc)))
        raise

    return state.model_copy(
        update={
            "run_record_json_path": written_run_record_path,
            "steps": [*state.steps, step.complete()],
        }
    )


def _run_record_path_for(output_json_path: Path) -> Path:
    return output_json_path.with_name(f"{output_json_path.stem}.run.json")
