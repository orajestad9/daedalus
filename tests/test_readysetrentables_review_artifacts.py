import json
from pathlib import Path
from typing import Any, cast

from daedalus.domains.readysetrentables_reviews.artifacts import write_review_batch_json
from daedalus.domains.readysetrentables_reviews.ingestion import load_airbnb_reviews_csv


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
