"""LangGraph-oriented nodes for the ReadySetRentables review workflow.

These functions are plain Python node units for now. They prepare the domain
workflow for graph orchestration while preserving the existing deterministic
workflow entry point and behavior.
"""

from pathlib import Path

from daedalus.domains.readysetrentables_reviews.artifacts import (
    ReviewBatchArtifactMetadata,
    write_review_batch_json,
    write_review_batch_metadata_json,
)
from daedalus.domains.readysetrentables_reviews.graph_state import (
    ReadySetRentablesReviewGraphState,
)
from daedalus.domains.readysetrentables_reviews.ingestion import load_airbnb_reviews_csv
from daedalus.orchestrator.artifact_type import ArtifactType
from daedalus.orchestrator.run_lifecycle import utc_now
from daedalus.orchestrator.step_record import WorkflowStepRecord
from daedalus.orchestrator.workflow_identity import WorkflowName


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
