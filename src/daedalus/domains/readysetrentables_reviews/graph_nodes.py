"""LangGraph-oriented nodes for the ReadySetRentables review workflow.

These functions are plain Python node units for now. They prepare the domain
workflow for graph orchestration while preserving the existing deterministic
workflow entry point and behavior.
"""

from daedalus.domains.readysetrentables_reviews.artifacts import write_review_batch_json
from daedalus.domains.readysetrentables_reviews.graph_state import (
    ReadySetRentablesReviewGraphState,
)
from daedalus.domains.readysetrentables_reviews.ingestion import load_airbnb_reviews_csv
from daedalus.orchestrator.step_record import WorkflowStepRecord


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
