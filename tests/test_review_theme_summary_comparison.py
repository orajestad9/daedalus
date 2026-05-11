import json
from pathlib import Path
from typing import Any, cast
from uuid import UUID, uuid4

import pytest

from daedalus.domains.readysetrentables_reviews.theme_summary_comparison import (
    COMPARATOR_NAME,
    COMPARATOR_VERSION,
    TARGET_NAME,
    TARGET_TYPE,
    compare_review_theme_summary_markdown,
)
from daedalus.evaluation import (
    EvaluationComparisonItem,
    EvaluationComparisonStatus,
)
from daedalus.model_clients import FakeModelClient, OllamaModelClient


# ---------------------------------------------------------------------------
# Report identity
# ---------------------------------------------------------------------------


def test_valid_comparison_produces_evaluation_comparison_report(tmp_path: Path) -> None:
    baseline, candidate = _write_both(tmp_path)

    report = compare_review_theme_summary_markdown(
        baseline_path=baseline,
        candidate_path=candidate,
    )

    assert report.comparisons


def test_report_target_name_is_review_theme_summary(tmp_path: Path) -> None:
    baseline, candidate = _write_both(tmp_path)

    report = compare_review_theme_summary_markdown(
        baseline_path=baseline,
        candidate_path=candidate,
    )

    assert report.target_name == TARGET_NAME


def test_report_target_type_is_review_theme_summary(tmp_path: Path) -> None:
    baseline, candidate = _write_both(tmp_path)

    report = compare_review_theme_summary_markdown(
        baseline_path=baseline,
        candidate_path=candidate,
    )

    assert report.target_type == TARGET_TYPE


def test_report_comparator_identity_is_set(tmp_path: Path) -> None:
    baseline, candidate = _write_both(tmp_path)

    report = compare_review_theme_summary_markdown(
        baseline_path=baseline,
        candidate_path=candidate,
    )

    assert report.comparator_name == COMPARATOR_NAME
    assert report.comparator_version == COMPARATOR_VERSION


def test_report_baseline_report_id_is_preserved(tmp_path: Path) -> None:
    baseline, candidate = _write_both(tmp_path)
    baseline_report_id = uuid4()

    report = compare_review_theme_summary_markdown(
        baseline_path=baseline,
        candidate_path=candidate,
        baseline_report_id=baseline_report_id,
    )

    assert report.baseline_report_id == baseline_report_id


def test_report_candidate_report_id_is_preserved(tmp_path: Path) -> None:
    baseline, candidate = _write_both(tmp_path)
    candidate_report_id = uuid4()

    report = compare_review_theme_summary_markdown(
        baseline_path=baseline,
        candidate_path=candidate,
        candidate_report_id=candidate_report_id,
    )

    assert report.candidate_report_id == candidate_report_id


def test_report_artifact_paths_are_preserved(tmp_path: Path) -> None:
    baseline, candidate = _write_both(tmp_path)

    report = compare_review_theme_summary_markdown(
        baseline_path=baseline,
        candidate_path=candidate,
    )

    assert report.baseline_artifact_path == baseline
    assert report.candidate_artifact_path == candidate


# ---------------------------------------------------------------------------
# Missing artifacts
# ---------------------------------------------------------------------------


def test_missing_baseline_produces_non_match_comparison(tmp_path: Path) -> None:
    baseline = tmp_path / "baseline" / "review_theme_summary.md"
    candidate = _write_summary(tmp_path / "candidate" / "review_theme_summary.md")

    report = compare_review_theme_summary_markdown(
        baseline_path=baseline,
        candidate_path=candidate,
    )

    item = _comparison_by_name(report.comparisons, "baseline_artifact_exists")
    assert item.status != EvaluationComparisonStatus.MATCH


def test_missing_candidate_produces_non_match_comparison(tmp_path: Path) -> None:
    baseline = _write_summary(tmp_path / "baseline" / "review_theme_summary.md")
    candidate = tmp_path / "candidate" / "review_theme_summary.md"

    report = compare_review_theme_summary_markdown(
        baseline_path=baseline,
        candidate_path=candidate,
    )

    item = _comparison_by_name(report.comparisons, "candidate_artifact_exists")
    assert item.status != EvaluationComparisonStatus.MATCH


# ---------------------------------------------------------------------------
# Empty artifact
# ---------------------------------------------------------------------------


def test_empty_candidate_with_non_empty_baseline_is_recorded(tmp_path: Path) -> None:
    baseline = _write_summary(tmp_path / "baseline.md")
    candidate = tmp_path / "candidate.md"
    candidate.write_text("", encoding="utf-8")

    report = compare_review_theme_summary_markdown(
        baseline_path=baseline,
        candidate_path=candidate,
    )

    item = _comparison_by_name(report.comparisons, "both_artifacts_non_empty")
    assert item.status == EvaluationComparisonStatus.REGRESSED


# ---------------------------------------------------------------------------
# Title presence
# ---------------------------------------------------------------------------


def test_matching_title_presence_produces_match(tmp_path: Path) -> None:
    baseline, candidate = _write_both(tmp_path)

    report = compare_review_theme_summary_markdown(
        baseline_path=baseline,
        candidate_path=candidate,
    )

    item = _comparison_by_name(report.comparisons, "title_presence_matches")
    assert item.status == EvaluationComparisonStatus.MATCH


def test_missing_candidate_title_produces_regressed(tmp_path: Path) -> None:
    baseline = _write_summary(tmp_path / "baseline.md")
    candidate = _write_summary(
        tmp_path / "candidate.md",
        summary_text="A substantive summary.",
        include_title=False,
    )

    report = compare_review_theme_summary_markdown(
        baseline_path=baseline,
        candidate_path=candidate,
    )

    item = _comparison_by_name(report.comparisons, "title_presence_matches")
    assert item.status in {
        EvaluationComparisonStatus.REGRESSED,
        EvaluationComparisonStatus.DIFFERENT,
    }


# ---------------------------------------------------------------------------
# Summary section presence
# ---------------------------------------------------------------------------


def test_matching_summary_section_presence_produces_match(tmp_path: Path) -> None:
    baseline, candidate = _write_both(tmp_path)

    report = compare_review_theme_summary_markdown(
        baseline_path=baseline,
        candidate_path=candidate,
    )

    item = _comparison_by_name(report.comparisons, "summary_section_presence_matches")
    assert item.status == EvaluationComparisonStatus.MATCH


def test_candidate_missing_summary_section_produces_regressed(tmp_path: Path) -> None:
    baseline = _write_summary(tmp_path / "baseline.md")
    candidate = _write_summary(
        tmp_path / "candidate.md",
        include_summary_section=False,
    )

    report = compare_review_theme_summary_markdown(
        baseline_path=baseline,
        candidate_path=candidate,
    )

    item = _comparison_by_name(report.comparisons, "summary_section_presence_matches")
    assert item.status in {
        EvaluationComparisonStatus.REGRESSED,
        EvaluationComparisonStatus.DIFFERENT,
    }


# ---------------------------------------------------------------------------
# Metadata presence
# ---------------------------------------------------------------------------


def test_prompt_metadata_presence_comparison_match(tmp_path: Path) -> None:
    baseline, candidate = _write_both(tmp_path)

    report = compare_review_theme_summary_markdown(
        baseline_path=baseline,
        candidate_path=candidate,
    )

    item = _comparison_by_name(report.comparisons, "prompt_metadata_presence_matches")
    assert item.status == EvaluationComparisonStatus.MATCH


def test_prompt_metadata_missing_from_candidate_produces_regressed(tmp_path: Path) -> None:
    baseline = _write_summary(tmp_path / "baseline.md")
    candidate = _write_summary(
        tmp_path / "candidate.md",
        include_prompt_metadata=False,
    )

    report = compare_review_theme_summary_markdown(
        baseline_path=baseline,
        candidate_path=candidate,
    )

    item = _comparison_by_name(report.comparisons, "prompt_metadata_presence_matches")
    assert item.status in {
        EvaluationComparisonStatus.REGRESSED,
        EvaluationComparisonStatus.DIFFERENT,
    }


def test_model_metadata_presence_comparison_match(tmp_path: Path) -> None:
    baseline, candidate = _write_both(tmp_path)

    report = compare_review_theme_summary_markdown(
        baseline_path=baseline,
        candidate_path=candidate,
    )

    item = _comparison_by_name(report.comparisons, "model_metadata_presence_matches")
    assert item.status == EvaluationComparisonStatus.MATCH


def test_model_metadata_missing_from_candidate_produces_regressed(tmp_path: Path) -> None:
    baseline = _write_summary(tmp_path / "baseline.md")
    candidate = _write_summary(
        tmp_path / "candidate.md",
        include_model_metadata=False,
    )

    report = compare_review_theme_summary_markdown(
        baseline_path=baseline,
        candidate_path=candidate,
    )

    item = _comparison_by_name(report.comparisons, "model_metadata_presence_matches")
    assert item.status in {
        EvaluationComparisonStatus.REGRESSED,
        EvaluationComparisonStatus.DIFFERENT,
    }


def test_usage_section_presence_comparison_match(tmp_path: Path) -> None:
    baseline, candidate = _write_both(tmp_path)

    report = compare_review_theme_summary_markdown(
        baseline_path=baseline,
        candidate_path=candidate,
    )

    item = _comparison_by_name(report.comparisons, "usage_section_presence_matches")
    assert item.status == EvaluationComparisonStatus.MATCH


def test_usage_section_missing_from_candidate_produces_regressed(tmp_path: Path) -> None:
    baseline = _write_summary(tmp_path / "baseline.md")
    candidate = _write_summary(
        tmp_path / "candidate.md",
        include_usage_section=False,
    )

    report = compare_review_theme_summary_markdown(
        baseline_path=baseline,
        candidate_path=candidate,
    )

    item = _comparison_by_name(report.comparisons, "usage_section_presence_matches")
    assert item.status in {
        EvaluationComparisonStatus.REGRESSED,
        EvaluationComparisonStatus.DIFFERENT,
    }


# ---------------------------------------------------------------------------
# Summary length delta
# ---------------------------------------------------------------------------


def test_shorter_candidate_summary_below_threshold_produces_regressed(
    tmp_path: Path,
) -> None:
    long_text = "A " * 100
    short_text = "OK."
    baseline = _write_summary(tmp_path / "baseline.md", summary_text=long_text)
    candidate = _write_summary(tmp_path / "candidate.md", summary_text=short_text)

    report = compare_review_theme_summary_markdown(
        baseline_path=baseline,
        candidate_path=candidate,
    )

    item = _comparison_by_name(report.comparisons, "summary_length_delta")
    assert item.status == EvaluationComparisonStatus.REGRESSED


def test_longer_candidate_summary_produces_improved_or_match(tmp_path: Path) -> None:
    short_text = "OK."
    long_text = "Guests praise the clear check-in details and the convenient location near transit."
    baseline = _write_summary(tmp_path / "baseline.md", summary_text=short_text)
    candidate = _write_summary(tmp_path / "candidate.md", summary_text=long_text)

    report = compare_review_theme_summary_markdown(
        baseline_path=baseline,
        candidate_path=candidate,
    )

    item = _comparison_by_name(report.comparisons, "summary_length_delta")
    assert item.status in {
        EvaluationComparisonStatus.IMPROVED,
        EvaluationComparisonStatus.MATCH,
    }


# ---------------------------------------------------------------------------
# Placeholder regression
# ---------------------------------------------------------------------------


def test_placeholder_candidate_produces_regressed_when_baseline_is_not(
    tmp_path: Path,
) -> None:
    baseline = _write_summary(
        tmp_path / "baseline.md",
        summary_text="Guests praised the helpful host and convenient location.",
    )
    candidate = _write_summary(
        tmp_path / "candidate.md",
        summary_text="fake model response",
    )

    report = compare_review_theme_summary_markdown(
        baseline_path=baseline,
        candidate_path=candidate,
    )

    item = _comparison_by_name(report.comparisons, "placeholder_regression")
    assert item.status == EvaluationComparisonStatus.REGRESSED


def test_non_placeholder_candidate_produces_match_for_placeholder_regression(
    tmp_path: Path,
) -> None:
    baseline, candidate = _write_both(tmp_path)

    report = compare_review_theme_summary_markdown(
        baseline_path=baseline,
        candidate_path=candidate,
    )

    item = _comparison_by_name(report.comparisons, "placeholder_regression")
    assert item.status == EvaluationComparisonStatus.MATCH


# ---------------------------------------------------------------------------
# No model providers called
# ---------------------------------------------------------------------------


def test_comparator_does_not_require_live_ollama(tmp_path: Path) -> None:
    baseline, candidate = _write_both(tmp_path)

    report = compare_review_theme_summary_markdown(
        baseline_path=baseline,
        candidate_path=candidate,
    )

    assert report.comparisons


def test_comparator_does_not_call_any_model_provider(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    baseline, candidate = _write_both(tmp_path)

    def fail_if_called(*_args: Any, **_kwargs: Any) -> None:
        raise AssertionError("model provider should not be called")

    monkeypatch.setattr(FakeModelClient, "complete", fail_if_called)
    monkeypatch.setattr(OllamaModelClient, "complete", fail_if_called)

    report = compare_review_theme_summary_markdown(
        baseline_path=baseline,
        candidate_path=candidate,
    )

    assert report.comparisons


# ---------------------------------------------------------------------------
# JSON serialization
# ---------------------------------------------------------------------------


def test_report_json_serialization_uses_enum_string_values(tmp_path: Path) -> None:
    baseline, candidate = _write_both(tmp_path)

    report = compare_review_theme_summary_markdown(
        baseline_path=baseline,
        candidate_path=candidate,
    )

    data = cast(dict[str, Any], json.loads(report.model_dump_json()))
    first = data["comparisons"][0]
    assert isinstance(first["status"], str)
    assert isinstance(first["severity"], str)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _write_both(tmp_path: Path) -> tuple[Path, Path]:
    baseline = _write_summary(tmp_path / "baseline" / "review_theme_summary.md")
    candidate = _write_summary(tmp_path / "candidate" / "review_theme_summary.md")
    return baseline, candidate


def _write_summary(
    path: Path,
    *,
    run_id: UUID | None = None,
    summary_text: str = "Guests praised the helpful host and the convenient location.",
    include_title: bool = True,
    include_prompt_metadata: bool = True,
    include_model_metadata: bool = True,
    include_summary_section: bool = True,
    include_usage_section: bool = True,
) -> Path:
    run_id = run_id or uuid4()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        _summary_markdown(
            run_id=run_id,
            summary_text=summary_text,
            include_title=include_title,
            include_prompt_metadata=include_prompt_metadata,
            include_model_metadata=include_model_metadata,
            include_summary_section=include_summary_section,
            include_usage_section=include_usage_section,
        ),
        encoding="utf-8",
    )
    return path


def _summary_markdown(
    *,
    run_id: UUID,
    summary_text: str,
    include_title: bool = True,
    include_prompt_metadata: bool = True,
    include_model_metadata: bool = True,
    include_summary_section: bool = True,
    include_usage_section: bool = True,
) -> str:
    lines: list[str] = []
    if include_title:
        lines += ["# ReadySetRentables Review Theme Summary", ""]
    lines.append(f"- Run ID: `{run_id}`")
    if include_prompt_metadata:
        lines += ["- Prompt: `summarize_reviews`", "- Prompt version: `v0`"]
    if include_model_metadata:
        lines += ["- Model provider: `fake`", "- Model name: `fake-model`"]
    lines.append("")
    if include_summary_section:
        lines += ["## Summary", "", summary_text, ""]
    if include_usage_section:
        lines += [
            "## Token And Cost Metadata",
            "",
            "- Input tokens: 10",
            "- Output tokens: 20",
            "- Total tokens: 30",
            "- Estimated cost USD: 0",
            "",
        ]
    return "\n".join(lines)


def _comparison_by_name(
    comparisons: list[EvaluationComparisonItem],
    comparison_name: str,
) -> EvaluationComparisonItem:
    return next(c for c in comparisons if c.comparison_name == comparison_name)
