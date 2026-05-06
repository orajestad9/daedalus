from datetime import date
from enum import StrEnum
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field


class ReviewSentiment(StrEnum):
    """High-level sentiment classification for a guest review."""

    POSITIVE = "positive"
    MIXED = "mixed"
    NEGATIVE = "negative"
    UNKNOWN = "unknown"


class ReviewSource(StrEnum):
    """Supported review data sources."""

    AIRBNB = "airbnb"


class RawReviewRecord(BaseModel):
    """Raw review record captured before normalization.

    This model intentionally allows flexible source_data because raw CSV exports
    can change over time. The normalized model should be stricter.
    """

    model_config = ConfigDict(extra="allow")

    source: ReviewSource = ReviewSource.AIRBNB
    source_data: dict[str, Any]


class NormalizedReview(BaseModel):
    """Clean internal representation of a guest review.

    This is the object downstream agents should consume instead of raw CSV rows.
    """

    review_id: str
    property_id: str | None = None
    source: ReviewSource = ReviewSource.AIRBNB

    reviewer_name: str | None = None
    review_text: str
    review_date: date | None = None

    rating: float | None = Field(default=None, ge=0, le=5)
    sentiment: ReviewSentiment = ReviewSentiment.UNKNOWN

    language: str | None = None
    country: str | None = None

    raw_record: RawReviewRecord | None = None


class ReviewBatch(BaseModel):
    """A batch of normalized reviews processed together in one workflow run."""

    batch_id: UUID = Field(default_factory=uuid4)
    source: ReviewSource = ReviewSource.AIRBNB
    reviews: list[NormalizedReview]

    @property
    def review_count(self) -> int:
        return len(self.reviews)
