"""Synthetic fixtures for offline testing of the RSR source extraction boundary."""

from datetime import datetime, timezone
from uuid import UUID

from daedalus.domains.readysetrentables_reviews.source_extraction_models import (
    RsrSourceExtractionRequest,
    RsrSourceExtractionResult,
    RsrSourceListingContext,
    RsrSourceNeighborhoodContext,
    RsrSourceReviewRecord,
)

_EXTRACTED_AT = datetime(2024, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
_REQUEST_ID = UUID("00000000-0000-0000-0000-000000000001")


def build_sample_rsr_source_extraction_result() -> RsrSourceExtractionResult:
    """Return a deterministic synthetic RsrSourceExtractionResult for offline testing.

    Contains no real review data, real listing names, or private information.
    """
    request = RsrSourceExtractionRequest(
        request_id=_REQUEST_ID,
        market_name="Sample Market",
        neighborhood_name="Sample Neighborhood",
        max_reviews=10,
    )

    reviews = [
        RsrSourceReviewRecord(
            review_id="synthetic-review-001",
            listing_id="synthetic-listing-001",
            rating=4.5,
            review_text=(
                "Synthetic review: guests liked the walkable location"
                " and clear check-in instructions."
            ),
            metadata={"fixture": "true", "source": "synthetic"},
        ),
        RsrSourceReviewRecord(
            review_id="synthetic-review-002",
            listing_id="synthetic-listing-001",
            rating=5.0,
            review_text=(
                "Synthetic review: excellent communication from the host"
                " and a well-stocked kitchen."
            ),
            metadata={"fixture": "true", "source": "synthetic"},
        ),
        RsrSourceReviewRecord(
            review_id="synthetic-review-003",
            listing_id="synthetic-listing-002",
            rating=3.5,
            review_text=(
                "Synthetic review: comfortable stay overall, minor noise from nearby street."
            ),
            metadata={"fixture": "true", "source": "synthetic"},
        ),
    ]

    listings = [
        RsrSourceListingContext(
            listing_id="synthetic-listing-001",
            listing_name="Synthetic Studio Listing",
            property_type="Studio",
            bedrooms=0,
            bathrooms=1.0,
            accommodates=2,
            average_rating=4.7,
            metadata={"fixture": "true", "source": "synthetic"},
        ),
        RsrSourceListingContext(
            listing_id="synthetic-listing-002",
            listing_name="Synthetic One-Bedroom Listing",
            property_type="Apartment",
            bedrooms=1,
            bathrooms=1.0,
            accommodates=3,
            average_rating=3.5,
            metadata={"fixture": "true", "source": "synthetic"},
        ),
    ]

    neighborhood = RsrSourceNeighborhoodContext(
        market_name="Sample Market",
        neighborhood_name="Sample Neighborhood",
        city="Sample City",
        state="TX",
        country="US",
        metadata={"fixture": "true", "source": "synthetic"},
    )

    return RsrSourceExtractionResult(
        request=request,
        extracted_at_utc=_EXTRACTED_AT,
        reviews=reviews,
        listings=listings,
        neighborhood=neighborhood,
        source_name="readysetrentables",
        source_version="v0",
        metadata={"fixture": "true", "source": "synthetic"},
    )
