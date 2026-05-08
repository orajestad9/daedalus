"""Deterministic preprocessing for review theme summary agent inputs."""

from uuid import UUID

from daedalus.domains.readysetrentables_reviews.models import ReviewBatch
from daedalus.domains.readysetrentables_reviews.theme_summary_models import (
    ReviewThemeSummaryInput,
)
from daedalus.model_clients.types import ModelBudget


def build_review_theme_summary_input(
    *,
    run_id: UUID,
    batch: ReviewBatch,
    max_representative_reviews: int = 5,
    budget: ModelBudget | None = None,
) -> ReviewThemeSummaryInput:
    """Build compact, deterministic model input metadata from normalized reviews."""
    if max_representative_reviews < 0:
        msg = "max_representative_reviews cannot be negative"
        raise ValueError(msg)

    ratings = [review.rating for review in batch.reviews if review.rating is not None]
    average_rating = sum(ratings) / len(ratings) if ratings else None
    representative_reviews = [
        review.review_text.strip() for review in batch.reviews if review.review_text.strip()
    ][:max_representative_reviews]

    return ReviewThemeSummaryInput(
        run_id=run_id,
        review_count=batch.review_count,
        average_rating=average_rating,
        representative_reviews=representative_reviews,
        rating_distribution=_rating_distribution(ratings),
        budget=budget,
    )


def _rating_distribution(ratings: list[float]) -> dict[str, int]:
    distribution: dict[str, int] = {}
    for rating in ratings:
        key = _rating_key(rating)
        distribution[key] = distribution.get(key, 0) + 1

    return distribution


def _rating_key(rating: float) -> str:
    if rating.is_integer():
        return str(int(rating))
    return str(rating)
