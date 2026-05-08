from decimal import Decimal
from uuid import uuid4

import pytest
from pydantic import ValidationError

from daedalus.domains.readysetrentables_reviews.theme_summary_models import (
    DEFAULT_REVIEW_THEME_PROMPT_NAME,
    DEFAULT_REVIEW_THEME_PROMPT_VERSION,
    ReviewThemeSummaryInput,
    ReviewThemeSummaryResult,
    ReviewThemeSummaryTheme,
)
from daedalus.model_clients.types import ModelBudget, ModelProvider


def test_review_theme_summary_input_accepts_valid_compact_input() -> None:
    budget = ModelBudget(max_total_tokens=500, allowed_providers=(ModelProvider.FAKE,))
    model = ReviewThemeSummaryInput(
        run_id=uuid4(),
        review_count=8,
        average_rating=4.5,
        representative_reviews=["Great location.", "Easy check-in."],
        rating_distribution={"5": 6, "4": 2},
        budget=budget,
    )

    assert model.review_count == 8
    assert model.average_rating == 4.5
    assert model.representative_reviews == ["Great location.", "Easy check-in."]
    assert model.rating_distribution == {"5": 6, "4": 2}
    assert model.budget == budget


def test_review_theme_summary_input_default_prompt_identity() -> None:
    model = ReviewThemeSummaryInput(run_id=uuid4(), review_count=0)

    assert model.prompt_name == DEFAULT_REVIEW_THEME_PROMPT_NAME
    assert model.prompt_version == DEFAULT_REVIEW_THEME_PROMPT_VERSION


def test_review_theme_summary_input_default_representative_reviews_are_independent() -> None:
    first = ReviewThemeSummaryInput(run_id=uuid4(), review_count=0)
    second = ReviewThemeSummaryInput(run_id=uuid4(), review_count=0)

    first.representative_reviews.append("Quiet stay.")

    assert second.representative_reviews == []


def test_review_theme_summary_input_default_rating_distribution_is_independent() -> None:
    first = ReviewThemeSummaryInput(run_id=uuid4(), review_count=0)
    second = ReviewThemeSummaryInput(run_id=uuid4(), review_count=0)

    first.rating_distribution["5"] = 1

    assert second.rating_distribution == {}


def test_review_theme_summary_input_rejects_negative_review_count() -> None:
    with pytest.raises(ValidationError):
        ReviewThemeSummaryInput(run_id=uuid4(), review_count=-1)


@pytest.mark.parametrize("average_rating", [-0.1, 5.1])
def test_review_theme_summary_input_rejects_invalid_average_rating(
    average_rating: float,
) -> None:
    with pytest.raises(ValidationError):
        ReviewThemeSummaryInput(
            run_id=uuid4(),
            review_count=1,
            average_rating=average_rating,
        )


def test_review_theme_summary_input_rejects_negative_rating_distribution_count() -> None:
    with pytest.raises(ValidationError):
        ReviewThemeSummaryInput(
            run_id=uuid4(),
            review_count=1,
            rating_distribution={"5": -1},
        )


def test_review_theme_summary_theme_accepts_valid_data() -> None:
    theme = ReviewThemeSummaryTheme(
        name="location",
        description="Guests mention the convenient location.",
        sentiment="positive",
        supporting_review_count=3,
    )

    assert theme.name == "location"
    assert theme.sentiment == "positive"
    assert theme.supporting_review_count == 3


def test_review_theme_summary_theme_rejects_negative_supporting_review_count() -> None:
    with pytest.raises(ValidationError):
        ReviewThemeSummaryTheme(
            name="check-in",
            description="Guests mention arrival details.",
            sentiment="mixed",
            supporting_review_count=-1,
        )


def test_review_theme_summary_result_accepts_valid_data() -> None:
    run_id = uuid4()
    result = ReviewThemeSummaryResult(
        run_id=run_id,
        summary_text="Guests frequently praise the location.",
        themes=[
            ReviewThemeSummaryTheme(
                name="location",
                description="Guests mention the convenient location.",
                sentiment="positive",
                supporting_review_count=3,
            )
        ],
        prompt_name=DEFAULT_REVIEW_THEME_PROMPT_NAME,
        prompt_version=DEFAULT_REVIEW_THEME_PROMPT_VERSION,
        model_provider=ModelProvider.FAKE,
        model_name="fake-model",
        input_tokens=10,
        output_tokens=20,
        total_tokens=30,
        estimated_cost_usd=Decimal("0"),
    )

    assert result.run_id == run_id
    assert result.summary_text == "Guests frequently praise the location."
    assert len(result.themes) == 1
    assert result.model_provider == ModelProvider.FAKE


def test_review_theme_summary_result_default_themes_are_independent() -> None:
    first = _summary_result()
    second = _summary_result()

    first.themes.append(
        ReviewThemeSummaryTheme(
            name="cleanliness",
            description="Guests mention cleanliness.",
            sentiment="positive",
        )
    )

    assert second.themes == []


@pytest.mark.parametrize(
    "field_name",
    [
        "input_tokens",
        "output_tokens",
        "total_tokens",
        "estimated_cost_usd",
    ],
)
def test_review_theme_summary_result_rejects_negative_token_or_cost_fields(
    field_name: str,
) -> None:
    with pytest.raises(ValidationError):
        if field_name == "input_tokens":
            _summary_result(input_tokens=-1)
        elif field_name == "output_tokens":
            _summary_result(output_tokens=-1)
        elif field_name == "total_tokens":
            _summary_result(total_tokens=-1)
        else:
            _summary_result(estimated_cost_usd=Decimal("-0.01"))


def test_review_theme_summary_result_json_serialization_uses_provider_string() -> None:
    result = _summary_result(model_provider=ModelProvider.FAKE)

    assert '"model_provider":"fake"' in result.model_dump_json()


def _summary_result(
    *,
    model_provider: ModelProvider = ModelProvider.FAKE,
    input_tokens: int | None = None,
    output_tokens: int | None = None,
    total_tokens: int | None = None,
    estimated_cost_usd: Decimal | None = None,
) -> ReviewThemeSummaryResult:
    return ReviewThemeSummaryResult(
        run_id=uuid4(),
        summary_text="Guests mention location and check-in.",
        prompt_name=DEFAULT_REVIEW_THEME_PROMPT_NAME,
        prompt_version=DEFAULT_REVIEW_THEME_PROMPT_VERSION,
        model_provider=model_provider,
        model_name="fake-model",
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        total_tokens=total_tokens,
        estimated_cost_usd=estimated_cost_usd,
    )
