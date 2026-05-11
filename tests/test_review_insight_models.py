from decimal import Decimal
from pathlib import Path
from uuid import uuid4

import pytest
from pydantic import ValidationError

from daedalus.domains.readysetrentables_reviews.review_insight_models import (
    DEFAULT_REVIEW_INSIGHT_PROMPT_NAME,
    DEFAULT_REVIEW_INSIGHT_PROMPT_VERSION,
    ReviewInsightExtractionInput,
    ReviewInsightExtractionResult,
    ReviewInsightTheme,
)
from daedalus.model_clients.types import ModelProvider


# --- ReviewInsightExtractionInput ---


def test_review_insight_extraction_input_accepts_valid_data() -> None:
    model = ReviewInsightExtractionInput(
        run_id=uuid4(),
        review_count=5,
        market_name="Austin",
        neighborhood_name="East Side",
        property_type="apartment",
        average_rating=4.2,
        rating_categories={"cleanliness": 4.5, "location": 4.8},
        representative_reviews=["Great stay.", "Easy check-in."],
        source_artifact_path=Path("artifacts/normalized_reviews.json"),
    )

    assert model.review_count == 5
    assert model.market_name == "Austin"
    assert model.neighborhood_name == "East Side"
    assert model.property_type == "apartment"
    assert model.average_rating == 4.2
    assert model.rating_categories == {"cleanliness": 4.5, "location": 4.8}
    assert model.representative_reviews == ["Great stay.", "Easy check-in."]
    assert model.source_artifact_path == Path("artifacts/normalized_reviews.json")


def test_review_insight_extraction_input_default_prompt_identity() -> None:
    model = ReviewInsightExtractionInput(run_id=uuid4(), review_count=0)

    assert model.prompt_name == DEFAULT_REVIEW_INSIGHT_PROMPT_NAME
    assert model.prompt_version == DEFAULT_REVIEW_INSIGHT_PROMPT_VERSION


def test_review_insight_extraction_input_optional_fields_default_to_none() -> None:
    model = ReviewInsightExtractionInput(run_id=uuid4(), review_count=0)

    assert model.market_name is None
    assert model.neighborhood_name is None
    assert model.property_type is None
    assert model.average_rating is None
    assert model.source_artifact_path is None


def test_review_insight_extraction_input_rejects_negative_review_count() -> None:
    with pytest.raises(ValidationError):
        ReviewInsightExtractionInput(run_id=uuid4(), review_count=-1)


@pytest.mark.parametrize("field_name", ["market_name", "neighborhood_name", "property_type"])
def test_review_insight_extraction_input_rejects_blank_optional_string_fields(
    field_name: str,
) -> None:
    with pytest.raises(ValidationError):
        if field_name == "market_name":
            ReviewInsightExtractionInput(run_id=uuid4(), review_count=1, market_name="   ")
        elif field_name == "neighborhood_name":
            ReviewInsightExtractionInput(run_id=uuid4(), review_count=1, neighborhood_name="   ")
        else:
            ReviewInsightExtractionInput(run_id=uuid4(), review_count=1, property_type="   ")


def test_review_insight_extraction_input_rating_categories_default_is_independent() -> None:
    first = ReviewInsightExtractionInput(run_id=uuid4(), review_count=0)
    second = ReviewInsightExtractionInput(run_id=uuid4(), review_count=0)

    first.rating_categories["location"] = 4.0

    assert second.rating_categories == {}


def test_review_insight_extraction_input_rejects_blank_rating_category_key() -> None:
    with pytest.raises(ValidationError):
        ReviewInsightExtractionInput(
            run_id=uuid4(),
            review_count=1,
            rating_categories={"   ": 4.0},
        )


def test_review_insight_extraction_input_rejects_rating_category_value_below_zero() -> None:
    with pytest.raises(ValidationError):
        ReviewInsightExtractionInput(
            run_id=uuid4(),
            review_count=1,
            rating_categories={"cleanliness": -0.1},
        )


def test_review_insight_extraction_input_rejects_rating_category_value_above_five() -> None:
    with pytest.raises(ValidationError):
        ReviewInsightExtractionInput(
            run_id=uuid4(),
            review_count=1,
            rating_categories={"cleanliness": 5.1},
        )


def test_review_insight_extraction_input_rating_category_accepts_boundary_values() -> None:
    model = ReviewInsightExtractionInput(
        run_id=uuid4(),
        review_count=1,
        rating_categories={"low": 0.0, "high": 5.0},
    )

    assert model.rating_categories == {"low": 0.0, "high": 5.0}


def test_review_insight_extraction_input_representative_reviews_default_is_independent() -> None:
    first = ReviewInsightExtractionInput(run_id=uuid4(), review_count=0)
    second = ReviewInsightExtractionInput(run_id=uuid4(), review_count=0)

    first.representative_reviews.append("Good stay.")

    assert second.representative_reviews == []


def test_review_insight_extraction_input_rejects_blank_representative_review() -> None:
    with pytest.raises(ValidationError):
        ReviewInsightExtractionInput(
            run_id=uuid4(),
            review_count=1,
            representative_reviews=["Good stay.", "  "],
        )


# --- ReviewInsightTheme ---


def test_review_insight_theme_accepts_valid_data() -> None:
    theme = ReviewInsightTheme(
        name="location",
        sentiment="positive",
        evidence_count=4,
        summary="Guests frequently praise the walkable neighborhood.",
    )

    assert theme.name == "location"
    assert theme.sentiment == "positive"
    assert theme.evidence_count == 4
    assert theme.summary == "Guests frequently praise the walkable neighborhood."


@pytest.mark.parametrize("field_name", ["name", "sentiment", "summary"])
def test_review_insight_theme_rejects_blank_required_string(field_name: str) -> None:
    with pytest.raises(ValidationError):
        if field_name == "name":
            ReviewInsightTheme(
                name="   ", sentiment="positive", evidence_count=1, summary="Good area."
            )
        elif field_name == "sentiment":
            ReviewInsightTheme(
                name="location", sentiment="   ", evidence_count=1, summary="Good area."
            )
        else:
            ReviewInsightTheme(
                name="location", sentiment="positive", evidence_count=1, summary="   "
            )


def test_review_insight_theme_rejects_negative_evidence_count() -> None:
    with pytest.raises(ValidationError):
        ReviewInsightTheme(
            name="check-in",
            sentiment="neutral",
            evidence_count=-1,
            summary="Guests mention arrival details.",
        )


# --- ReviewInsightExtractionResult ---


def test_review_insight_extraction_result_accepts_valid_data() -> None:
    run_id = uuid4()
    result = ReviewInsightExtractionResult(
        run_id=run_id,
        provider=ModelProvider.OLLAMA,
        model_name="llama3",
        prompt_name=DEFAULT_REVIEW_INSIGHT_PROMPT_NAME,
        prompt_version=DEFAULT_REVIEW_INSIGHT_PROMPT_VERSION,
        themes=[
            ReviewInsightTheme(
                name="location",
                sentiment="positive",
                evidence_count=3,
                summary="Guests value the central location.",
            )
        ],
        strengths=["Central location", "Clean space"],
        risks=["Noise from street"],
        guest_expectations=["Self check-in instructions"],
        raw_insight_summary="Location and cleanliness dominate guest feedback.",
        input_tokens=120,
        output_tokens=80,
        total_tokens=200,
        estimated_cost_usd=Decimal("0.002"),
    )

    assert result.run_id == run_id
    assert result.provider == ModelProvider.OLLAMA
    assert result.model_name == "llama3"
    assert len(result.themes) == 1
    assert result.strengths == ["Central location", "Clean space"]
    assert result.risks == ["Noise from street"]
    assert result.guest_expectations == ["Self check-in instructions"]
    assert result.raw_insight_summary == "Location and cleanliness dominate guest feedback."
    assert result.input_tokens == 120
    assert result.total_tokens == 200
    assert result.estimated_cost_usd == Decimal("0.002")


def test_review_insight_extraction_result_themes_default_is_independent() -> None:
    first = _extraction_result()
    second = _extraction_result()

    first.themes.append(
        ReviewInsightTheme(
            name="cleanliness",
            sentiment="positive",
            evidence_count=2,
            summary="Guests mention cleanliness.",
        )
    )

    assert second.themes == []


def test_review_insight_extraction_result_strengths_default_is_independent() -> None:
    first = _extraction_result()
    second = _extraction_result()

    first.strengths.append("Central location")

    assert second.strengths == []


def test_review_insight_extraction_result_risks_default_is_independent() -> None:
    first = _extraction_result()
    second = _extraction_result()

    first.risks.append("Noise")

    assert second.risks == []


def test_review_insight_extraction_result_guest_expectations_default_is_independent() -> None:
    first = _extraction_result()
    second = _extraction_result()

    first.guest_expectations.append("Self check-in guide")

    assert second.guest_expectations == []


@pytest.mark.parametrize("field_name", ["model_name", "prompt_name", "prompt_version"])
def test_review_insight_extraction_result_rejects_blank_required_string(
    field_name: str,
) -> None:
    with pytest.raises(ValidationError):
        if field_name == "model_name":
            ReviewInsightExtractionResult(
                run_id=uuid4(),
                provider=ModelProvider.FAKE,
                model_name="   ",
                prompt_name=DEFAULT_REVIEW_INSIGHT_PROMPT_NAME,
                prompt_version=DEFAULT_REVIEW_INSIGHT_PROMPT_VERSION,
                raw_insight_summary="Guests mention location.",
            )
        elif field_name == "prompt_name":
            ReviewInsightExtractionResult(
                run_id=uuid4(),
                provider=ModelProvider.FAKE,
                model_name="fake-model",
                prompt_name="   ",
                prompt_version=DEFAULT_REVIEW_INSIGHT_PROMPT_VERSION,
                raw_insight_summary="Guests mention location.",
            )
        else:
            ReviewInsightExtractionResult(
                run_id=uuid4(),
                provider=ModelProvider.FAKE,
                model_name="fake-model",
                prompt_name=DEFAULT_REVIEW_INSIGHT_PROMPT_NAME,
                prompt_version="   ",
                raw_insight_summary="Guests mention location.",
            )


def test_review_insight_extraction_result_rejects_blank_raw_insight_summary() -> None:
    with pytest.raises(ValidationError):
        ReviewInsightExtractionResult(
            run_id=uuid4(),
            provider=ModelProvider.FAKE,
            model_name="fake-model",
            prompt_name=DEFAULT_REVIEW_INSIGHT_PROMPT_NAME,
            prompt_version=DEFAULT_REVIEW_INSIGHT_PROMPT_VERSION,
            raw_insight_summary="   ",
        )


@pytest.mark.parametrize("list_field", ["strengths", "risks", "guest_expectations"])
def test_review_insight_extraction_result_rejects_blank_list_entries(
    list_field: str,
) -> None:
    with pytest.raises(ValidationError):
        if list_field == "strengths":
            ReviewInsightExtractionResult(
                run_id=uuid4(),
                provider=ModelProvider.FAKE,
                model_name="fake-model",
                prompt_name=DEFAULT_REVIEW_INSIGHT_PROMPT_NAME,
                prompt_version=DEFAULT_REVIEW_INSIGHT_PROMPT_VERSION,
                raw_insight_summary="Guests mention location.",
                strengths=["valid entry", "  "],
            )
        elif list_field == "risks":
            ReviewInsightExtractionResult(
                run_id=uuid4(),
                provider=ModelProvider.FAKE,
                model_name="fake-model",
                prompt_name=DEFAULT_REVIEW_INSIGHT_PROMPT_NAME,
                prompt_version=DEFAULT_REVIEW_INSIGHT_PROMPT_VERSION,
                raw_insight_summary="Guests mention location.",
                risks=["valid entry", "  "],
            )
        else:
            ReviewInsightExtractionResult(
                run_id=uuid4(),
                provider=ModelProvider.FAKE,
                model_name="fake-model",
                prompt_name=DEFAULT_REVIEW_INSIGHT_PROMPT_NAME,
                prompt_version=DEFAULT_REVIEW_INSIGHT_PROMPT_VERSION,
                raw_insight_summary="Guests mention location.",
                guest_expectations=["valid entry", "  "],
            )


@pytest.mark.parametrize("field_name", ["input_tokens", "output_tokens", "total_tokens"])
def test_review_insight_extraction_result_rejects_negative_token_fields(
    field_name: str,
) -> None:
    with pytest.raises(ValidationError):
        if field_name == "input_tokens":
            ReviewInsightExtractionResult(
                run_id=uuid4(),
                provider=ModelProvider.FAKE,
                model_name="fake-model",
                prompt_name=DEFAULT_REVIEW_INSIGHT_PROMPT_NAME,
                prompt_version=DEFAULT_REVIEW_INSIGHT_PROMPT_VERSION,
                raw_insight_summary="Guests mention location.",
                input_tokens=-1,
            )
        elif field_name == "output_tokens":
            ReviewInsightExtractionResult(
                run_id=uuid4(),
                provider=ModelProvider.FAKE,
                model_name="fake-model",
                prompt_name=DEFAULT_REVIEW_INSIGHT_PROMPT_NAME,
                prompt_version=DEFAULT_REVIEW_INSIGHT_PROMPT_VERSION,
                raw_insight_summary="Guests mention location.",
                output_tokens=-1,
            )
        else:
            ReviewInsightExtractionResult(
                run_id=uuid4(),
                provider=ModelProvider.FAKE,
                model_name="fake-model",
                prompt_name=DEFAULT_REVIEW_INSIGHT_PROMPT_NAME,
                prompt_version=DEFAULT_REVIEW_INSIGHT_PROMPT_VERSION,
                raw_insight_summary="Guests mention location.",
                total_tokens=-1,
            )


def test_review_insight_extraction_result_rejects_negative_estimated_cost() -> None:
    with pytest.raises(ValidationError):
        ReviewInsightExtractionResult(
            run_id=uuid4(),
            provider=ModelProvider.FAKE,
            model_name="fake-model",
            prompt_name=DEFAULT_REVIEW_INSIGHT_PROMPT_NAME,
            prompt_version=DEFAULT_REVIEW_INSIGHT_PROMPT_VERSION,
            raw_insight_summary="Guests mention location.",
            estimated_cost_usd=Decimal("-0.01"),
        )


def test_review_insight_extraction_result_json_serializes_provider_and_decimal() -> None:
    result = _extraction_result(
        provider=ModelProvider.OLLAMA,
        estimated_cost_usd=Decimal("0.0015"),
    )

    serialized = result.model_dump_json()

    assert '"provider":"ollama"' in serialized
    assert "0.0015" in serialized


# --- helpers ---


def _extraction_result(
    *,
    provider: ModelProvider = ModelProvider.FAKE,
    estimated_cost_usd: Decimal | None = None,
) -> ReviewInsightExtractionResult:
    return ReviewInsightExtractionResult(
        run_id=uuid4(),
        provider=provider,
        model_name="fake-model",
        prompt_name=DEFAULT_REVIEW_INSIGHT_PROMPT_NAME,
        prompt_version=DEFAULT_REVIEW_INSIGHT_PROMPT_VERSION,
        raw_insight_summary="Guests mention location and cleanliness.",
        estimated_cost_usd=estimated_cost_usd,
    )
