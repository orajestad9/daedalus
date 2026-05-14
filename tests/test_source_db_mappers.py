from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from daedalus.domains.readysetrentables_reviews.source_db_mappers import (
    build_source_extraction_result_from_rows,
    map_listing_row_to_source_listing_context,
    map_neighborhood_row_to_source_neighborhood_context,
    map_review_row_to_source_review_record,
)
from daedalus.domains.readysetrentables_reviews.source_extraction_models import (
    RsrSourceExtractionRequest,
)


def test_map_review_row_to_source_review_record_maps_valid_row() -> None:
    created_at = datetime(2024, 1, 2, 3, 4, tzinfo=timezone.utc)

    review = map_review_row_to_source_review_record(
        {
            "review_id": "review-001",
            "listing_id": "listing-001",
            "rating": 4.5,
            "review_text": "Synthetic review text.",
            "created_at": created_at,
            "metadata": {"source": "synthetic"},
        }
    )

    assert review.review_id == "review-001"
    assert review.listing_id == "listing-001"
    assert review.rating == 4.5
    assert review.review_text == "Synthetic review text."
    assert review.created_at == created_at
    assert review.metadata == {"source": "synthetic"}


def test_review_mapper_handles_missing_optional_fields() -> None:
    review = map_review_row_to_source_review_record(
        {
            "review_id": "review-001",
            "review_text": "Synthetic review text.",
        }
    )

    assert review.listing_id is None
    assert review.rating is None
    assert review.created_at is None
    assert review.metadata == {}


def test_review_mapper_rejects_invalid_row_through_model_validation() -> None:
    with pytest.raises(ValidationError):
        map_review_row_to_source_review_record(
            {
                "review_id": "review-001",
                "review_text": "   ",
            }
        )


def test_review_mapper_does_not_require_db_access() -> None:
    review = map_review_row_to_source_review_record(
        {
            "review_id": "review-001",
            "review_text": "Synthetic review text.",
        }
    )

    assert review.review_id == "review-001"


def test_map_listing_row_to_source_listing_context_maps_valid_row() -> None:
    listing = map_listing_row_to_source_listing_context(
        {
            "listing_id": "listing-001",
            "listing_name": "Synthetic Listing",
            "property_type": "house",
            "bedrooms": 3,
            "bathrooms": 2.5,
            "accommodates": 6,
            "average_rating": 4.8,
            "metadata": {"source": "synthetic"},
        }
    )

    assert listing.listing_id == "listing-001"
    assert listing.listing_name == "Synthetic Listing"
    assert listing.property_type == "house"
    assert listing.bedrooms == 3
    assert listing.bathrooms == 2.5
    assert listing.accommodates == 6
    assert listing.average_rating == 4.8
    assert listing.metadata == {"source": "synthetic"}


def test_listing_mapper_handles_missing_optional_fields() -> None:
    listing = map_listing_row_to_source_listing_context({"listing_id": "listing-001"})

    assert listing.listing_name is None
    assert listing.property_type is None
    assert listing.bedrooms is None
    assert listing.bathrooms is None
    assert listing.accommodates is None
    assert listing.average_rating is None
    assert listing.metadata == {}


def test_listing_mapper_rejects_invalid_row_through_model_validation() -> None:
    with pytest.raises(ValidationError):
        map_listing_row_to_source_listing_context({"listing_id": "   "})


def test_map_neighborhood_row_to_source_neighborhood_context_maps_valid_row() -> None:
    neighborhood = map_neighborhood_row_to_source_neighborhood_context(
        {
            "market_name": "Synthetic Market",
            "neighborhood_name": "Synthetic District",
            "city": "Sample City",
            "state": "ST",
            "country": "US",
            "metadata": {"source": "synthetic"},
        }
    )

    assert neighborhood.market_name == "Synthetic Market"
    assert neighborhood.neighborhood_name == "Synthetic District"
    assert neighborhood.city == "Sample City"
    assert neighborhood.state == "ST"
    assert neighborhood.country == "US"
    assert neighborhood.metadata == {"source": "synthetic"}


def test_neighborhood_mapper_handles_missing_optional_fields() -> None:
    neighborhood = map_neighborhood_row_to_source_neighborhood_context(
        {
            "market_name": "Synthetic Market",
            "neighborhood_name": "Synthetic District",
        }
    )

    assert neighborhood.city is None
    assert neighborhood.state is None
    assert neighborhood.country is None
    assert neighborhood.metadata == {}


def test_neighborhood_mapper_rejects_invalid_row_through_model_validation() -> None:
    with pytest.raises(ValidationError):
        map_neighborhood_row_to_source_neighborhood_context(
            {
                "market_name": "Synthetic Market",
                "neighborhood_name": "   ",
            }
        )


def test_build_source_extraction_result_from_rows_maps_rows() -> None:
    result = build_source_extraction_result_from_rows(
        request=_request(),
        review_rows=[_review_row()],
        listing_rows=[_listing_row()],
        neighborhood_row=_neighborhood_row(),
        extracted_at_utc=datetime(2024, 1, 3, tzinfo=timezone.utc),
    )

    assert result.reviews[0].review_id == "review-001"
    assert result.listings[0].listing_id == "listing-001"
    assert result.neighborhood is not None
    assert result.neighborhood.neighborhood_name == "Synthetic District"


def test_build_source_extraction_result_from_rows_handles_no_neighborhood() -> None:
    result = build_source_extraction_result_from_rows(
        request=_request(),
        review_rows=[_review_row()],
        listing_rows=[_listing_row()],
        neighborhood_row=None,
    )

    assert result.neighborhood is None


def test_build_source_extraction_result_from_rows_generates_timezone_aware_timestamp() -> None:
    result = build_source_extraction_result_from_rows(
        request=_request(),
        review_rows=[],
        listing_rows=[],
    )

    assert result.extracted_at_utc.tzinfo is not None


def test_build_source_extraction_result_from_rows_preserves_supplied_timestamp() -> None:
    extracted_at = datetime(2024, 2, 3, 4, 5, tzinfo=timezone.utc)

    result = build_source_extraction_result_from_rows(
        request=_request(),
        review_rows=[],
        listing_rows=[],
        extracted_at_utc=extracted_at,
    )

    assert result.extracted_at_utc == extracted_at


def test_build_source_extraction_result_from_rows_preserves_source_metadata() -> None:
    result = build_source_extraction_result_from_rows(
        request=_request(),
        review_rows=[],
        listing_rows=[],
        source_name="readysetrentables_test",
        source_version="v1",
        metadata={"fixture": "true"},
    )

    assert result.source_name == "readysetrentables_test"
    assert result.source_version == "v1"
    assert result.metadata == {"fixture": "true"}


def test_no_real_db_connection_is_used() -> None:
    result = build_source_extraction_result_from_rows(
        request=_request(),
        review_rows=[_review_row()],
        listing_rows=[],
    )

    assert result.reviews[0].review_id == "review-001"


def test_json_serialization_works_for_mapped_result() -> None:
    result = build_source_extraction_result_from_rows(
        request=_request(),
        review_rows=[_review_row()],
        listing_rows=[_listing_row()],
        neighborhood_row=_neighborhood_row(),
        extracted_at_utc=datetime(2024, 1, 3, tzinfo=timezone.utc),
    )

    json_content = result.model_dump_json()

    assert "review-001" in json_content
    assert "listing-001" in json_content
    assert "Synthetic District" in json_content


def _request() -> RsrSourceExtractionRequest:
    return RsrSourceExtractionRequest(market_name="Synthetic Market")


def _review_row() -> dict[str, object]:
    return {
        "review_id": "review-001",
        "listing_id": "listing-001",
        "rating": 4.5,
        "review_text": "Synthetic review text.",
        "created_at": datetime(2024, 1, 2, 3, 4, tzinfo=timezone.utc),
        "metadata": {"source": "synthetic"},
    }


def _listing_row() -> dict[str, object]:
    return {
        "listing_id": "listing-001",
        "listing_name": "Synthetic Listing",
        "property_type": "house",
        "bedrooms": 3,
        "bathrooms": 2.5,
        "accommodates": 6,
        "average_rating": 4.8,
        "metadata": {"source": "synthetic"},
    }


def _neighborhood_row() -> dict[str, object]:
    return {
        "market_name": "Synthetic Market",
        "neighborhood_name": "Synthetic District",
        "city": "Sample City",
        "state": "ST",
        "country": "US",
        "metadata": {"source": "synthetic"},
    }
