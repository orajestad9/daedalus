"""LangGraph-oriented nodes for the ReadySetRentables review workflow.

These functions are plain Python node units for now. They prepare the domain
workflow for graph orchestration while preserving the existing deterministic
workflow entry point and behavior.
"""

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
