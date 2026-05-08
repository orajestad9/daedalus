import json
import logging
from datetime import datetime
from pathlib import Path
from uuid import UUID

from daedalus.domains.readysetrentables_reviews.workflow import (
    run_review_normalization_workflow,
)
from daedalus.orchestrator.status import WorkflowStatus


SAMPLE_CSV_PATH = Path("sample_data/readysetrentables_reviews/airbnb_reviews_sample.csv")
EXPECTED_SAMPLE_REVIEW_COUNT = 8
EXPECTED_STEP_NAMES = [
    "load_reviews",
    "write_normalized_artifact",
    "write_metadata_artifact",
    "write_summary_artifact",
    "write_run_record_artifact",
]


def test_run_review_normalization_workflow_writes_json_artifact(tmp_path: Path) -> None:
    output_path = tmp_path / "normalized_reviews.json"

    result = run_review_normalization_workflow(
        input_csv_path=SAMPLE_CSV_PATH,
        output_json_path=output_path,
    )

    assert result.source_csv_path == SAMPLE_CSV_PATH
    assert result.output_json_path == output_path
    assert result.metadata_json_path == tmp_path / "normalized_reviews.metadata.json"
    assert result.summary_markdown_path == tmp_path / "normalized_reviews.summary.md"
    assert result.run_record_json_path == tmp_path / "normalized_reviews.run.json"
    assert result.review_count == EXPECTED_SAMPLE_REVIEW_COUNT
    assert isinstance(result.run_id, UUID)
    assert result.approval_required is False
    assert result.approved is False
    assert [step.step_name for step in result.steps] == EXPECTED_STEP_NAMES
    assert output_path.exists()
    assert result.metadata_json_path.exists()
    assert result.summary_markdown_path.exists()
    assert result.run_record_json_path.exists()


def test_run_review_normalization_workflow_artifact_contains_reviews(tmp_path: Path) -> None:
    output_path = tmp_path / "normalized_reviews.json"

    run_review_normalization_workflow(
        input_csv_path=SAMPLE_CSV_PATH,
        output_json_path=output_path,
    )

    artifact = json.loads(output_path.read_text(encoding="utf-8"))

    assert artifact["source"] == "airbnb"
    assert len(artifact["reviews"]) == EXPECTED_SAMPLE_REVIEW_COUNT
    assert artifact["reviews"][0]["review_id"] == "rr_syn_0001"


def test_run_review_normalization_workflow_writes_metadata_artifact(tmp_path: Path) -> None:
    output_path = tmp_path / "normalized_reviews.json"

    result = run_review_normalization_workflow(
        input_csv_path=SAMPLE_CSV_PATH,
        output_json_path=output_path,
    )

    metadata = json.loads(result.metadata_json_path.read_text(encoding="utf-8"))

    assert metadata["run_id"] == str(result.run_id)
    assert metadata["workflow_name"] == "readysetrentables_review_normalization"
    assert metadata["artifact_type"] == "normalized_reviews"
    assert metadata["source_csv_path"] == str(SAMPLE_CSV_PATH)
    assert metadata["output_json_path"] == str(output_path)
    assert metadata["review_count"] == EXPECTED_SAMPLE_REVIEW_COUNT

    created_at_utc = datetime.fromisoformat(metadata["created_at_utc"].replace("Z", "+00:00"))
    assert created_at_utc.tzinfo is not None


def test_run_review_normalization_workflow_writes_summary_markdown(tmp_path: Path) -> None:
    output_path = tmp_path / "normalized_reviews.json"

    result = run_review_normalization_workflow(
        input_csv_path=SAMPLE_CSV_PATH,
        output_json_path=output_path,
    )

    summary = result.summary_markdown_path.read_text(encoding="utf-8")

    assert str(result.run_id) in summary
    assert f"Review count: {EXPECTED_SAMPLE_REVIEW_COUNT}" in summary
    assert str(output_path) in summary
    assert "Approval required: False" in summary
    assert "Approved: False" in summary


def test_run_review_normalization_workflow_writes_run_record(tmp_path: Path) -> None:
    output_path = tmp_path / "normalized_reviews.json"

    result = run_review_normalization_workflow(
        input_csv_path=SAMPLE_CSV_PATH,
        output_json_path=output_path,
    )

    run_record = json.loads(result.run_record_json_path.read_text(encoding="utf-8"))

    assert run_record["run_id"] == str(result.run_id)
    assert run_record["workflow_name"] == "readysetrentables_review_normalization"
    assert run_record["domain"] == "readysetrentables_reviews"
    assert run_record["status"] == "completed"
    assert run_record["source_input_path"] == str(SAMPLE_CSV_PATH)
    assert run_record["output_artifact_path"] == str(output_path)
    assert run_record["metadata_artifact_path"] == str(result.metadata_json_path)
    assert run_record["summary_artifact_path"] == str(result.summary_markdown_path)
    assert run_record["run_record_artifact_path"] == str(result.run_record_json_path)
    assert isinstance(run_record["duration_ms"], int)
    assert run_record["duration_ms"] >= 0
    assert run_record["review_count"] == EXPECTED_SAMPLE_REVIEW_COUNT
    assert run_record["approval_required"] is False
    assert run_record["approved"] is False

    started_at_utc = datetime.fromisoformat(run_record["started_at_utc"].replace("Z", "+00:00"))
    completed_at_utc = datetime.fromisoformat(run_record["completed_at_utc"].replace("Z", "+00:00"))
    assert started_at_utc.tzinfo is not None
    assert completed_at_utc.tzinfo is not None


def test_run_review_normalization_workflow_collects_completed_steps(
    tmp_path: Path,
) -> None:
    output_path = tmp_path / "normalized_reviews.json"

    result = run_review_normalization_workflow(
        input_csv_path=SAMPLE_CSV_PATH,
        output_json_path=output_path,
    )

    assert [step.step_name for step in result.steps] == EXPECTED_STEP_NAMES
    assert {step.run_id for step in result.steps} == {result.run_id}
    assert all(step.status == WorkflowStatus.COMPLETED for step in result.steps)
    assert all(step.duration_ms is not None for step in result.steps)
    assert all(step.duration_ms is not None and step.duration_ms >= 0 for step in result.steps)


def test_run_review_normalization_workflow_logs_run_context(
    tmp_path: Path,
) -> None:
    output_path = tmp_path / "normalized_reviews.json"
    workflow_logger = logging.getLogger("daedalus.domains.readysetrentables_reviews.workflow")
    handler = _ListHandler()
    original_level = workflow_logger.level
    original_propagate = workflow_logger.propagate
    workflow_logger.setLevel(logging.INFO)
    workflow_logger.propagate = False
    workflow_logger.addHandler(handler)

    try:
        result = run_review_normalization_workflow(
            input_csv_path=SAMPLE_CSV_PATH,
            output_json_path=output_path,
        )
    finally:
        workflow_logger.removeHandler(handler)
        workflow_logger.setLevel(original_level)
        workflow_logger.propagate = original_propagate

    messages = [record.getMessage() for record in handler.records]
    assert any(
        "Starting workflow" in message
        and f"run_id={result.run_id}" in message
        and "workflow_name=readysetrentables_review_normalization" in message
        for message in messages
    )
    assert any(
        "Completed workflow" in message
        and f"run_id={result.run_id}" in message
        and "workflow_name=readysetrentables_review_normalization" in message
        for message in messages
    )


class _ListHandler(logging.Handler):
    def __init__(self) -> None:
        super().__init__()
        self.records: list[logging.LogRecord] = []

    def emit(self, record: logging.LogRecord) -> None:
        self.records.append(record)
