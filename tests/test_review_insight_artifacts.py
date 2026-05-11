import json
from decimal import Decimal
from pathlib import Path
from uuid import uuid4

from daedalus.domains.readysetrentables_reviews.review_insight_artifacts import (
    write_review_insights_json,
)
from daedalus.domains.readysetrentables_reviews.review_insight_models import (
    DEFAULT_REVIEW_INSIGHT_PROMPT_NAME,
    DEFAULT_REVIEW_INSIGHT_PROMPT_VERSION,
    ReviewInsightExtractionResult,
    ReviewInsightTheme,
)
from daedalus.model_clients.types import ModelProvider


def test_write_review_insights_json_creates_file(tmp_path: Path) -> None:
    output_path = tmp_path / "review_insights.json"

    write_review_insights_json(result=_extraction_result(), output_path=output_path)

    assert output_path.is_file()


def test_write_review_insights_json_creates_parent_directory(tmp_path: Path) -> None:
    output_path = tmp_path / "nested" / "artifacts" / "review_insights.json"

    write_review_insights_json(result=_extraction_result(), output_path=output_path)

    assert output_path.parent.is_dir()


def test_write_review_insights_json_returns_output_path(tmp_path: Path) -> None:
    output_path = tmp_path / "review_insights.json"

    returned = write_review_insights_json(result=_extraction_result(), output_path=output_path)

    assert returned == output_path


def test_write_review_insights_json_is_valid_json(tmp_path: Path) -> None:
    output_path = tmp_path / "review_insights.json"

    write_review_insights_json(result=_extraction_result(), output_path=output_path)

    data = json.loads(output_path.read_text(encoding="utf-8"))
    assert isinstance(data, dict)


def test_write_review_insights_json_includes_run_id(tmp_path: Path) -> None:
    result = _extraction_result()
    output_path = tmp_path / "review_insights.json"

    write_review_insights_json(result=result, output_path=output_path)

    data = json.loads(output_path.read_text(encoding="utf-8"))
    assert data["run_id"] == str(result.run_id)


def test_write_review_insights_json_includes_provider_as_string(tmp_path: Path) -> None:
    output_path = tmp_path / "review_insights.json"

    write_review_insights_json(result=_extraction_result(), output_path=output_path)

    data = json.loads(output_path.read_text(encoding="utf-8"))
    assert data["provider"] == "fake"


def test_write_review_insights_json_includes_model_name(tmp_path: Path) -> None:
    output_path = tmp_path / "review_insights.json"

    write_review_insights_json(result=_extraction_result(), output_path=output_path)

    data = json.loads(output_path.read_text(encoding="utf-8"))
    assert data["model_name"] == "fake-model"


def test_write_review_insights_json_includes_prompt_identity(tmp_path: Path) -> None:
    output_path = tmp_path / "review_insights.json"

    write_review_insights_json(result=_extraction_result(), output_path=output_path)

    data = json.loads(output_path.read_text(encoding="utf-8"))
    assert data["prompt_name"] == DEFAULT_REVIEW_INSIGHT_PROMPT_NAME
    assert data["prompt_version"] == DEFAULT_REVIEW_INSIGHT_PROMPT_VERSION


def test_write_review_insights_json_includes_themes(tmp_path: Path) -> None:
    theme = ReviewInsightTheme(
        name="location",
        sentiment="positive",
        evidence_count=3,
        summary="Guests value the central location.",
    )
    output_path = tmp_path / "review_insights.json"

    write_review_insights_json(
        result=_extraction_result(themes=[theme]),
        output_path=output_path,
    )

    data = json.loads(output_path.read_text(encoding="utf-8"))
    assert len(data["themes"]) == 1
    assert data["themes"][0]["name"] == "location"
    assert data["themes"][0]["sentiment"] == "positive"
    assert data["themes"][0]["evidence_count"] == 3


def test_write_review_insights_json_includes_strengths_risks_expectations(
    tmp_path: Path,
) -> None:
    output_path = tmp_path / "review_insights.json"

    write_review_insights_json(
        result=_extraction_result(
            strengths=["Central location"],
            risks=["Street noise"],
            guest_expectations=["Self check-in guide"],
        ),
        output_path=output_path,
    )

    data = json.loads(output_path.read_text(encoding="utf-8"))
    assert data["strengths"] == ["Central location"]
    assert data["risks"] == ["Street noise"]
    assert data["guest_expectations"] == ["Self check-in guide"]


def test_write_review_insights_json_includes_raw_insight_summary(tmp_path: Path) -> None:
    output_path = tmp_path / "review_insights.json"

    write_review_insights_json(result=_extraction_result(), output_path=output_path)

    data = json.loads(output_path.read_text(encoding="utf-8"))
    assert data["raw_insight_summary"] == "Location and cleanliness dominate guest feedback."


def test_write_review_insights_json_includes_token_and_cost_when_present(
    tmp_path: Path,
) -> None:
    output_path = tmp_path / "review_insights.json"

    write_review_insights_json(
        result=_extraction_result(
            input_tokens=100,
            output_tokens=50,
            total_tokens=150,
            estimated_cost_usd=Decimal("0.003"),
        ),
        output_path=output_path,
    )

    data = json.loads(output_path.read_text(encoding="utf-8"))
    assert data["input_tokens"] == 100
    assert data["output_tokens"] == 50
    assert data["total_tokens"] == 150
    assert data["estimated_cost_usd"] == "0.003"


def test_write_review_insights_json_token_fields_null_when_absent(tmp_path: Path) -> None:
    output_path = tmp_path / "review_insights.json"

    write_review_insights_json(result=_extraction_result(), output_path=output_path)

    data = json.loads(output_path.read_text(encoding="utf-8"))
    assert data["input_tokens"] is None
    assert data["output_tokens"] is None
    assert data["total_tokens"] is None
    assert data["estimated_cost_usd"] is None


# --- helpers ---


def _extraction_result(
    *,
    themes: list[ReviewInsightTheme] | None = None,
    strengths: list[str] | None = None,
    risks: list[str] | None = None,
    guest_expectations: list[str] | None = None,
    input_tokens: int | None = None,
    output_tokens: int | None = None,
    total_tokens: int | None = None,
    estimated_cost_usd: Decimal | None = None,
) -> ReviewInsightExtractionResult:
    return ReviewInsightExtractionResult(
        run_id=uuid4(),
        provider=ModelProvider.FAKE,
        model_name="fake-model",
        prompt_name=DEFAULT_REVIEW_INSIGHT_PROMPT_NAME,
        prompt_version=DEFAULT_REVIEW_INSIGHT_PROMPT_VERSION,
        themes=themes or [],
        strengths=strengths or [],
        risks=risks or [],
        guest_expectations=guest_expectations or [],
        raw_insight_summary="Location and cleanliness dominate guest feedback.",
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        total_tokens=total_tokens,
        estimated_cost_usd=estimated_cost_usd,
    )
