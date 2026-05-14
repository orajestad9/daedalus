"""Pure row mappers for ReadySetRentables source extraction results."""

from collections.abc import Mapping, Sequence
from datetime import datetime
from typing import Any

from daedalus.domains.readysetrentables_reviews.source_extraction_models import (
    RsrSourceExtractionRequest,
    RsrSourceExtractionResult,
    RsrSourceListingContext,
    RsrSourceNeighborhoodContext,
    RsrSourceReviewRecord,
)
from daedalus.orchestrator.run_lifecycle import utc_now


def map_review_row_to_source_review_record(row: Mapping[str, Any]) -> RsrSourceReviewRecord:
    """Map an already-fetched review row into a sanitized source review model."""
    return RsrSourceReviewRecord.model_validate(
        {
            "review_id": row.get("review_id"),
            "listing_id": row.get("listing_id"),
            "rating": row.get("rating"),
            "review_text": row.get("review_text"),
            "created_at": row.get("created_at"),
            "metadata": _metadata_or_empty(row.get("metadata")),
        }
    )


def map_listing_row_to_source_listing_context(row: Mapping[str, Any]) -> RsrSourceListingContext:
    """Map an already-fetched listing row into a sanitized listing context model."""
    return RsrSourceListingContext.model_validate(
        {
            "listing_id": row.get("listing_id"),
            "listing_name": row.get("listing_name"),
            "property_type": row.get("property_type"),
            "bedrooms": row.get("bedrooms"),
            "bathrooms": row.get("bathrooms"),
            "accommodates": row.get("accommodates"),
            "average_rating": row.get("average_rating"),
            "metadata": _metadata_or_empty(row.get("metadata")),
        }
    )


def map_neighborhood_row_to_source_neighborhood_context(
    row: Mapping[str, Any],
) -> RsrSourceNeighborhoodContext:
    """Map an already-fetched neighborhood row into a sanitized neighborhood model."""
    return RsrSourceNeighborhoodContext.model_validate(
        {
            "market_name": row.get("market_name"),
            "neighborhood_name": row.get("neighborhood_name"),
            "city": row.get("city"),
            "state": row.get("state"),
            "country": row.get("country"),
            "metadata": _metadata_or_empty(row.get("metadata")),
        }
    )


def build_source_extraction_result_from_rows(
    *,
    request: RsrSourceExtractionRequest,
    review_rows: Sequence[Mapping[str, Any]],
    listing_rows: Sequence[Mapping[str, Any]],
    neighborhood_row: Mapping[str, Any] | None = None,
    extracted_at_utc: datetime | None = None,
    source_name: str = "readysetrentables",
    source_version: str = "v0",
    metadata: Mapping[str, str] | None = None,
) -> RsrSourceExtractionResult:
    """Build a source extraction result from already-fetched row dictionaries."""
    reviews = [map_review_row_to_source_review_record(row) for row in review_rows]
    listings = [map_listing_row_to_source_listing_context(row) for row in listing_rows]
    neighborhood = (
        None
        if neighborhood_row is None
        else map_neighborhood_row_to_source_neighborhood_context(neighborhood_row)
    )

    return RsrSourceExtractionResult(
        request=request,
        extracted_at_utc=utc_now() if extracted_at_utc is None else extracted_at_utc,
        reviews=reviews,
        listings=listings,
        neighborhood=neighborhood,
        source_name=source_name,
        source_version=source_version,
        metadata=dict(metadata or {}),
    )


def _metadata_or_empty(value: Any) -> Any:
    if value is None:
        return {}
    return value
