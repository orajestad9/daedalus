import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast
from uuid import uuid4

from daedalus.domains.readysetrentables_reviews.artifacts import (
    ReviewBatchArtifactMetadata,
    write_review_batch_json,
    write_review_batch_metadata_json,
    write_review_normalization_summary_markdown,
)
from daedalus.domains.readysetrentables_reviews.ingestion import load_airbnb_reviews_csv
from daedalus.orchestrator.artifact_type import ArtifactType


SAMPLE_CSV_PATH = (
    Path(__file__).resolve().parents[1]
    / "sample_data"
    / "readysetrentables_reviews"
    / "airbnb_reviews_sample.csv"
)
EXPECTED_SAMPLE_REVIEW_COUNT = 8


def test_writes_review_batch_json_artifact(tmp_path: Path) -> None:
    batch = load_airbnb_reviews_csv(SAMPLE_CSV_PATH)
    output_path = tmp_path / "artifacts" / "readysetrentables" / "review_batch.json"

    returned_path = write_review_batch_json(batch, output_path)

    assert returned_path == output_path
    assert output_path.is_file()


def test_review_batch_json_contains_expected_content(tmp_path: Path) -> None:
    batch = load_airbnb_reviews_csv(SAMPLE_CSV_PATH)
    output_path = tmp_path / "review_batch.json"

    write_review_batch_json(batch, output_path)

    data = cast(dict[str, Any], json.loads(output_path.read_text(encoding="utf-8")))

    assert data["source"] == "airbnb"
    assert len(data["reviews"]) == EXPECTED_SAMPLE_REVIEW_COUNT

    first_review = data["reviews"][0]
    assert first_review["review_id"] == "rr_syn_0001"
    assert first_review["review_date"] == "2025-01-14"
    assert first_review["rating"] == 5.0
    assert first_review["raw_record"]["source_data"]["review_id"] == "rr_syn_0001"
    assert first_review["raw_record"]["source_data"]["rating"] == "5"


def test_writes_review_batch_metadata_json(tmp_path: Path) -> None:
    run_id = uuid4()
    output_json_path = tmp_path / "review_batch.json"
    metadata_path = tmp_path / "metadata" / "review_batch.metadata.json"
    metadata = ReviewBatchArtifactMetadata(
        run_id=run_id,
        workflow_name="readysetrentables_review_normalization",
        artifact_type=ArtifactType.NORMALIZED_REVIEWS,
        source_csv_path=SAMPLE_CSV_PATH,
        output_json_path=output_json_path,
        created_at_utc=datetime(2026, 5, 7, 12, 0, tzinfo=UTC),
        review_count=EXPECTED_SAMPLE_REVIEW_COUNT,
    )

    returned_path = write_review_batch_metadata_json(metadata, metadata_path)

    data = cast(dict[str, Any], json.loads(metadata_path.read_text(encoding="utf-8")))
    assert returned_path == metadata_path
    assert data["run_id"] == str(run_id)
    assert data["workflow_name"] == "readysetrentables_review_normalization"
    assert data["artifact_type"] == "normalized_reviews"
    assert data["source_csv_path"] == str(SAMPLE_CSV_PATH)
    assert data["output_json_path"] == str(output_json_path)
    assert data["created_at_utc"] == "2026-05-07T12:00:00Z"
    assert data["review_count"] == EXPECTED_SAMPLE_REVIEW_COUNT


def test_writes_review_normalization_summary_markdown(tmp_path: Path) -> None:
    run_id = uuid4()
    output_json_path = tmp_path / "review_batch.json"
    metadata_json_path = tmp_path / "review_batch.metadata.json"
    summary_markdown_path = tmp_path / "summary" / "review_batch.summary.md"

    returned_path = write_review_normalization_summary_markdown(
        run_id=run_id,
        source_csv_path=SAMPLE_CSV_PATH,
        output_json_path=output_json_path,
        metadata_json_path=metadata_json_path,
        summary_markdown_path=summary_markdown_path,
        review_count=EXPECTED_SAMPLE_REVIEW_COUNT,
        approval_required=True,
        approved=True,
    )

    summary = summary_markdown_path.read_text(encoding="utf-8")
    assert returned_path == summary_markdown_path
    assert "# ReadySetRentables Review Normalization Summary" in summary
    assert str(run_id) in summary
    assert str(output_json_path) in summary
    assert f"Review count: {EXPECTED_SAMPLE_REVIEW_COUNT}" in summary
    assert "Approval required: True" in summary
    assert "Approved: True" in summary
