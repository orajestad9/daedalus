"""Deterministic comparison evaluator for ReadySetRentables review theme summaries."""

import re
from pathlib import Path
from uuid import UUID

from daedalus.evaluation import (
    EvaluationComparisonItem,
    EvaluationComparisonReport,
    EvaluationComparisonStatus,
    EvaluationSeverity,
)

COMPARATOR_NAME = "readysetrentables_review_theme_summary_basic_comparison"
COMPARATOR_VERSION = "v0"
TARGET_NAME = "review_theme_summary"
TARGET_TYPE = "review_theme_summary"

_TITLE = "# ReadySetRentables Review Theme Summary"
_SUMMARY_HEADING_PATTERN = re.compile(r"^## Summary\s*$", re.MULTILINE)
_NEXT_HEADING_PATTERN = re.compile(r"^##\s+", re.MULTILINE)
_PLACEHOLDER_SUMMARIES = {
    "fake model response",
    "placeholder",
    "tbd",
    "todo",
}
_REGRESSION_THRESHOLD = 0.5


def compare_review_theme_summary_markdown(
    *,
    baseline_path: Path,
    candidate_path: Path,
    baseline_report_id: UUID | None = None,
    candidate_report_id: UUID | None = None,
) -> EvaluationComparisonReport:
    """Compare two review_theme_summary.md artifacts deterministically."""
    baseline_exists = baseline_path.exists()
    candidate_exists = candidate_path.exists()
    baseline_text = baseline_path.read_text(encoding="utf-8") if baseline_exists else None
    candidate_text = candidate_path.read_text(encoding="utf-8") if candidate_exists else None
    either_missing = not baseline_exists or not candidate_exists

    comparisons = [
        _baseline_exists_comparison(baseline_path, baseline_exists),
        _candidate_exists_comparison(candidate_path, candidate_exists),
        _both_non_empty_comparison(baseline_text, candidate_text, either_missing),
        _presence_comparison(
            "title_presence_matches",
            baseline_present=_has_title(baseline_text),
            candidate_present=_has_title(candidate_text),
            either_missing=either_missing,
            present_label="title",
        ),
        _presence_comparison(
            "summary_section_presence_matches",
            baseline_present=_has_summary_section(baseline_text),
            candidate_present=_has_summary_section(candidate_text),
            either_missing=either_missing,
            present_label="summary section",
            regressed_severity=EvaluationSeverity.ERROR,
        ),
        _presence_comparison(
            "prompt_metadata_presence_matches",
            baseline_present=_has_prompt_metadata(baseline_text),
            candidate_present=_has_prompt_metadata(candidate_text),
            either_missing=either_missing,
            present_label="prompt metadata",
        ),
        _presence_comparison(
            "model_metadata_presence_matches",
            baseline_present=_has_model_metadata(baseline_text),
            candidate_present=_has_model_metadata(candidate_text),
            either_missing=either_missing,
            present_label="model metadata",
        ),
        _presence_comparison(
            "usage_section_presence_matches",
            baseline_present=_has_usage_section(baseline_text),
            candidate_present=_has_usage_section(candidate_text),
            either_missing=either_missing,
            present_label="usage section",
        ),
        _summary_length_delta_comparison(baseline_text, candidate_text, either_missing),
        _placeholder_regression_comparison(baseline_text, candidate_text, either_missing),
    ]

    return EvaluationComparisonReport(
        baseline_report_id=baseline_report_id,
        candidate_report_id=candidate_report_id,
        baseline_artifact_path=baseline_path,
        candidate_artifact_path=candidate_path,
        target_name=TARGET_NAME,
        target_type=TARGET_TYPE,
        comparator_name=COMPARATOR_NAME,
        comparator_version=COMPARATOR_VERSION,
        comparisons=comparisons,
    )


def _baseline_exists_comparison(
    baseline_path: Path,
    exists: bool,
) -> EvaluationComparisonItem:
    if exists:
        return _match("baseline_artifact_exists", "Baseline artifact exists.")
    return _item(
        "baseline_artifact_exists",
        status=EvaluationComparisonStatus.DIFFERENT,
        severity=EvaluationSeverity.ERROR,
        message="Baseline artifact is missing.",
        details={"path": str(baseline_path)},
    )


def _candidate_exists_comparison(
    candidate_path: Path,
    exists: bool,
) -> EvaluationComparisonItem:
    if exists:
        return _match("candidate_artifact_exists", "Candidate artifact exists.")
    return _item(
        "candidate_artifact_exists",
        status=EvaluationComparisonStatus.DIFFERENT,
        severity=EvaluationSeverity.ERROR,
        message="Candidate artifact is missing.",
        details={"path": str(candidate_path)},
    )


def _both_non_empty_comparison(
    baseline_text: str | None,
    candidate_text: str | None,
    either_missing: bool,
) -> EvaluationComparisonItem:
    if either_missing:
        return _inconclusive(
            "both_artifacts_non_empty",
            "Cannot compare content: one or both artifacts are missing.",
        )

    assert baseline_text is not None
    assert candidate_text is not None

    baseline_empty = not baseline_text.strip()
    candidate_empty = not candidate_text.strip()

    if baseline_empty == candidate_empty:
        if not baseline_empty:
            return _match("both_artifacts_non_empty", "Both artifacts are non-empty.")
        return _match("both_artifacts_non_empty", "Both artifacts are empty.")

    if not baseline_empty and candidate_empty:
        return _item(
            "both_artifacts_non_empty",
            status=EvaluationComparisonStatus.REGRESSED,
            severity=EvaluationSeverity.ERROR,
            message="Candidate is empty; baseline was non-empty.",
        )

    return _item(
        "both_artifacts_non_empty",
        status=EvaluationComparisonStatus.IMPROVED,
        severity=EvaluationSeverity.INFO,
        message="Candidate is non-empty; baseline was empty.",
    )


def _presence_comparison(
    comparison_name: str,
    *,
    baseline_present: bool,
    candidate_present: bool,
    either_missing: bool,
    present_label: str,
    regressed_severity: EvaluationSeverity = EvaluationSeverity.WARNING,
) -> EvaluationComparisonItem:
    if either_missing:
        return _inconclusive(
            comparison_name,
            f"Cannot compare {present_label} presence: one or both artifacts are missing.",
        )

    baseline_val = "present" if baseline_present else "absent"
    candidate_val = "present" if candidate_present else "absent"

    if baseline_present == candidate_present:
        suffix = "in both" if baseline_present else "from both"
        return _item(
            comparison_name,
            status=EvaluationComparisonStatus.MATCH,
            severity=EvaluationSeverity.INFO,
            message=f"{present_label.capitalize()} is {baseline_val} {suffix}.",
            baseline_value=baseline_val,
            candidate_value=candidate_val,
        )

    if baseline_present and not candidate_present:
        return _item(
            comparison_name,
            status=EvaluationComparisonStatus.REGRESSED,
            severity=regressed_severity,
            message=f"{present_label.capitalize()} is present in baseline but missing from candidate.",
            baseline_value=baseline_val,
            candidate_value=candidate_val,
        )

    return _item(
        comparison_name,
        status=EvaluationComparisonStatus.IMPROVED,
        severity=EvaluationSeverity.INFO,
        message=f"{present_label.capitalize()} is present in candidate but was absent from baseline.",
        baseline_value=baseline_val,
        candidate_value=candidate_val,
    )


def _summary_length_delta_comparison(
    baseline_text: str | None,
    candidate_text: str | None,
    either_missing: bool,
) -> EvaluationComparisonItem:
    if either_missing:
        return _inconclusive(
            "summary_length_delta",
            "Cannot compare summary lengths: one or both artifacts are missing.",
        )

    assert baseline_text is not None
    assert candidate_text is not None

    baseline_summary = _summary_section(baseline_text)
    candidate_summary = _summary_section(candidate_text)

    if baseline_summary is None or candidate_summary is None:
        return _inconclusive(
            "summary_length_delta",
            "Cannot compare summary section lengths: one or both summary sections are missing.",
        )

    baseline_len = len(baseline_summary)
    candidate_len = len(candidate_summary)
    details = {
        "baseline_summary_length": str(baseline_len),
        "candidate_summary_length": str(candidate_len),
    }

    if baseline_len > 0 and candidate_len < baseline_len * _REGRESSION_THRESHOLD:
        return _item(
            "summary_length_delta",
            status=EvaluationComparisonStatus.REGRESSED,
            severity=EvaluationSeverity.WARNING,
            message="Candidate summary section is significantly shorter than baseline.",
            baseline_value=str(baseline_len),
            candidate_value=str(candidate_len),
            details=details,
        )

    if candidate_len > baseline_len:
        return _item(
            "summary_length_delta",
            status=EvaluationComparisonStatus.IMPROVED,
            severity=EvaluationSeverity.INFO,
            message="Candidate summary section is longer than baseline.",
            baseline_value=str(baseline_len),
            candidate_value=str(candidate_len),
            details=details,
        )

    return _item(
        "summary_length_delta",
        status=EvaluationComparisonStatus.MATCH,
        severity=EvaluationSeverity.INFO,
        message="Candidate summary section length is similar to baseline.",
        baseline_value=str(baseline_len),
        candidate_value=str(candidate_len),
        details=details,
    )


def _placeholder_regression_comparison(
    baseline_text: str | None,
    candidate_text: str | None,
    either_missing: bool,
) -> EvaluationComparisonItem:
    if either_missing:
        return _inconclusive(
            "placeholder_regression",
            "Cannot compare placeholder status: one or both artifacts are missing.",
        )

    assert baseline_text is not None
    assert candidate_text is not None

    baseline_summary = _summary_section(baseline_text)
    candidate_summary = _summary_section(candidate_text)

    if baseline_summary is None or candidate_summary is None:
        return _inconclusive(
            "placeholder_regression",
            "Cannot compare placeholder status: one or both summary sections are missing.",
        )

    baseline_placeholder = _is_placeholder_text(baseline_summary)
    candidate_placeholder = _is_placeholder_text(candidate_summary)

    if candidate_placeholder and not baseline_placeholder:
        return _item(
            "placeholder_regression",
            status=EvaluationComparisonStatus.REGRESSED,
            severity=EvaluationSeverity.ERROR,
            message="Candidate summary appears placeholder-only; baseline was not.",
        )

    return _match(
        "placeholder_regression",
        "Candidate summary does not appear placeholder-only relative to baseline.",
    )


def _summary_section(text: str) -> str | None:
    match = _SUMMARY_HEADING_PATTERN.search(text)
    if match is None:
        return None
    summary_start = match.end()
    next_heading_match = _NEXT_HEADING_PATTERN.search(text, summary_start)
    summary_end = next_heading_match.start() if next_heading_match else len(text)
    return text[summary_start:summary_end].strip()


def _has_title(text: str | None) -> bool:
    return text is not None and _TITLE in text


def _has_summary_section(text: str | None) -> bool:
    return text is not None and _summary_section(text) is not None


def _has_prompt_metadata(text: str | None) -> bool:
    return text is not None and "Prompt:" in text and "Prompt version:" in text


def _has_model_metadata(text: str | None) -> bool:
    return text is not None and "Model provider:" in text and "Model name:" in text


def _has_usage_section(text: str | None) -> bool:
    return text is not None and "## Token And Cost Metadata" in text


def _is_placeholder_text(text: str) -> bool:
    normalized_text = " ".join(text.strip().lower().split())
    return normalized_text in _PLACEHOLDER_SUMMARIES


def _item(
    comparison_name: str,
    *,
    status: EvaluationComparisonStatus,
    severity: EvaluationSeverity,
    message: str,
    baseline_value: str | None = None,
    candidate_value: str | None = None,
    details: dict[str, str] | None = None,
) -> EvaluationComparisonItem:
    return EvaluationComparisonItem(
        comparison_name=comparison_name,
        status=status,
        severity=severity,
        message=message,
        baseline_value=baseline_value,
        candidate_value=candidate_value,
        details=details or {},
    )


def _match(
    comparison_name: str,
    message: str,
    *,
    baseline_value: str | None = None,
    candidate_value: str | None = None,
) -> EvaluationComparisonItem:
    return _item(
        comparison_name,
        status=EvaluationComparisonStatus.MATCH,
        severity=EvaluationSeverity.INFO,
        message=message,
        baseline_value=baseline_value,
        candidate_value=candidate_value,
    )


def _inconclusive(comparison_name: str, message: str) -> EvaluationComparisonItem:
    return _item(
        comparison_name,
        status=EvaluationComparisonStatus.INCONCLUSIVE,
        severity=EvaluationSeverity.INFO,
        message=message,
    )
