"""Artifact writers for ReadySetRentables review theme summary outputs."""

from pathlib import Path

from daedalus.domains.readysetrentables_reviews.theme_summary_models import (
    ReviewThemeSummaryResult,
)


def write_review_theme_summary_markdown(
    *,
    result: ReviewThemeSummaryResult,
    output_path: Path,
) -> Path:
    """Write an inspectable markdown artifact for a review theme summary result."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(_review_theme_summary_markdown(result), encoding="utf-8")
    return output_path


def _review_theme_summary_markdown(result: ReviewThemeSummaryResult) -> str:
    lines = [
        "# ReadySetRentables Review Theme Summary",
        "",
        f"- Run ID: `{result.run_id}`",
        f"- Prompt: `{result.prompt_name}`",
        f"- Prompt version: `{result.prompt_version}`",
        f"- Model provider: `{result.model_provider.value}`",
        f"- Model name: `{result.model_name}`",
        "",
        "## Summary",
        "",
        result.summary_text,
        "",
    ]
    token_lines = _token_cost_lines(result)
    if token_lines:
        lines.extend(["## Token And Cost Metadata", ""])
        lines.extend(token_lines)
        lines.append("")

    lines.extend(["## Themes", ""])
    if not result.themes:
        lines.append("No structured themes were returned.")
    else:
        for theme in result.themes:
            lines.append(f"### {theme.name}")
            lines.append("")
            lines.append(f"- Sentiment: {theme.sentiment}")
            if theme.supporting_review_count is not None:
                lines.append(f"- Supporting review count: {theme.supporting_review_count}")
            lines.extend(["", theme.description, ""])

    return "\n".join(lines).rstrip() + "\n"


def _token_cost_lines(result: ReviewThemeSummaryResult) -> list[str]:
    lines: list[str] = []
    if result.input_tokens is not None:
        lines.append(f"- Input tokens: {result.input_tokens}")
    if result.output_tokens is not None:
        lines.append(f"- Output tokens: {result.output_tokens}")
    if result.total_tokens is not None:
        lines.append(f"- Total tokens: {result.total_tokens}")
    if result.estimated_cost_usd is not None:
        lines.append(f"- Estimated cost USD: {result.estimated_cost_usd}")

    return lines
