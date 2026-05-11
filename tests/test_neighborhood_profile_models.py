import json
from decimal import Decimal
from uuid import uuid4

import pytest
from pydantic import ValidationError

from daedalus.domains.readysetrentables_reviews.neighborhood_profile_models import (
    DEFAULT_NEIGHBORHOOD_PROFILE_PROMPT_NAME,
    DEFAULT_NEIGHBORHOOD_PROFILE_PROMPT_VERSION,
    NeighborhoodProfileInput,
    NeighborhoodProfileResult,
    NeighborhoodProfileSection,
)
from daedalus.domains.readysetrentables_reviews.review_insight_models import (
    DEFAULT_REVIEW_INSIGHT_PROMPT_NAME,
    DEFAULT_REVIEW_INSIGHT_PROMPT_VERSION,
    ReviewInsightExtractionResult,
)
from daedalus.model_clients.types import ModelProvider


# --- NeighborhoodProfileInput ---


def test_neighborhood_profile_input_accepts_valid_data() -> None:
    insights = _extraction_result()
    model = NeighborhoodProfileInput(
        run_id=uuid4(),
        market_name="Austin",
        neighborhood_name="East Side",
        property_type="apartment",
        review_insights=insights,
    )

    assert model.market_name == "Austin"
    assert model.neighborhood_name == "East Side"
    assert model.property_type == "apartment"
    assert model.review_insights == insights


def test_neighborhood_profile_input_default_prompt_identity() -> None:
    model = NeighborhoodProfileInput(
        run_id=uuid4(),
        market_name="Austin",
        neighborhood_name="East Side",
        review_insights=_extraction_result(),
    )

    assert model.prompt_name == DEFAULT_NEIGHBORHOOD_PROFILE_PROMPT_NAME
    assert model.prompt_version == DEFAULT_NEIGHBORHOOD_PROFILE_PROMPT_VERSION


def test_neighborhood_profile_input_optional_fields_default_to_none() -> None:
    model = NeighborhoodProfileInput(
        run_id=uuid4(),
        market_name="Austin",
        neighborhood_name="East Side",
        review_insights=_extraction_result(),
    )

    assert model.property_type is None
    assert model.source_artifact_path is None


def test_neighborhood_profile_input_rejects_blank_market_name() -> None:
    with pytest.raises(ValidationError):
        NeighborhoodProfileInput(
            run_id=uuid4(),
            market_name="   ",
            neighborhood_name="East Side",
            review_insights=_extraction_result(),
        )


def test_neighborhood_profile_input_rejects_blank_neighborhood_name() -> None:
    with pytest.raises(ValidationError):
        NeighborhoodProfileInput(
            run_id=uuid4(),
            market_name="Austin",
            neighborhood_name="   ",
            review_insights=_extraction_result(),
        )


def test_neighborhood_profile_input_rejects_blank_property_type_when_provided() -> None:
    with pytest.raises(ValidationError):
        NeighborhoodProfileInput(
            run_id=uuid4(),
            market_name="Austin",
            neighborhood_name="East Side",
            property_type="   ",
            review_insights=_extraction_result(),
        )


@pytest.mark.parametrize("field_name", ["prompt_name", "prompt_version"])
def test_neighborhood_profile_input_rejects_blank_prompt_fields(field_name: str) -> None:
    with pytest.raises(ValidationError):
        if field_name == "prompt_name":
            NeighborhoodProfileInput(
                run_id=uuid4(),
                market_name="Austin",
                neighborhood_name="East Side",
                review_insights=_extraction_result(),
                prompt_name="   ",
            )
        else:
            NeighborhoodProfileInput(
                run_id=uuid4(),
                market_name="Austin",
                neighborhood_name="East Side",
                review_insights=_extraction_result(),
                prompt_version="   ",
            )


def test_neighborhood_profile_input_nested_review_insights_serializes() -> None:
    model = NeighborhoodProfileInput(
        run_id=uuid4(),
        market_name="Austin",
        neighborhood_name="East Side",
        review_insights=_extraction_result(),
    )

    data = json.loads(model.model_dump_json())
    assert "review_insights" in data
    assert data["review_insights"]["model_name"] == "fake-model"
    assert data["review_insights"]["provider"] == "fake"


# --- NeighborhoodProfileSection ---


def test_neighborhood_profile_section_accepts_valid_data() -> None:
    section = NeighborhoodProfileSection(
        heading="Location",
        body="The neighborhood offers walkable access to amenities.",
    )

    assert section.heading == "Location"
    assert section.body == "The neighborhood offers walkable access to amenities."


def test_neighborhood_profile_section_rejects_blank_heading() -> None:
    with pytest.raises(ValidationError):
        NeighborhoodProfileSection(heading="   ", body="Some content.")


def test_neighborhood_profile_section_rejects_blank_body() -> None:
    with pytest.raises(ValidationError):
        NeighborhoodProfileSection(heading="Location", body="   ")


# --- NeighborhoodProfileResult ---


def test_neighborhood_profile_result_accepts_valid_data() -> None:
    run_id = uuid4()
    result = NeighborhoodProfileResult(
        run_id=run_id,
        provider=ModelProvider.FAKE,
        model_name="fake-model",
        prompt_name=DEFAULT_NEIGHBORHOOD_PROFILE_PROMPT_NAME,
        prompt_version=DEFAULT_NEIGHBORHOOD_PROFILE_PROMPT_VERSION,
        market_name="Austin",
        neighborhood_name="East Side",
        profile_title="East Side Austin Neighborhood Profile",
        summary="A vibrant neighborhood with strong guest appeal.",
        sections=[
            NeighborhoodProfileSection(
                heading="Location",
                body="Walkable access to dining and entertainment.",
            )
        ],
        investment_highlights=["High occupancy rates"],
        guest_experience_notes=["Guests appreciate the local coffee shops"],
        risks=["Street noise on weekends"],
        markdown="# East Side Austin\n\nA vibrant neighborhood.",
        input_tokens=200,
        output_tokens=400,
        total_tokens=600,
        estimated_cost_usd=Decimal("0.012"),
    )

    assert result.run_id == run_id
    assert result.provider == ModelProvider.FAKE
    assert result.market_name == "Austin"
    assert result.neighborhood_name == "East Side"
    assert result.profile_title == "East Side Austin Neighborhood Profile"
    assert result.summary == "A vibrant neighborhood with strong guest appeal."
    assert len(result.sections) == 1
    assert result.investment_highlights == ["High occupancy rates"]
    assert result.guest_experience_notes == ["Guests appreciate the local coffee shops"]
    assert result.risks == ["Street noise on weekends"]
    assert result.input_tokens == 200
    assert result.total_tokens == 600
    assert result.estimated_cost_usd == Decimal("0.012")


def test_neighborhood_profile_result_sections_default_is_independent() -> None:
    first = _profile_result()
    second = _profile_result()

    first.sections.append(
        NeighborhoodProfileSection(heading="Transport", body="Easy transit access.")
    )

    assert second.sections == []


def test_neighborhood_profile_result_investment_highlights_default_is_independent() -> None:
    first = _profile_result()
    second = _profile_result()

    first.investment_highlights.append("High demand area")

    assert second.investment_highlights == []


def test_neighborhood_profile_result_guest_experience_notes_default_is_independent() -> None:
    first = _profile_result()
    second = _profile_result()

    first.guest_experience_notes.append("Close to attractions")

    assert second.guest_experience_notes == []


def test_neighborhood_profile_result_risks_default_is_independent() -> None:
    first = _profile_result()
    second = _profile_result()

    first.risks.append("Limited parking")

    assert second.risks == []


@pytest.mark.parametrize("field_name", ["model_name", "prompt_name", "prompt_version"])
def test_neighborhood_profile_result_rejects_blank_identity_fields(field_name: str) -> None:
    with pytest.raises(ValidationError):
        if field_name == "model_name":
            _profile_result(model_name="   ")
        elif field_name == "prompt_name":
            _profile_result(prompt_name="   ")
        else:
            _profile_result(prompt_version="   ")


@pytest.mark.parametrize(
    "field_name",
    ["market_name", "neighborhood_name", "profile_title", "summary", "markdown"],
)
def test_neighborhood_profile_result_rejects_blank_required_text_fields(
    field_name: str,
) -> None:
    with pytest.raises(ValidationError):
        if field_name == "market_name":
            _profile_result(market_name="   ")
        elif field_name == "neighborhood_name":
            _profile_result(neighborhood_name="   ")
        elif field_name == "profile_title":
            _profile_result(profile_title="   ")
        elif field_name == "summary":
            _profile_result(summary="   ")
        else:
            _profile_result(markdown="   ")


@pytest.mark.parametrize("list_field", ["investment_highlights", "guest_experience_notes", "risks"])
def test_neighborhood_profile_result_rejects_blank_list_entries(list_field: str) -> None:
    with pytest.raises(ValidationError):
        if list_field == "investment_highlights":
            _profile_result(investment_highlights=["valid", "  "])
        elif list_field == "guest_experience_notes":
            _profile_result(guest_experience_notes=["valid", "  "])
        else:
            _profile_result(risks=["valid", "  "])


@pytest.mark.parametrize("field_name", ["input_tokens", "output_tokens", "total_tokens"])
def test_neighborhood_profile_result_rejects_negative_token_fields(field_name: str) -> None:
    with pytest.raises(ValidationError):
        if field_name == "input_tokens":
            _profile_result(input_tokens=-1)
        elif field_name == "output_tokens":
            _profile_result(output_tokens=-1)
        else:
            _profile_result(total_tokens=-1)


def test_neighborhood_profile_result_rejects_negative_estimated_cost() -> None:
    with pytest.raises(ValidationError):
        _profile_result(estimated_cost_usd=Decimal("-0.01"))


def test_neighborhood_profile_result_json_serializes_provider_and_decimal() -> None:
    result = _profile_result(
        provider=ModelProvider.FAKE,
        estimated_cost_usd=Decimal("0.0042"),
    )

    serialized = result.model_dump_json()

    assert '"provider":"fake"' in serialized
    assert "0.0042" in serialized


# --- helpers ---


def _extraction_result() -> ReviewInsightExtractionResult:
    return ReviewInsightExtractionResult(
        run_id=uuid4(),
        provider=ModelProvider.FAKE,
        model_name="fake-model",
        prompt_name=DEFAULT_REVIEW_INSIGHT_PROMPT_NAME,
        prompt_version=DEFAULT_REVIEW_INSIGHT_PROMPT_VERSION,
        raw_insight_summary="Guests mention location and cleanliness.",
    )


def _profile_result(
    *,
    model_name: str = "fake-model",
    prompt_name: str = DEFAULT_NEIGHBORHOOD_PROFILE_PROMPT_NAME,
    prompt_version: str = DEFAULT_NEIGHBORHOOD_PROFILE_PROMPT_VERSION,
    market_name: str = "Austin",
    neighborhood_name: str = "East Side",
    profile_title: str = "East Side Austin Neighborhood Profile",
    summary: str = "A vibrant neighborhood with strong guest appeal.",
    markdown: str = "# East Side Austin\n\nA vibrant neighborhood.",
    provider: ModelProvider = ModelProvider.FAKE,
    investment_highlights: list[str] | None = None,
    guest_experience_notes: list[str] | None = None,
    risks: list[str] | None = None,
    input_tokens: int | None = None,
    output_tokens: int | None = None,
    total_tokens: int | None = None,
    estimated_cost_usd: Decimal | None = None,
) -> NeighborhoodProfileResult:
    return NeighborhoodProfileResult(
        run_id=uuid4(),
        provider=provider,
        model_name=model_name,
        prompt_name=prompt_name,
        prompt_version=prompt_version,
        market_name=market_name,
        neighborhood_name=neighborhood_name,
        profile_title=profile_title,
        summary=summary,
        markdown=markdown,
        investment_highlights=investment_highlights or [],
        guest_experience_notes=guest_experience_notes or [],
        risks=risks or [],
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        total_tokens=total_tokens,
        estimated_cost_usd=estimated_cost_usd,
    )
