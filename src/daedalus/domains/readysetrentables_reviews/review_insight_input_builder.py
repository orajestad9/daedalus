"""Build review insight extraction inputs from RSR source extraction artifacts."""

from collections.abc import Iterable
from pathlib import Path
from uuid import UUID

from daedalus.domains.readysetrentables_reviews.review_insight_models import (
    ReviewInsightExtractionInput,
)
from daedalus.domains.readysetrentables_reviews.source_extraction_models import (
    RsrSourceExtractionResult,
    RsrSourceListingContext,
)

_SUPPORTED_RATING_CATEGORY_KEYS = (
    "review_scores_accuracy",
    "review_scores_cleanliness",
    "review_scores_checkin",
    "review_scores_communication",
    "review_scores_location",
    "review_scores_value",
)


def build_review_insight_extraction_input_from_source_extract(
    *,
    source_extract: RsrSourceExtractionResult,
    run_id: UUID | None = None,
    source_artifact_path: Path | None = None,
    max_representative_reviews: int = 25,
) -> ReviewInsightExtractionInput:
    """Transform sanitized RSR source extraction data into model-ready input."""
    if max_representative_reviews < 0:
        msg = "max_representative_reviews cannot be negative"
        raise ValueError(msg)

    return ReviewInsightExtractionInput(
        run_id=run_id or source_extract.request.request_id,
        review_count=len(source_extract.reviews),
        market_name=_first_present(
            source_extract.request.market_name,
            source_extract.neighborhood.market_name if source_extract.neighborhood else None,
        ),
        neighborhood_name=_first_present(
            source_extract.request.neighborhood_name,
            (
                source_extract.neighborhood.neighborhood_name
                if source_extract.neighborhood
                else None
            ),
        ),
        property_type=_first_present(
            source_extract.request.property_type,
            _first_listing_property_type(source_extract.listings),
        ),
        average_rating=_average(
            listing.average_rating
            for listing in source_extract.listings
            if listing.average_rating is not None
        ),
        rating_categories=_rating_categories(source_extract.listings),
        representative_reviews=_representative_reviews(
            source_extract=source_extract,
            max_representative_reviews=max_representative_reviews,
        ),
        source_artifact_path=source_artifact_path,
    )


def _first_present(*values: str | None) -> str | None:
    for value in values:
        if value is not None and value.strip():
            return value
    return None


def _first_listing_property_type(listings: list[RsrSourceListingContext]) -> str | None:
    for listing in listings:
        if listing.property_type is not None and listing.property_type.strip():
            return listing.property_type
    return None


def _average(values: Iterable[float]) -> float | None:
    numeric_values = list(values)
    if not numeric_values:
        return None
    return sum(numeric_values) / len(numeric_values)


def _rating_categories(listings: list[RsrSourceListingContext]) -> dict[str, float]:
    categories: dict[str, float] = {}
    for key in _SUPPORTED_RATING_CATEGORY_KEYS:
        average_value = _average(_metadata_float_values(listings, key))
        if average_value is not None:
            categories[key] = average_value
    return categories


def _metadata_float_values(
    listings: list[RsrSourceListingContext],
    key: str,
) -> list[float]:
    values: list[float] = []
    for listing in listings:
        raw_value = listing.metadata.get(key)
        if raw_value is None:
            continue
        try:
            parsed_value = float(raw_value)
        except ValueError:
            continue
        if parsed_value < 0 or parsed_value > 5:
            continue
        values.append(parsed_value)
    return values


def _representative_reviews(
    *,
    source_extract: RsrSourceExtractionResult,
    max_representative_reviews: int,
) -> list[str]:
    # Real review text is carried only into the local model input artifact so the
    # agent has evidence; CLI output should stick to counts and safe metadata.
    if max_representative_reviews == 0:
        return []

    reviews: list[str] = []
    for review in source_extract.reviews:
        review_text = review.review_text.strip()
        if review_text:
            reviews.append(review_text)
        if len(reviews) == max_representative_reviews:
            break
    return reviews
