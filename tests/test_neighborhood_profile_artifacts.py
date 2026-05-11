import json
from decimal import Decimal
from pathlib import Path
from uuid import uuid4

import pytest

from daedalus.domains.readysetrentables_reviews.neighborhood_profile_artifacts import (
    write_neighborhood_profile_json,
    write_neighborhood_profile_markdown,
)
from daedalus.domains.readysetrentables_reviews.neighborhood_profile_models import (
    DEFAULT_NEIGHBORHOOD_PROFILE_PROMPT_NAME,
    DEFAULT_NEIGHBORHOOD_PROFILE_PROMPT_VERSION,
    NeighborhoodProfileResult,
    NeighborhoodProfileSection,
)
from daedalus.model_clients.types import ModelProvider


# --- write_neighborhood_profile_json ---


def test_write_neighborhood_profile_json_creates_file(tmp_path: Path) -> None:
    output_path = tmp_path / "neighborhood_profile.json"

    write_neighborhood_profile_json(result=_profile_result(), output_path=output_path)

    assert output_path.is_file()


def test_write_neighborhood_profile_json_creates_parent_directory(tmp_path: Path) -> None:
    output_path = tmp_path / "nested" / "artifacts" / "neighborhood_profile.json"

    write_neighborhood_profile_json(result=_profile_result(), output_path=output_path)

    assert output_path.parent.is_dir()


def test_write_neighborhood_profile_json_returns_output_path(tmp_path: Path) -> None:
    output_path = tmp_path / "neighborhood_profile.json"

    returned = write_neighborhood_profile_json(result=_profile_result(), output_path=output_path)

    assert returned == output_path


def test_write_neighborhood_profile_json_is_valid_json(tmp_path: Path) -> None:
    output_path = tmp_path / "neighborhood_profile.json"

    write_neighborhood_profile_json(result=_profile_result(), output_path=output_path)

    data = json.loads(output_path.read_text(encoding="utf-8"))
    assert isinstance(data, dict)


def test_write_neighborhood_profile_json_includes_run_id(tmp_path: Path) -> None:
    result = _profile_result()
    output_path = tmp_path / "neighborhood_profile.json"

    write_neighborhood_profile_json(result=result, output_path=output_path)

    data = json.loads(output_path.read_text(encoding="utf-8"))
    assert data["run_id"] == str(result.run_id)


def test_write_neighborhood_profile_json_includes_provider_as_string(tmp_path: Path) -> None:
    output_path = tmp_path / "neighborhood_profile.json"

    write_neighborhood_profile_json(result=_profile_result(), output_path=output_path)

    data = json.loads(output_path.read_text(encoding="utf-8"))
    assert data["provider"] == "fake"


def test_write_neighborhood_profile_json_includes_model_name(tmp_path: Path) -> None:
    output_path = tmp_path / "neighborhood_profile.json"

    write_neighborhood_profile_json(result=_profile_result(), output_path=output_path)

    data = json.loads(output_path.read_text(encoding="utf-8"))
    assert data["model_name"] == "fake-model"


def test_write_neighborhood_profile_json_includes_prompt_identity(tmp_path: Path) -> None:
    output_path = tmp_path / "neighborhood_profile.json"

    write_neighborhood_profile_json(result=_profile_result(), output_path=output_path)

    data = json.loads(output_path.read_text(encoding="utf-8"))
    assert data["prompt_name"] == DEFAULT_NEIGHBORHOOD_PROFILE_PROMPT_NAME
    assert data["prompt_version"] == DEFAULT_NEIGHBORHOOD_PROFILE_PROMPT_VERSION


def test_write_neighborhood_profile_json_includes_market_and_neighborhood(
    tmp_path: Path,
) -> None:
    output_path = tmp_path / "neighborhood_profile.json"

    write_neighborhood_profile_json(result=_profile_result(), output_path=output_path)

    data = json.loads(output_path.read_text(encoding="utf-8"))
    assert data["market_name"] == "Austin"
    assert data["neighborhood_name"] == "East Side"


def test_write_neighborhood_profile_json_includes_profile_title(tmp_path: Path) -> None:
    output_path = tmp_path / "neighborhood_profile.json"

    write_neighborhood_profile_json(result=_profile_result(), output_path=output_path)

    data = json.loads(output_path.read_text(encoding="utf-8"))
    assert data["profile_title"] == "East Side Austin Neighborhood Profile"


def test_write_neighborhood_profile_json_includes_summary(tmp_path: Path) -> None:
    output_path = tmp_path / "neighborhood_profile.json"

    write_neighborhood_profile_json(result=_profile_result(), output_path=output_path)

    data = json.loads(output_path.read_text(encoding="utf-8"))
    assert data["summary"] == "A vibrant neighborhood with strong guest appeal."


def test_write_neighborhood_profile_json_includes_sections(tmp_path: Path) -> None:
    section = NeighborhoodProfileSection(
        heading="Location",
        body="Walkable access to dining.",
    )
    output_path = tmp_path / "neighborhood_profile.json"

    write_neighborhood_profile_json(
        result=_profile_result(sections=[section]),
        output_path=output_path,
    )

    data = json.loads(output_path.read_text(encoding="utf-8"))
    assert len(data["sections"]) == 1
    assert data["sections"][0]["heading"] == "Location"
    assert data["sections"][0]["body"] == "Walkable access to dining."


def test_write_neighborhood_profile_json_includes_lists(tmp_path: Path) -> None:
    output_path = tmp_path / "neighborhood_profile.json"

    write_neighborhood_profile_json(
        result=_profile_result(
            investment_highlights=["High occupancy rates"],
            guest_experience_notes=["Close to attractions"],
            risks=["Street noise"],
        ),
        output_path=output_path,
    )

    data = json.loads(output_path.read_text(encoding="utf-8"))
    assert data["investment_highlights"] == ["High occupancy rates"]
    assert data["guest_experience_notes"] == ["Close to attractions"]
    assert data["risks"] == ["Street noise"]


def test_write_neighborhood_profile_json_includes_markdown_field(tmp_path: Path) -> None:
    output_path = tmp_path / "neighborhood_profile.json"

    write_neighborhood_profile_json(result=_profile_result(), output_path=output_path)

    data = json.loads(output_path.read_text(encoding="utf-8"))
    assert "East Side Austin" in data["markdown"]


def test_write_neighborhood_profile_json_includes_token_and_cost_when_present(
    tmp_path: Path,
) -> None:
    output_path = tmp_path / "neighborhood_profile.json"

    write_neighborhood_profile_json(
        result=_profile_result(
            input_tokens=200,
            output_tokens=400,
            total_tokens=600,
            estimated_cost_usd=Decimal("0.012"),
        ),
        output_path=output_path,
    )

    data = json.loads(output_path.read_text(encoding="utf-8"))
    assert data["input_tokens"] == 200
    assert data["output_tokens"] == 400
    assert data["total_tokens"] == 600
    assert data["estimated_cost_usd"] == "0.012"


# --- write_neighborhood_profile_markdown ---


def test_write_neighborhood_profile_markdown_creates_file(tmp_path: Path) -> None:
    output_path = tmp_path / "neighborhood_profile.md"

    write_neighborhood_profile_markdown(result=_profile_result(), output_path=output_path)

    assert output_path.is_file()


def test_write_neighborhood_profile_markdown_creates_parent_directory(tmp_path: Path) -> None:
    output_path = tmp_path / "nested" / "artifacts" / "neighborhood_profile.md"

    write_neighborhood_profile_markdown(result=_profile_result(), output_path=output_path)

    assert output_path.parent.is_dir()


def test_write_neighborhood_profile_markdown_returns_output_path(tmp_path: Path) -> None:
    output_path = tmp_path / "neighborhood_profile.md"

    returned = write_neighborhood_profile_markdown(
        result=_profile_result(), output_path=output_path
    )

    assert returned == output_path


def test_write_neighborhood_profile_markdown_includes_run_id(tmp_path: Path) -> None:
    result = _profile_result()
    output_path = tmp_path / "neighborhood_profile.md"

    write_neighborhood_profile_markdown(result=result, output_path=output_path)

    content = output_path.read_text(encoding="utf-8")
    assert str(result.run_id) in content


def test_write_neighborhood_profile_markdown_includes_provider(tmp_path: Path) -> None:
    output_path = tmp_path / "neighborhood_profile.md"

    write_neighborhood_profile_markdown(result=_profile_result(), output_path=output_path)

    content = output_path.read_text(encoding="utf-8")
    assert "fake" in content


def test_write_neighborhood_profile_markdown_includes_model_name(tmp_path: Path) -> None:
    output_path = tmp_path / "neighborhood_profile.md"

    write_neighborhood_profile_markdown(result=_profile_result(), output_path=output_path)

    content = output_path.read_text(encoding="utf-8")
    assert "fake-model" in content


def test_write_neighborhood_profile_markdown_includes_prompt_identity(tmp_path: Path) -> None:
    output_path = tmp_path / "neighborhood_profile.md"

    write_neighborhood_profile_markdown(result=_profile_result(), output_path=output_path)

    content = output_path.read_text(encoding="utf-8")
    assert DEFAULT_NEIGHBORHOOD_PROFILE_PROMPT_NAME in content
    assert DEFAULT_NEIGHBORHOOD_PROFILE_PROMPT_VERSION in content


def test_write_neighborhood_profile_markdown_includes_market_and_neighborhood(
    tmp_path: Path,
) -> None:
    output_path = tmp_path / "neighborhood_profile.md"

    write_neighborhood_profile_markdown(result=_profile_result(), output_path=output_path)

    content = output_path.read_text(encoding="utf-8")
    assert "Austin" in content
    assert "East Side" in content


def test_write_neighborhood_profile_markdown_includes_markdown_body(tmp_path: Path) -> None:
    output_path = tmp_path / "neighborhood_profile.md"

    write_neighborhood_profile_markdown(result=_profile_result(), output_path=output_path)

    content = output_path.read_text(encoding="utf-8")
    assert "# East Side Austin" in content
    assert "A vibrant neighborhood." in content


def test_write_neighborhood_profile_markdown_does_not_print_to_stdout(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    output_path = tmp_path / "neighborhood_profile.md"

    write_neighborhood_profile_markdown(result=_profile_result(), output_path=output_path)

    captured = capsys.readouterr()
    assert captured.out == ""


# --- helpers ---


def _profile_result(
    *,
    sections: list[NeighborhoodProfileSection] | None = None,
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
        provider=ModelProvider.FAKE,
        model_name="fake-model",
        prompt_name=DEFAULT_NEIGHBORHOOD_PROFILE_PROMPT_NAME,
        prompt_version=DEFAULT_NEIGHBORHOOD_PROFILE_PROMPT_VERSION,
        market_name="Austin",
        neighborhood_name="East Side",
        profile_title="East Side Austin Neighborhood Profile",
        summary="A vibrant neighborhood with strong guest appeal.",
        sections=sections or [],
        investment_highlights=investment_highlights or [],
        guest_experience_notes=guest_experience_notes or [],
        risks=risks or [],
        markdown="# East Side Austin\n\nA vibrant neighborhood.",
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        total_tokens=total_tokens,
        estimated_cost_usd=estimated_cost_usd,
    )
