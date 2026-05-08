from pathlib import Path
from uuid import UUID, uuid4

from daedalus.domains.readysetrentables_reviews.graph_state import (
    ReadySetRentablesReviewGraphState,
)
from daedalus.orchestrator.step_record import WorkflowStepRecord


def test_graph_state_create_generates_run_id_and_preserves_paths() -> None:
    input_csv_path = Path("sample_data/readysetrentables_reviews/airbnb_reviews_sample.csv")
    output_json_path = Path("artifacts/readysetrentables/normalized_reviews.json")

    state = ReadySetRentablesReviewGraphState.create(
        input_csv_path=input_csv_path,
        output_json_path=output_json_path,
    )

    assert isinstance(state.run_id, UUID)
    assert state.input_csv_path == input_csv_path
    assert state.output_json_path == output_json_path


def test_graph_state_create_starts_with_empty_workflow_data() -> None:
    state = ReadySetRentablesReviewGraphState.create(
        input_csv_path=Path("reviews.csv"),
        output_json_path=Path("normalized_reviews.json"),
    )

    assert state.batch is None
    assert state.metadata_json_path is None
    assert state.summary_markdown_path is None
    assert state.run_record_json_path is None
    assert state.steps == []
    assert state.approval_required is False
    assert state.approved is False


def test_graph_state_create_accepts_approval_flags() -> None:
    state = ReadySetRentablesReviewGraphState.create(
        input_csv_path=Path("reviews.csv"),
        output_json_path=Path("normalized_reviews.json"),
        approval_required=True,
        approved=True,
    )

    assert state.approval_required is True
    assert state.approved is True


def test_graph_state_steps_are_not_shared_between_instances() -> None:
    first_state = ReadySetRentablesReviewGraphState.create(
        input_csv_path=Path("first.csv"),
        output_json_path=Path("first.json"),
    )
    second_state = ReadySetRentablesReviewGraphState.create(
        input_csv_path=Path("second.csv"),
        output_json_path=Path("second.json"),
    )

    first_state.steps.append(WorkflowStepRecord.start(run_id=uuid4(), step_name="load_reviews"))

    assert len(first_state.steps) == 1
    assert second_state.steps == []
