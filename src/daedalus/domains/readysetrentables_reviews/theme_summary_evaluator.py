"""Deterministic evaluator for ReadySetRentables review theme summaries."""

from pathlib import Path
import re
from typing import TypeGuard
from uuid import UUID

from daedalus.evaluation import (
    EvaluationCheckResult,
    EvaluationReport,
    EvaluationSeverity,
    EvaluationStatus,
)

EVALUATOR_NAME = "readysetrentables_review_theme_summary_basic"
EVALUATOR_VERSION = "v0"
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


def evaluate_review_theme_summary_markdown(
    *,
    summary_path: Path,
    run_id: UUID | None = None,
) -> EvaluationReport:
    """Evaluate a review theme summary markdown artifact with local checks."""
    exists = summary_path.exists()
    text = summary_path.read_text(encoding="utf-8") if exists else None

    checks = [
        _artifact_exists_check(summary_path=summary_path, exists=exists),
        _artifact_non_empty_check(text=text),
        _contains_title_check(text=text),
        _contains_run_id_check(text=text, run_id=run_id),
        _contains_prompt_metadata_check(text=text),
        _contains_model_metadata_check(text=text),
        _contains_summary_section_check(text=text),
        _summary_section_non_empty_check(text=text),
        _contains_usage_section_check(text=text),
        _placeholder_only_output_check(text=text),
    ]

    return EvaluationReport(
        run_id=run_id,
        artifact_path=summary_path,
        target_name=summary_path.name,
        target_type=TARGET_TYPE,
        evaluator_name=EVALUATOR_NAME,
        evaluator_version=EVALUATOR_VERSION,
        checks=checks,
    )


def _artifact_exists_check(
    *,
    summary_path: Path,
    exists: bool,
) -> EvaluationCheckResult:
    if exists:
        return _passed("artifact_exists", "Review theme summary artifact exists.")

    return _failed_error(
        "artifact_exists",
        "Review theme summary artifact was not found.",
        details={"path": str(summary_path)},
    )


def _artifact_non_empty_check(text: str | None) -> EvaluationCheckResult:
    if text is None:
        return _skipped("artifact_non_empty", "Artifact content was not available.")
    if text.strip():
        return _passed("artifact_non_empty", "Review theme summary artifact is non-empty.")

    return _failed_error("artifact_non_empty", "Review theme summary artifact is empty.")


def _contains_title_check(text: str | None) -> EvaluationCheckResult:
    if not _has_inspectable_text(text):
        return _skipped("contains_title", "Artifact content was not available.")
    if _TITLE in text:
        return _passed("contains_title", "Review theme summary title is present.")

    return _failed_warning(
        "contains_title",
        "Review theme summary title is missing.",
        details={"expected_title": _TITLE},
    )


def _contains_run_id_check(
    *,
    text: str | None,
    run_id: UUID | None,
) -> EvaluationCheckResult:
    if run_id is None:
        return _skipped("contains_run_id", "No run_id was provided for evaluation.")
    if not _has_inspectable_text(text):
        return _skipped("contains_run_id", "Artifact content was not available.")
    if str(run_id) in text:
        return _passed("contains_run_id", "Expected run_id is present.")

    return _failed_warning("contains_run_id", "Expected run_id is missing.")


def _contains_prompt_metadata_check(text: str | None) -> EvaluationCheckResult:
    if not _has_inspectable_text(text):
        return _skipped("contains_prompt_metadata", "Artifact content was not available.")
    if "Prompt:" in text and "Prompt version:" in text:
        return _passed("contains_prompt_metadata", "Prompt metadata is present.")

    return _failed_warning(
        "contains_prompt_metadata",
        "Prompt name or prompt version metadata is missing.",
    )


def _contains_model_metadata_check(text: str | None) -> EvaluationCheckResult:
    if not _has_inspectable_text(text):
        return _skipped("contains_model_metadata", "Artifact content was not available.")
    if "Model provider:" in text and "Model name:" in text:
        return _passed("contains_model_metadata", "Model metadata is present.")

    return _failed_warning(
        "contains_model_metadata",
        "Model provider or model name metadata is missing.",
    )


def _contains_summary_section_check(text: str | None) -> EvaluationCheckResult:
    if not _has_inspectable_text(text):
        return _skipped("contains_summary_section", "Artifact content was not available.")
    if _summary_section(text) is not None:
        return _passed("contains_summary_section", "Summary section is present.")

    return _failed_error("contains_summary_section", "Summary section is missing.")


def _summary_section_non_empty_check(text: str | None) -> EvaluationCheckResult:
    if not _has_inspectable_text(text):
        return _skipped("summary_section_non_empty", "Artifact content was not available.")

    summary_text = _summary_section(text)
    if summary_text is None:
        return _skipped("summary_section_non_empty", "Summary section was not found.")
    if summary_text.strip():
        return _passed("summary_section_non_empty", "Summary section is non-empty.")

    return _failed_error("summary_section_non_empty", "Summary section is empty.")


def _contains_usage_section_check(text: str | None) -> EvaluationCheckResult:
    if not _has_inspectable_text(text):
        return _skipped("contains_usage_section", "Artifact content was not available.")
    if "## Token And Cost Metadata" in text:
        return _passed("contains_usage_section", "Token and cost metadata section is present.")

    return _failed_warning(
        "contains_usage_section",
        "Token and cost metadata section is missing.",
    )


def _placeholder_only_output_check(text: str | None) -> EvaluationCheckResult:
    if not _has_inspectable_text(text):
        return _skipped("placeholder_only_output", "Artifact content was not available.")

    summary_text = _summary_section(text)
    if summary_text is None or not summary_text.strip():
        return _skipped("placeholder_only_output", "Summary text was not available.")
    if _is_placeholder_text(summary_text):
        return _failed_error(
            "placeholder_only_output",
            "Summary appears to contain only placeholder output.",
        )

    return _passed("placeholder_only_output", "Summary does not look placeholder-only.")


def _summary_section(text: str) -> str | None:
    match = _SUMMARY_HEADING_PATTERN.search(text)
    if match is None:
        return None

    summary_start = match.end()
    next_heading_match = _NEXT_HEADING_PATTERN.search(text, summary_start)
    summary_end = next_heading_match.start() if next_heading_match else len(text)
    return text[summary_start:summary_end].strip()


def _has_inspectable_text(text: str | None) -> TypeGuard[str]:
    return text is not None and bool(text.strip())


def _is_placeholder_text(text: str) -> bool:
    normalized_text = " ".join(text.strip().lower().split())
    return normalized_text in _PLACEHOLDER_SUMMARIES


def _passed(check_name: str, message: str) -> EvaluationCheckResult:
    return EvaluationCheckResult(
        check_name=check_name,
        status=EvaluationStatus.PASSED,
        severity=EvaluationSeverity.INFO,
        message=message,
    )


def _skipped(check_name: str, message: str) -> EvaluationCheckResult:
    return EvaluationCheckResult(
        check_name=check_name,
        status=EvaluationStatus.SKIPPED,
        severity=EvaluationSeverity.INFO,
        message=message,
    )


def _failed_warning(
    check_name: str,
    message: str,
    *,
    details: dict[str, str] | None = None,
) -> EvaluationCheckResult:
    return EvaluationCheckResult(
        check_name=check_name,
        status=EvaluationStatus.FAILED,
        severity=EvaluationSeverity.WARNING,
        message=message,
        details=details or {},
    )


def _failed_error(
    check_name: str,
    message: str,
    *,
    details: dict[str, str] | None = None,
) -> EvaluationCheckResult:
    return EvaluationCheckResult(
        check_name=check_name,
        status=EvaluationStatus.FAILED,
        severity=EvaluationSeverity.ERROR,
        message=message,
        details=details or {},
    )
