from pathlib import Path

import pytest

from daedalus.domains.readysetrentables_reviews.graph_nodes import (
    load_reviews_node,
    write_normalized_artifact_node,
)
from daedalus.domains.readysetrentables_reviews.graph_state import (
    ReadySetRentablesReviewGraphState,
)
from daedalus.orchestrator.status import WorkflowStatus


SAMPLE_CSV_PATH = Path("sample_data/readysetrentables_reviews/airbnb_reviews_sample.csv")
EXPECTED_SAMPLE_REVIEW_COUNT = 8


def test_load_reviews_node_populates_batch_and_preserves_state_fields() -> None:
    output_json_path = Path("artifacts/readysetrentables/normalized_reviews.json")
    state = ReadySetRentablesReviewGraphState.create(
        input_csv_path=SAMPLE_CSV_PATH,
        output_json_path=output_json_path,
        approval_required=True,
        approved=True,
    )

    updated_state = load_reviews_node(state)

    assert updated_state.batch is not None
    assert updated_state.batch.review_count == EXPECTED_SAMPLE_REVIEW_COUNT
    assert updated_state.run_id == state.run_id
    assert updated_state.input_csv_path == SAMPLE_CSV_PATH
    assert updated_state.output_json_path == output_json_path
    assert updated_state.approval_required is True
    assert updated_state.approved is True


def test_load_reviews_node_appends_completed_step() -> None:
    state = ReadySetRentablesReviewGraphState.create(
        input_csv_path=SAMPLE_CSV_PATH,
        output_json_path=Path("normalized_reviews.json"),
    )

    updated_state = load_reviews_node(state)

    assert len(updated_state.steps) == 1
    step = updated_state.steps[0]
    assert step.step_name == "load_reviews"
    assert step.run_id == state.run_id
    assert step.status == WorkflowStatus.COMPLETED
    assert step.completed_at_utc is not None
    assert step.duration_ms is not None
    assert step.duration_ms >= 0


def test_load_reviews_node_records_failed_step_and_reraises(tmp_path: Path) -> None:
    missing_csv_path = tmp_path / "missing_reviews.csv"
    state = ReadySetRentablesReviewGraphState.create(
        input_csv_path=missing_csv_path,
        output_json_path=Path("normalized_reviews.json"),
    )

    with pytest.raises(FileNotFoundError):
        load_reviews_node(state)

    assert len(state.steps) == 1
    step = state.steps[0]
    assert step.step_name == "load_reviews"
    assert step.run_id == state.run_id
    assert step.status == WorkflowStatus.FAILED
    assert step.completed_at_utc is not None
    assert step.duration_ms is not None
    assert step.duration_ms >= 0
    assert step.error_message is not None


def test_write_normalized_artifact_node_writes_json_and_preserves_state(
    tmp_path: Path,
) -> None:
    output_json_path = tmp_path / "normalized_reviews.json"
    state = ReadySetRentablesReviewGraphState.create(
        input_csv_path=SAMPLE_CSV_PATH,
        output_json_path=output_json_path,
        approval_required=True,
        approved=True,
    )
    loaded_state = load_reviews_node(state)

    updated_state = write_normalized_artifact_node(loaded_state)

    assert output_json_path.exists()
    assert updated_state.output_json_path == output_json_path
    assert updated_state.run_id == loaded_state.run_id
    assert updated_state.input_csv_path == SAMPLE_CSV_PATH
    assert updated_state.approval_required is True
    assert updated_state.approved is True
    assert updated_state.batch == loaded_state.batch


def test_write_normalized_artifact_node_preserves_existing_steps_and_appends_completed_step(
    tmp_path: Path,
) -> None:
    state = ReadySetRentablesReviewGraphState.create(
        input_csv_path=SAMPLE_CSV_PATH,
        output_json_path=tmp_path / "normalized_reviews.json",
    )
    loaded_state = load_reviews_node(state)

    updated_state = write_normalized_artifact_node(loaded_state)

    assert [step.step_name for step in updated_state.steps] == [
        "load_reviews",
        "write_normalized_artifact",
    ]
    assert updated_state.steps[0] == loaded_state.steps[0]
    step = updated_state.steps[1]
    assert step.run_id == state.run_id
    assert step.status == WorkflowStatus.COMPLETED
    assert step.completed_at_utc is not None
    assert step.duration_ms is not None
    assert step.duration_ms >= 0


def test_write_normalized_artifact_node_requires_loaded_batch() -> None:
    state = ReadySetRentablesReviewGraphState.create(
        input_csv_path=SAMPLE_CSV_PATH,
        output_json_path=Path("normalized_reviews.json"),
    )

    with pytest.raises(ValueError, match="review batch is loaded"):
        write_normalized_artifact_node(state)
