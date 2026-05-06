from datetime import date

import pytest
from pydantic import ValidationError

from daedalus.domains.readysetrentables_reviews.models import (
    NormalizedReview,
    ReviewBatch,
    ReviewSentiment,
)


def test_normalized_review_accepts_valid_data() -> None:
    review = NormalizedReview(
        review_id="review-001",
        property_id="property-123",
        reviewer_name="Alex",
        review_text="Great stay. The location was excellent.",
        review_date=date(2026, 5, 6),
        rating=4.8,
        sentiment=ReviewSentiment.POSITIVE,
        language="en",
        country="US",
    )

    assert review.review_id == "review-001"
    assert review.property_id == "property-123"
    assert review.rating == 4.8
    assert review.sentiment == ReviewSentiment.POSITIVE


def test_normalized_review_rejects_rating_above_five() -> None:
    with pytest.raises(ValidationError):
        NormalizedReview(
            review_id="review-002",
            review_text="Impossible rating.",
            rating=5.5,
        )


def test_review_batch_counts_reviews() -> None:
    batch = ReviewBatch(
        reviews=[
            NormalizedReview(
                review_id="review-001",
                review_text="Great stay.",
                rating=5.0,
            ),
            NormalizedReview(
                review_id="review-002",
                review_text="Good location but noisy.",
                rating=3.5,
                sentiment=ReviewSentiment.MIXED,
            ),
        ]
    )

    assert batch.review_count == 2
