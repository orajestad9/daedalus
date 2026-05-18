import json
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

import pytest

from daedalus.domains.readysetrentables_reviews.review_insight_input_builder import (
    build_review_insight_extraction_input_from_source_extract,
)
from daedalus.domains.readysetrentables_reviews.review_insight_models import (
    DEFAULT_REVIEW_INSIGHT_PROMPT_NAME,
    DEFAULT_REVIEW_INSIGHT_PROMPT_VERSION,
    ReviewInsightExtractionInput,
)
from daedalus.domains.readysetrentables_reviews.source_extraction_models import (
    RsrSourceExtractionRequest,
    RsrSourceExtractionResult,
    RsrSourceListingContext,
    RsrSourceNeighborhoodContext,
    RsrSourceReviewRecord,
)


def test_builds_review_insight_extraction_input_from_valid_source_extract() -> None:
    source_extract = _source_extract()

    model = build_review_insight_extraction_input_from_source_extract(source_extract=source_extract)

    assert isinstance(model, ReviewInsightExtractionInput)
    assert model.review_count == 3
    assert model.market_name == "Sample Market"
    assert model.neighborhood_name == "Request Neighborhood"
    assert model.property_type == "Request Property"
    assert model.representative_reviews == [
        "First synthetic review.",
        "Second synthetic review.",
        "Third synthetic review.",
    ]


def test_build_uses_provided_run_id_when_supplied() -> None:
    run_id = uuid4()

    model = build_review_insight_extraction_input_from_source_extract(
        source_extract=_source_extract(),
        run_id=run_id,
    )

    assert model.run_id == run_id


def test_build_falls_back_to_source_request_id_when_run_id_omitted() -> None:
    source_extract = _source_extract()

    model = build_review_insight_extraction_input_from_source_extract(source_extract=source_extract)

    assert model.run_id == source_extract.request.request_id


def test_build_review_count_equals_number_of_source_reviews() -> None:
    model = build_review_insight_extraction_input_from_source_extract(
        source_extract=_source_extract(
            reviews=[
                _review("review-1", "First synthetic review."),
                _review("review-2", "Second synthetic review."),
            ]
        )
    )

    assert model.review_count == 2


def test_build_market_name_comes_from_request() -> None:
    model = build_review_insight_extraction_input_from_source_extract(
        source_extract=_source_extract(request_market_name="Request Market")
    )

    assert model.market_name == "Request Market"


def test_build_neighborhood_name_comes_from_request_when_provided() -> None:
    model = build_review_insight_extraction_input_from_source_extract(
        source_extract=_source_extract(
            request_neighborhood_name="Request Neighborhood",
            neighborhood_name="Context Neighborhood",
        )
    )

    assert model.neighborhood_name == "Request Neighborhood"


def test_build_neighborhood_name_falls_back_to_neighborhood_context() -> None:
    model = build_review_insight_extraction_input_from_source_extract(
        source_extract=_source_extract(
            request_neighborhood_name=None,
            neighborhood_name="Context Neighborhood",
        )
    )

    assert model.neighborhood_name == "Context Neighborhood"


def test_build_property_type_comes_from_request_when_provided() -> None:
    model = build_review_insight_extraction_input_from_source_extract(
        source_extract=_source_extract(
            request_property_type="Request Property",
            listings=[_listing("listing-1", property_type="Listing Property")],
        )
    )

    assert model.property_type == "Request Property"


def test_build_property_type_falls_back_to_listing_context() -> None:
    model = build_review_insight_extraction_input_from_source_extract(
        source_extract=_source_extract(
            request_property_type=None,
            listings=[_listing("listing-1", property_type="Listing Property")],
        )
    )

    assert model.property_type == "Listing Property"


def test_build_average_rating_averages_listing_average_rating_values() -> None:
    model = build_review_insight_extraction_input_from_source_extract(
        source_extract=_source_extract(
            listings=[
                _listing("listing-1", average_rating=4.0),
                _listing("listing-2", average_rating=5.0),
                _listing("listing-3", average_rating=None),
            ]
        )
    )

    assert model.average_rating == 4.5


def test_build_average_rating_is_none_when_no_listing_ratings_exist() -> None:
    model = build_review_insight_extraction_input_from_source_extract(
        source_extract=_source_extract(
            listings=[
                _listing("listing-1", average_rating=None),
                _listing("listing-2", average_rating=None),
            ]
        )
    )

    assert model.average_rating is None


def test_build_rating_categories_average_supported_review_score_metadata() -> None:
    model = build_review_insight_extraction_input_from_source_extract(
        source_extract=_source_extract(
            listings=[
                _listing(
                    "listing-1",
                    metadata={
                        "review_scores_accuracy": "4.0",
                        "review_scores_cleanliness": "5.0",
                    },
                ),
                _listing(
                    "listing-2",
                    metadata={
                        "review_scores_accuracy": "5.0",
                        "review_scores_cleanliness": "3.0",
                        "review_scores_location": "4.5",
                    },
                ),
            ]
        )
    )

    assert model.rating_categories == {
        "review_scores_accuracy": 4.5,
        "review_scores_cleanliness": 4.0,
        "review_scores_location": 4.5,
    }


def test_build_rating_categories_ignore_missing_non_numeric_and_out_of_range_values() -> None:
    model = build_review_insight_extraction_input_from_source_extract(
        source_extract=_source_extract(
            listings=[
                _listing(
                    "listing-1",
                    metadata={
                        "review_scores_accuracy": "not numeric",
                        "review_scores_cleanliness": "6.0",
                        "review_scores_checkin": "4.0",
                    },
                ),
                _listing(
                    "listing-2",
                    metadata={
                        "review_scores_accuracy": "4.5",
                        "review_scores_cleanliness": "-1",
                    },
                ),
            ]
        )
    )

    assert model.rating_categories == {
        "review_scores_accuracy": 4.5,
        "review_scores_checkin": 4.0,
    }


def test_build_representative_reviews_preserve_order() -> None:
    model = build_review_insight_extraction_input_from_source_extract(
        source_extract=_source_extract(
            reviews=[
                _review("review-1", "First synthetic review."),
                _review("review-2", "Second synthetic review."),
                _review("review-3", "Third synthetic review."),
            ]
        )
    )

    assert model.representative_reviews == [
        "First synthetic review.",
        "Second synthetic review.",
        "Third synthetic review.",
    ]


def test_build_representative_reviews_strip_whitespace() -> None:
    model = build_review_insight_extraction_input_from_source_extract(
        source_extract=_source_extract(
            reviews=[_review("review-1", "  Trimmed synthetic review.  ")]
        )
    )

    assert model.representative_reviews == ["Trimmed synthetic review."]


def test_build_representative_reviews_omit_blank_text() -> None:
    blank_review = RsrSourceReviewRecord.model_construct(
        review_id="review-blank",
        review_text="   ",
    )
    model = build_review_insight_extraction_input_from_source_extract(
        source_extract=_source_extract(
            reviews=[blank_review, _review("review-1", "Visible synthetic review.")]
        )
    )

    assert model.representative_reviews == ["Visible synthetic review."]


def test_build_representative_reviews_respect_max_representative_reviews() -> None:
    model = build_review_insight_extraction_input_from_source_extract(
        source_extract=_source_extract(),
        max_representative_reviews=2,
    )

    assert model.representative_reviews == [
        "First synthetic review.",
        "Second synthetic review.",
    ]


def test_build_allows_zero_representative_reviews() -> None:
    model = build_review_insight_extraction_input_from_source_extract(
        source_extract=_source_extract(),
        max_representative_reviews=0,
    )

    assert model.representative_reviews == []


def test_build_rejects_negative_max_representative_reviews() -> None:
    with pytest.raises(ValueError, match="max_representative_reviews"):
        build_review_insight_extraction_input_from_source_extract(
            source_extract=_source_extract(),
            max_representative_reviews=-1,
        )


def test_build_source_artifact_path_is_preserved() -> None:
    source_artifact_path = Path("artifacts/readysetrentables/rsr_source_extract.json")

    model = build_review_insight_extraction_input_from_source_extract(
        source_extract=_source_extract(),
        source_artifact_path=source_artifact_path,
    )

    assert model.source_artifact_path == source_artifact_path


def test_build_prompt_identity_defaults_remain_set() -> None:
    model = build_review_insight_extraction_input_from_source_extract(
        source_extract=_source_extract()
    )

    assert model.prompt_name == DEFAULT_REVIEW_INSIGHT_PROMPT_NAME
    assert model.prompt_version == DEFAULT_REVIEW_INSIGHT_PROMPT_VERSION


def test_build_does_not_require_db_access() -> None:
    model = build_review_insight_extraction_input_from_source_extract(
        source_extract=_source_extract()
    )

    assert model.review_count == 3


def test_build_does_not_call_model_providers() -> None:
    model = build_review_insight_extraction_input_from_source_extract(
        source_extract=_source_extract()
    )

    assert model.prompt_name == DEFAULT_REVIEW_INSIGHT_PROMPT_NAME


def test_build_json_serialization_works() -> None:
    model = build_review_insight_extraction_input_from_source_extract(
        source_extract=_source_extract()
    )

    data = json.loads(model.model_dump_json())

    assert data["review_count"] == 3
    assert data["representative_reviews"][0] == "First synthetic review."


def _source_extract(
    *,
    request_market_name: str = "Sample Market",
    request_neighborhood_name: str | None = "Request Neighborhood",
    request_property_type: str | None = "Request Property",
    neighborhood_name: str = "Context Neighborhood",
    reviews: list[RsrSourceReviewRecord] | None = None,
    listings: list[RsrSourceListingContext] | None = None,
) -> RsrSourceExtractionResult:
    return RsrSourceExtractionResult(
        request=RsrSourceExtractionRequest(
            market_name=request_market_name,
            neighborhood_name=request_neighborhood_name,
            property_type=request_property_type,
        ),
        extracted_at_utc=datetime(2026, 5, 18, 10, 0, tzinfo=UTC),
        reviews=reviews
        if reviews is not None
        else [
            _review("review-1", "First synthetic review."),
            _review("review-2", "Second synthetic review."),
            _review("review-3", "Third synthetic review."),
        ],
        listings=listings if listings is not None else [_listing("listing-1")],
        neighborhood=RsrSourceNeighborhoodContext(
            market_name="Context Market",
            neighborhood_name=neighborhood_name,
        ),
        metadata={"fixture": "true", "source": "synthetic"},
    )


def _review(review_id: str, review_text: str) -> RsrSourceReviewRecord:
    return RsrSourceReviewRecord(review_id=review_id, review_text=review_text)


def _listing(
    listing_id: str,
    *,
    property_type: str | None = "Listing Property",
    average_rating: float | None = 4.8,
    metadata: dict[str, str] | None = None,
) -> RsrSourceListingContext:
    return RsrSourceListingContext(
        listing_id=listing_id,
        property_type=property_type,
        average_rating=average_rating,
        metadata=metadata or {},
    )
