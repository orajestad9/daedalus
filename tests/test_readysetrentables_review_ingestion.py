from datetime import date
from pathlib import Path

import pytest

from daedalus.domains.readysetrentables_reviews.ingestion import load_airbnb_reviews_csv


SAMPLE_CSV_PATH = (
    Path(__file__).resolve().parents[1]
    / "sample_data"
    / "readysetrentables_reviews"
    / "airbnb_reviews_sample.csv"
)


def test_loads_committed_sample_csv() -> None:
    batch = load_airbnb_reviews_csv(SAMPLE_CSV_PATH)

    assert batch.review_count == 8


def test_normalizes_first_sample_review_fields() -> None:
    batch = load_airbnb_reviews_csv(SAMPLE_CSV_PATH)
    first_review = batch.reviews[0]

    assert first_review.review_id == "rr_syn_0001"
    assert first_review.property_id == "prop_syn_101"
    assert first_review.reviewer_name == "Maya Chen"
    assert first_review.review_date == date(2025, 1, 14)
    assert first_review.rating == 5.0
    assert first_review.language == "en"
    assert first_review.country == "United States"


def test_preserves_raw_record_source_data() -> None:
    batch = load_airbnb_reviews_csv(SAMPLE_CSV_PATH)
    first_review = batch.reviews[0]

    if first_review.raw_record is None:
        pytest.fail("Expected raw_record to be preserved")

    source_data = first_review.raw_record.source_data
    assert source_data["review_id"] == "rr_syn_0001"
    assert source_data["property_id"] == "prop_syn_101"
    assert source_data["rating"] == "5"
    assert source_data["review_text"].startswith("Bright apartment with a spotless kitchen")


def test_missing_file_raises_file_not_found() -> None:
    with pytest.raises(FileNotFoundError):
        load_airbnb_reviews_csv(Path("sample_data/readysetrentables_reviews/missing.csv"))


def test_missing_required_column_raises_value_error(tmp_path: Path) -> None:
    csv_path = _write_csv(
        tmp_path,
        "review_id,rating\nrr_syn_9999,5\n",
    )

    with pytest.raises(ValueError, match="review_text"):
        load_airbnb_reviews_csv(csv_path)


def test_empty_required_field_raises_value_error(tmp_path: Path) -> None:
    csv_path = _write_csv(
        tmp_path,
        "review_id,review_text\nrr_syn_9999,   \n",
    )

    with pytest.raises(ValueError, match="empty required field: review_text"):
        load_airbnb_reviews_csv(csv_path)


def test_invalid_rating_raises_value_error(tmp_path: Path) -> None:
    csv_path = _write_csv(
        tmp_path,
        "review_id,review_text,rating\nrr_syn_9999,Great stay,not-a-rating\n",
    )

    with pytest.raises(ValueError, match="invalid rating"):
        load_airbnb_reviews_csv(csv_path)


def test_invalid_date_raises_value_error(tmp_path: Path) -> None:
    csv_path = _write_csv(
        tmp_path,
        "review_id,review_text,review_date\nrr_syn_9999,Great stay,05/06/2026\n",
    )

    with pytest.raises(ValueError, match="invalid review_date"):
        load_airbnb_reviews_csv(csv_path)


def _write_csv(tmp_path: Path, contents: str) -> Path:
    csv_path = tmp_path / "reviews.csv"
    csv_path.write_text(contents, encoding="utf-8")
    return csv_path
