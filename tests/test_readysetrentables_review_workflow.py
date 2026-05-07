import json
from datetime import datetime
from pathlib import Path
from uuid import UUID

from daedalus.domains.readysetrentables_reviews.workflow import (
    run_review_normalization_workflow,
)


SAMPLE_CSV_PATH = Path("sample_data/readysetrentables_reviews/airbnb_reviews_sample.csv")
EXPECTED_SAMPLE_REVIEW_COUNT = 8


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
    assert result.review_count == EXPECTED_SAMPLE_REVIEW_COUNT
    assert isinstance(result.run_id, UUID)
    assert result.approval_required is False
    assert result.approved is False
    assert output_path.exists()
    assert result.metadata_json_path.exists()
    assert result.summary_markdown_path.exists()


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
    assert metadata["artifact_type"] == "normalized_review_batch"
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
