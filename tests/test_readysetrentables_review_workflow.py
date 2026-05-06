import json
from pathlib import Path

from daedalus.domains.readysetrentables_reviews.workflow import (
    run_review_normalization_workflow,
)


SAMPLE_CSV_PATH = Path("sample_data/readysetrentables_reviews/airbnb_reviews_sample.csv")


def test_run_review_normalization_workflow_writes_json_artifact(tmp_path: Path) -> None:
    output_path = tmp_path / "normalized_reviews.json"

    result = run_review_normalization_workflow(
        input_csv_path=SAMPLE_CSV_PATH,
        output_json_path=output_path,
    )

    assert result.source_csv_path == SAMPLE_CSV_PATH
    assert result.output_json_path == output_path
    assert result.review_count == 6
    assert output_path.exists()


def test_run_review_normalization_workflow_artifact_contains_reviews(tmp_path: Path) -> None:
    output_path = tmp_path / "normalized_reviews.json"

    run_review_normalization_workflow(
        input_csv_path=SAMPLE_CSV_PATH,
        output_json_path=output_path,
    )

    artifact = json.loads(output_path.read_text(encoding="utf-8"))

    assert artifact["source"] == "airbnb"
    assert len(artifact["reviews"]) == 6
    assert artifact["reviews"][0]["review_id"] == "r-001"
