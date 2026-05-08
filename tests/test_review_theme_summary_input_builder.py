from uuid import uuid4

import pytest

from daedalus.domains.readysetrentables_reviews.models import NormalizedReview, ReviewBatch
from daedalus.domains.readysetrentables_reviews.theme_summary_input_builder import (
    build_review_theme_summary_input,
)
from daedalus.domains.readysetrentables_reviews.theme_summary_models import (
    DEFAULT_REVIEW_THEME_PROMPT_NAME,
    DEFAULT_REVIEW_THEME_PROMPT_VERSION,
    ReviewThemeSummaryInput,
)
from daedalus.model_clients.types import ModelBudget, ModelProvider


def test_builds_review_theme_summary_input_from_sample_review_batch() -> None:
    model = build_review_theme_summary_input(run_id=uuid4(), batch=_review_batch())

    assert isinstance(model, ReviewThemeSummaryInput)


def test_build_review_theme_summary_input_preserves_run_id() -> None:
    run_id = uuid4()

    model = build_review_theme_summary_input(run_id=run_id, batch=_review_batch())

    assert model.run_id == run_id


def test_build_review_theme_summary_input_sets_review_count() -> None:
    model = build_review_theme_summary_input(run_id=uuid4(), batch=_review_batch())

    assert model.review_count == 4


def test_build_review_theme_summary_input_computes_average_rating() -> None:
    model = build_review_theme_summary_input(run_id=uuid4(), batch=_review_batch())

    assert model.average_rating == pytest.approx(4.375)


def test_build_review_theme_summary_input_computes_rating_distribution() -> None:
    model = build_review_theme_summary_input(run_id=uuid4(), batch=_review_batch())

    assert model.rating_distribution == {"5": 2, "4": 1, "3.5": 1}


def test_build_review_theme_summary_input_selects_first_n_non_empty_reviews() -> None:
    model = build_review_theme_summary_input(
        run_id=uuid4(),
        batch=_review_batch(),
        max_representative_reviews=2,
    )

    assert model.representative_reviews == [
        "Great location and easy arrival.",
        "Clean apartment with helpful instructions.",
    ]


def test_build_review_theme_summary_input_allows_zero_representative_reviews() -> None:
    model = build_review_theme_summary_input(
        run_id=uuid4(),
        batch=_review_batch(),
        max_representative_reviews=0,
    )

    assert model.representative_reviews == []


def test_build_review_theme_summary_input_rejects_negative_representative_review_limit() -> None:
    with pytest.raises(ValueError, match="max_representative_reviews"):
        build_review_theme_summary_input(
            run_id=uuid4(),
            batch=_review_batch(),
            max_representative_reviews=-1,
        )


def test_build_review_theme_summary_input_preserves_budget() -> None:
    budget = ModelBudget(max_total_tokens=250, allowed_providers=(ModelProvider.FAKE,))

    model = build_review_theme_summary_input(
        run_id=uuid4(),
        batch=_review_batch(),
        budget=budget,
    )

    assert model.budget == budget


def test_build_review_theme_summary_input_preserves_prompt_defaults() -> None:
    model = build_review_theme_summary_input(run_id=uuid4(), batch=_review_batch())

    assert model.prompt_name == DEFAULT_REVIEW_THEME_PROMPT_NAME
    assert model.prompt_version == DEFAULT_REVIEW_THEME_PROMPT_VERSION


def test_build_review_theme_summary_input_handles_batch_without_ratings() -> None:
    batch = ReviewBatch(
        reviews=[
            NormalizedReview(review_id="review-001", review_text="Quiet and tidy."),
            NormalizedReview(review_id="review-002", review_text="Helpful host."),
        ]
    )

    model = build_review_theme_summary_input(run_id=uuid4(), batch=batch)

    assert model.average_rating is None
    assert model.rating_distribution == {}


def _review_batch() -> ReviewBatch:
    return ReviewBatch(
        reviews=[
            NormalizedReview(
                review_id="review-001",
                review_text="Great location and easy arrival.",
                rating=5.0,
            ),
            NormalizedReview(
                review_id="review-002",
                review_text="Clean apartment with helpful instructions.",
                rating=4.0,
            ),
            NormalizedReview(
                review_id="review-003",
                review_text="",
                rating=3.5,
            ),
            NormalizedReview(
                review_id="review-004",
                review_text="Bright space near transit.",
                rating=5.0,
            ),
        ]
    )
