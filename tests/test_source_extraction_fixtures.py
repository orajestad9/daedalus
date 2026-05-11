import json
from pathlib import Path

import pytest

from daedalus.domains.readysetrentables_reviews.source_extraction_artifacts import (
    write_rsr_source_extract_json,
)
from daedalus.domains.readysetrentables_reviews.source_extraction_fixtures import (
    build_sample_rsr_source_extraction_result,
)
from daedalus.domains.readysetrentables_reviews.source_extraction_models import (
    RsrSourceExtractionResult,
)

_PRIVATE_MARKERS = ["real", "production", "localhost", "password", "secret", "api_key"]


def test_fixture_returns_rsr_source_extraction_result() -> None:
    result = build_sample_rsr_source_extraction_result()

    assert isinstance(result, RsrSourceExtractionResult)


def test_fixture_extracted_at_utc_is_timezone_aware() -> None:
    result = build_sample_rsr_source_extraction_result()

    assert result.extracted_at_utc.tzinfo is not None


def test_fixture_request_market_name_is_populated() -> None:
    result = build_sample_rsr_source_extraction_result()

    assert result.request.market_name
    assert result.request.market_name.strip()


def test_fixture_reviews_list_is_populated() -> None:
    result = build_sample_rsr_source_extraction_result()

    assert len(result.reviews) >= 3


def test_fixture_listings_list_is_populated() -> None:
    result = build_sample_rsr_source_extraction_result()

    assert len(result.listings) >= 2


def test_fixture_neighborhood_is_populated() -> None:
    result = build_sample_rsr_source_extraction_result()

    assert result.neighborhood is not None
    assert result.neighborhood.neighborhood_name.strip()


def test_fixture_all_reviews_have_non_empty_review_id() -> None:
    result = build_sample_rsr_source_extraction_result()

    for review in result.reviews:
        assert review.review_id.strip()


def test_fixture_all_reviews_have_non_empty_review_text() -> None:
    result = build_sample_rsr_source_extraction_result()

    for review in result.reviews:
        assert review.review_text.strip()


def test_fixture_all_listings_have_non_empty_listing_id() -> None:
    result = build_sample_rsr_source_extraction_result()

    for listing in result.listings:
        assert listing.listing_id.strip()


def test_fixture_metadata_marks_synthetic_data() -> None:
    result = build_sample_rsr_source_extraction_result()

    assert result.metadata.get("fixture") == "true"
    assert result.metadata.get("source") == "synthetic"


def test_fixture_can_be_written_with_writer(tmp_path: Path) -> None:
    result = build_sample_rsr_source_extraction_result()
    output_path = tmp_path / "rsr_source_extract.json"

    returned = write_rsr_source_extract_json(result=result, output_path=output_path)

    assert returned == output_path
    assert output_path.exists()


def test_fixture_written_json_is_parseable(tmp_path: Path) -> None:
    result = build_sample_rsr_source_extraction_result()
    output_path = tmp_path / "rsr_source_extract.json"

    write_rsr_source_extract_json(result=result, output_path=output_path)
    data = json.loads(output_path.read_text(encoding="utf-8"))

    assert isinstance(data, dict)
    assert "reviews" in data
    assert "listings" in data


@pytest.mark.parametrize("marker", _PRIVATE_MARKERS)
def test_fixture_contains_no_obvious_private_markers(marker: str) -> None:
    result = build_sample_rsr_source_extraction_result()
    serialized = result.model_dump_json().lower()

    assert marker not in serialized, f"private marker '{marker}' found in fixture output"


def test_fixture_is_deterministic() -> None:
    result_a = build_sample_rsr_source_extraction_result()
    result_b = build_sample_rsr_source_extraction_result()

    assert result_a.model_dump_json() == result_b.model_dump_json()
