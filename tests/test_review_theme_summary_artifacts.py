from decimal import Decimal
from pathlib import Path
from uuid import uuid4

from daedalus.domains.readysetrentables_reviews.theme_summary_artifacts import (
    write_review_theme_summary_markdown,
)
from daedalus.domains.readysetrentables_reviews.theme_summary_models import (
    DEFAULT_REVIEW_THEME_PROMPT_NAME,
    DEFAULT_REVIEW_THEME_PROMPT_VERSION,
    ReviewThemeSummaryResult,
    ReviewThemeSummaryTheme,
)
from daedalus.model_clients.types import ModelProvider


def test_write_review_theme_summary_markdown_writes_artifact(tmp_path: Path) -> None:
    output_path = tmp_path / "review_theme_summary.md"

    write_review_theme_summary_markdown(result=_summary_result(), output_path=output_path)

    assert output_path.is_file()


def test_write_review_theme_summary_markdown_creates_parent_directory(tmp_path: Path) -> None:
    output_path = tmp_path / "nested" / "artifacts" / "review_theme_summary.md"

    write_review_theme_summary_markdown(result=_summary_result(), output_path=output_path)

    assert output_path.parent.is_dir()


def test_write_review_theme_summary_markdown_returns_output_path(tmp_path: Path) -> None:
    output_path = tmp_path / "review_theme_summary.md"

    returned_path = write_review_theme_summary_markdown(
        result=_summary_result(),
        output_path=output_path,
    )

    assert returned_path == output_path


def test_write_review_theme_summary_markdown_includes_run_id(tmp_path: Path) -> None:
    result = _summary_result()
    output_path = tmp_path / "review_theme_summary.md"

    write_review_theme_summary_markdown(result=result, output_path=output_path)

    markdown = output_path.read_text(encoding="utf-8")
    assert str(result.run_id) in markdown


def test_write_review_theme_summary_markdown_includes_prompt_identity(tmp_path: Path) -> None:
    output_path = tmp_path / "review_theme_summary.md"

    write_review_theme_summary_markdown(result=_summary_result(), output_path=output_path)

    markdown = output_path.read_text(encoding="utf-8")
    assert f"Prompt: `{DEFAULT_REVIEW_THEME_PROMPT_NAME}`" in markdown
    assert f"Prompt version: `{DEFAULT_REVIEW_THEME_PROMPT_VERSION}`" in markdown


def test_write_review_theme_summary_markdown_includes_model_identity(tmp_path: Path) -> None:
    output_path = tmp_path / "review_theme_summary.md"

    write_review_theme_summary_markdown(result=_summary_result(), output_path=output_path)

    markdown = output_path.read_text(encoding="utf-8")
    assert "Model provider: `fake`" in markdown
    assert "Model name: `fake-model`" in markdown


def test_write_review_theme_summary_markdown_includes_summary_text(tmp_path: Path) -> None:
    output_path = tmp_path / "review_theme_summary.md"

    write_review_theme_summary_markdown(result=_summary_result(), output_path=output_path)

    markdown = output_path.read_text(encoding="utf-8")
    assert "Guests often praise the location and arrival instructions." in markdown


def test_write_review_theme_summary_markdown_includes_token_and_cost_fields(
    tmp_path: Path,
) -> None:
    output_path = tmp_path / "review_theme_summary.md"

    write_review_theme_summary_markdown(result=_summary_result(), output_path=output_path)

    markdown = output_path.read_text(encoding="utf-8")
    assert "Input tokens: 10" in markdown
    assert "Output tokens: 20" in markdown
    assert "Total tokens: 30" in markdown
    assert "Estimated cost USD: 0.001" in markdown


def test_write_review_theme_summary_markdown_includes_empty_themes_message(
    tmp_path: Path,
) -> None:
    output_path = tmp_path / "review_theme_summary.md"

    write_review_theme_summary_markdown(result=_summary_result(themes=[]), output_path=output_path)

    markdown = output_path.read_text(encoding="utf-8")
    assert "No structured themes were returned." in markdown


def test_write_review_theme_summary_markdown_includes_theme_details(tmp_path: Path) -> None:
    output_path = tmp_path / "review_theme_summary.md"
    theme = ReviewThemeSummaryTheme(
        name="Arrival experience",
        sentiment="positive",
        description="Guests mention clear check-in details.",
        supporting_review_count=3,
    )

    write_review_theme_summary_markdown(
        result=_summary_result(themes=[theme]),
        output_path=output_path,
    )

    markdown = output_path.read_text(encoding="utf-8")
    assert "### Arrival experience" in markdown
    assert "Sentiment: positive" in markdown
    assert "Supporting review count: 3" in markdown
    assert "Guests mention clear check-in details." in markdown


def _summary_result(
    *,
    themes: list[ReviewThemeSummaryTheme] | None = None,
) -> ReviewThemeSummaryResult:
    return ReviewThemeSummaryResult(
        run_id=uuid4(),
        summary_text="Guests often praise the location and arrival instructions.",
        themes=themes or [],
        prompt_name=DEFAULT_REVIEW_THEME_PROMPT_NAME,
        prompt_version=DEFAULT_REVIEW_THEME_PROMPT_VERSION,
        model_provider=ModelProvider.FAKE,
        model_name="fake-model",
        input_tokens=10,
        output_tokens=20,
        total_tokens=30,
        estimated_cost_usd=Decimal("0.001"),
    )
