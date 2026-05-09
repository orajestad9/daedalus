import json
from pathlib import Path

import pytest

from daedalus.domains.readysetrentables_reviews.graph_nodes import (
    build_review_theme_summary_input_node,
    load_reviews_node,
    write_metadata_artifact_node,
    write_normalized_artifact_node,
    write_run_record_artifact_node,
    write_summary_artifact_node,
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


def test_write_metadata_artifact_node_writes_metadata_and_preserves_state(
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
    artifact_state = write_normalized_artifact_node(loaded_state)

    updated_state = write_metadata_artifact_node(artifact_state)

    expected_metadata_path = tmp_path / "normalized_reviews.metadata.json"
    assert updated_state.metadata_json_path == expected_metadata_path
    assert expected_metadata_path.exists()
    assert updated_state.run_id == artifact_state.run_id
    assert updated_state.input_csv_path == SAMPLE_CSV_PATH
    assert updated_state.output_json_path == output_json_path
    assert updated_state.approval_required is True
    assert updated_state.approved is True
    assert updated_state.batch == artifact_state.batch


def test_write_metadata_artifact_node_writes_expected_metadata_content(
    tmp_path: Path,
) -> None:
    state = ReadySetRentablesReviewGraphState.create(
        input_csv_path=SAMPLE_CSV_PATH,
        output_json_path=tmp_path / "normalized_reviews.json",
    )
    artifact_state = write_normalized_artifact_node(load_reviews_node(state))

    updated_state = write_metadata_artifact_node(artifact_state)

    assert updated_state.metadata_json_path is not None
    metadata = json.loads(updated_state.metadata_json_path.read_text(encoding="utf-8"))
    assert metadata["run_id"] == str(state.run_id)
    assert metadata["artifact_type"] == "normalized_reviews"
    assert metadata["review_count"] == EXPECTED_SAMPLE_REVIEW_COUNT


def test_write_metadata_artifact_node_preserves_existing_steps_and_appends_completed_step(
    tmp_path: Path,
) -> None:
    state = ReadySetRentablesReviewGraphState.create(
        input_csv_path=SAMPLE_CSV_PATH,
        output_json_path=tmp_path / "normalized_reviews.json",
    )
    artifact_state = write_normalized_artifact_node(load_reviews_node(state))

    updated_state = write_metadata_artifact_node(artifact_state)

    assert [step.step_name for step in updated_state.steps] == [
        "load_reviews",
        "write_normalized_artifact",
        "write_metadata_artifact",
    ]
    assert updated_state.steps[:2] == artifact_state.steps
    step = updated_state.steps[2]
    assert step.run_id == state.run_id
    assert step.status == WorkflowStatus.COMPLETED
    assert step.completed_at_utc is not None
    assert step.duration_ms is not None
    assert step.duration_ms >= 0


def test_write_metadata_artifact_node_requires_loaded_batch() -> None:
    state = ReadySetRentablesReviewGraphState.create(
        input_csv_path=SAMPLE_CSV_PATH,
        output_json_path=Path("normalized_reviews.json"),
    )

    with pytest.raises(ValueError, match="review batch is loaded"):
        write_metadata_artifact_node(state)


def test_build_review_theme_summary_input_node_populates_compact_input() -> None:
    state = ReadySetRentablesReviewGraphState.create(
        input_csv_path=SAMPLE_CSV_PATH,
        output_json_path=Path("normalized_reviews.json"),
    )
    loaded_state = load_reviews_node(state)

    updated_state = build_review_theme_summary_input_node(loaded_state)

    assert updated_state.review_theme_summary_input is not None
    assert updated_state.review_theme_summary_input.run_id == state.run_id
    assert updated_state.review_theme_summary_input.review_count == EXPECTED_SAMPLE_REVIEW_COUNT
    assert updated_state.review_theme_summary_input.representative_reviews
    assert updated_state.run_id == loaded_state.run_id
    assert updated_state.input_csv_path == loaded_state.input_csv_path
    assert updated_state.output_json_path == loaded_state.output_json_path
    assert updated_state.batch == loaded_state.batch


def test_build_review_theme_summary_input_node_preserves_existing_steps_and_appends_completed_step() -> (
    None
):
    state = ReadySetRentablesReviewGraphState.create(
        input_csv_path=SAMPLE_CSV_PATH,
        output_json_path=Path("normalized_reviews.json"),
    )
    loaded_state = load_reviews_node(state)

    updated_state = build_review_theme_summary_input_node(loaded_state)

    assert [step.step_name for step in updated_state.steps] == [
        "load_reviews",
        "build_review_theme_summary_input",
    ]
    assert updated_state.steps[0] == loaded_state.steps[0]
    step = updated_state.steps[1]
    assert step.run_id == state.run_id
    assert step.status == WorkflowStatus.COMPLETED
    assert step.completed_at_utc is not None
    assert step.duration_ms is not None
    assert step.duration_ms >= 0


def test_build_review_theme_summary_input_node_requires_loaded_batch() -> None:
    state = ReadySetRentablesReviewGraphState.create(
        input_csv_path=SAMPLE_CSV_PATH,
        output_json_path=Path("normalized_reviews.json"),
    )

    with pytest.raises(ValueError, match="review batch is loaded"):
        build_review_theme_summary_input_node(state)


def test_write_summary_artifact_node_writes_summary_and_preserves_state(
    tmp_path: Path,
) -> None:
    output_json_path = tmp_path / "normalized_reviews.json"
    state = ReadySetRentablesReviewGraphState.create(
        input_csv_path=SAMPLE_CSV_PATH,
        output_json_path=output_json_path,
        approval_required=True,
        approved=True,
    )
    metadata_state = write_metadata_artifact_node(
        write_normalized_artifact_node(load_reviews_node(state))
    )

    updated_state = write_summary_artifact_node(metadata_state)

    expected_summary_path = tmp_path / "normalized_reviews.summary.md"
    assert updated_state.summary_markdown_path == expected_summary_path
    assert expected_summary_path.exists()
    assert updated_state.run_id == metadata_state.run_id
    assert updated_state.input_csv_path == SAMPLE_CSV_PATH
    assert updated_state.output_json_path == output_json_path
    assert updated_state.metadata_json_path == metadata_state.metadata_json_path
    assert updated_state.approval_required is True
    assert updated_state.approved is True
    assert updated_state.batch == metadata_state.batch


def test_write_summary_artifact_node_writes_expected_summary_content(
    tmp_path: Path,
) -> None:
    state = ReadySetRentablesReviewGraphState.create(
        input_csv_path=SAMPLE_CSV_PATH,
        output_json_path=tmp_path / "normalized_reviews.json",
        approval_required=True,
        approved=True,
    )
    metadata_state = write_metadata_artifact_node(
        write_normalized_artifact_node(load_reviews_node(state))
    )

    updated_state = write_summary_artifact_node(metadata_state)

    assert updated_state.summary_markdown_path is not None
    summary = updated_state.summary_markdown_path.read_text(encoding="utf-8")
    assert str(state.run_id) in summary
    assert f"Review count: {EXPECTED_SAMPLE_REVIEW_COUNT}" in summary
    assert "Approval required: True" in summary
    assert "Approved: True" in summary
    assert "## Workflow Steps" in summary
    assert "- load_reviews: completed" in summary
    assert "- write_normalized_artifact: completed" in summary
    assert "- write_metadata_artifact: completed" in summary
    assert "- write_summary_artifact: completed" not in summary


def test_write_summary_artifact_node_preserves_existing_steps_and_appends_completed_step(
    tmp_path: Path,
) -> None:
    state = ReadySetRentablesReviewGraphState.create(
        input_csv_path=SAMPLE_CSV_PATH,
        output_json_path=tmp_path / "normalized_reviews.json",
    )
    metadata_state = write_metadata_artifact_node(
        write_normalized_artifact_node(load_reviews_node(state))
    )

    updated_state = write_summary_artifact_node(metadata_state)

    assert [step.step_name for step in updated_state.steps] == [
        "load_reviews",
        "write_normalized_artifact",
        "write_metadata_artifact",
        "write_summary_artifact",
    ]
    assert updated_state.steps[:3] == metadata_state.steps
    step = updated_state.steps[3]
    assert step.run_id == state.run_id
    assert step.status == WorkflowStatus.COMPLETED
    assert step.completed_at_utc is not None
    assert step.duration_ms is not None
    assert step.duration_ms >= 0


def test_write_summary_artifact_node_requires_loaded_batch() -> None:
    state = ReadySetRentablesReviewGraphState.create(
        input_csv_path=SAMPLE_CSV_PATH,
        output_json_path=Path("normalized_reviews.json"),
    )

    with pytest.raises(ValueError, match="review batch is loaded"):
        write_summary_artifact_node(state)


def test_write_summary_artifact_node_requires_metadata_path(tmp_path: Path) -> None:
    state = write_normalized_artifact_node(
        load_reviews_node(
            ReadySetRentablesReviewGraphState.create(
                input_csv_path=SAMPLE_CSV_PATH,
                output_json_path=tmp_path / "normalized_reviews.json",
            )
        )
    )

    with pytest.raises(ValueError, match="metadata artifact is written"):
        write_summary_artifact_node(state)


def test_write_run_record_artifact_node_writes_run_record_and_preserves_state(
    tmp_path: Path,
) -> None:
    output_json_path = tmp_path / "normalized_reviews.json"
    state = ReadySetRentablesReviewGraphState.create(
        input_csv_path=SAMPLE_CSV_PATH,
        output_json_path=output_json_path,
        approval_required=True,
        approved=True,
    )
    summary_state = write_summary_artifact_node(
        write_metadata_artifact_node(write_normalized_artifact_node(load_reviews_node(state)))
    )

    updated_state = write_run_record_artifact_node(summary_state)

    expected_run_record_path = tmp_path / "normalized_reviews.run.json"
    assert updated_state.run_record_json_path == expected_run_record_path
    assert expected_run_record_path.exists()
    assert updated_state.run_id == summary_state.run_id
    assert updated_state.started_at_utc == summary_state.started_at_utc
    assert updated_state.input_csv_path == SAMPLE_CSV_PATH
    assert updated_state.output_json_path == output_json_path
    assert updated_state.metadata_json_path == summary_state.metadata_json_path
    assert updated_state.summary_markdown_path == summary_state.summary_markdown_path
    assert updated_state.approval_required is True
    assert updated_state.approved is True
    assert updated_state.batch == summary_state.batch


def test_write_run_record_artifact_node_writes_expected_run_record_content(
    tmp_path: Path,
) -> None:
    state = ReadySetRentablesReviewGraphState.create(
        input_csv_path=SAMPLE_CSV_PATH,
        output_json_path=tmp_path / "normalized_reviews.json",
        approval_required=True,
        approved=True,
    )
    summary_state = write_summary_artifact_node(
        write_metadata_artifact_node(write_normalized_artifact_node(load_reviews_node(state)))
    )

    updated_state = write_run_record_artifact_node(summary_state)

    assert updated_state.run_record_json_path is not None
    run_record = json.loads(updated_state.run_record_json_path.read_text(encoding="utf-8"))
    assert run_record["run_id"] == str(state.run_id)
    assert run_record["workflow_name"] == "readysetrentables_review_normalization"
    assert run_record["domain"] == "readysetrentables_reviews"
    assert run_record["status"] == "completed"
    assert isinstance(run_record["duration_ms"], int)
    assert run_record["duration_ms"] >= 0
    assert run_record["source_input_path"] == str(SAMPLE_CSV_PATH)
    assert run_record["output_artifact_path"] == str(summary_state.output_json_path)
    assert run_record["metadata_artifact_path"] == str(summary_state.metadata_json_path)
    assert run_record["summary_artifact_path"] == str(summary_state.summary_markdown_path)
    assert run_record["run_record_artifact_path"] == str(updated_state.run_record_json_path)
    assert run_record["review_count"] == EXPECTED_SAMPLE_REVIEW_COUNT
    assert run_record["approval_required"] is True
    assert run_record["approved"] is True


def test_write_run_record_artifact_node_preserves_existing_steps_and_appends_completed_step(
    tmp_path: Path,
) -> None:
    state = ReadySetRentablesReviewGraphState.create(
        input_csv_path=SAMPLE_CSV_PATH,
        output_json_path=tmp_path / "normalized_reviews.json",
    )
    summary_state = write_summary_artifact_node(
        write_metadata_artifact_node(write_normalized_artifact_node(load_reviews_node(state)))
    )

    updated_state = write_run_record_artifact_node(summary_state)

    assert [step.step_name for step in updated_state.steps] == [
        "load_reviews",
        "write_normalized_artifact",
        "write_metadata_artifact",
        "write_summary_artifact",
        "write_run_record_artifact",
    ]
    assert updated_state.steps[:4] == summary_state.steps
    step = updated_state.steps[4]
    assert step.run_id == state.run_id
    assert step.status == WorkflowStatus.COMPLETED
    assert step.completed_at_utc is not None
    assert step.duration_ms is not None
    assert step.duration_ms >= 0


def test_write_run_record_artifact_node_requires_loaded_batch() -> None:
    state = ReadySetRentablesReviewGraphState.create(
        input_csv_path=SAMPLE_CSV_PATH,
        output_json_path=Path("normalized_reviews.json"),
    )

    with pytest.raises(ValueError, match="review batch is loaded"):
        write_run_record_artifact_node(state)


def test_write_run_record_artifact_node_requires_metadata_path(tmp_path: Path) -> None:
    state = write_normalized_artifact_node(
        load_reviews_node(
            ReadySetRentablesReviewGraphState.create(
                input_csv_path=SAMPLE_CSV_PATH,
                output_json_path=tmp_path / "normalized_reviews.json",
            )
        )
    )

    with pytest.raises(ValueError, match="metadata artifact is written"):
        write_run_record_artifact_node(state)


def test_write_run_record_artifact_node_requires_summary_path(tmp_path: Path) -> None:
    state = write_metadata_artifact_node(
        write_normalized_artifact_node(
            load_reviews_node(
                ReadySetRentablesReviewGraphState.create(
                    input_csv_path=SAMPLE_CSV_PATH,
                    output_json_path=tmp_path / "normalized_reviews.json",
                )
            )
        )
    )

    with pytest.raises(ValueError, match="summary artifact is written"):
        write_run_record_artifact_node(state)
