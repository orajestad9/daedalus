"""Deterministic evaluator for ReadySetRentables review insight extraction results."""

import json
from pathlib import Path
from typing import Any
from uuid import UUID

from pydantic import ValidationError

from daedalus.domains.readysetrentables_reviews.review_insight_models import (
    ReviewInsightExtractionResult,
)
from daedalus.evaluation import (
    EvaluationCheckResult,
    EvaluationReport,
    EvaluationSeverity,
    EvaluationStatus,
)

EVALUATOR_NAME = "readysetrentables_review_insights_basic"
EVALUATOR_VERSION = "v0"
TARGET_TYPE = "review_insights"


def evaluate_review_insights_json(
    *,
    insights_path: Path,
    run_id: UUID | None = None,
) -> EvaluationReport:
    """Evaluate a review_insights.json artifact with deterministic local checks."""
    exists = insights_path.is_file()
    text = insights_path.read_text(encoding="utf-8") if exists else None
    parsed = _safe_parse_json(text)
    result = _safe_parse_result(parsed)

    checks = [
        _artifact_exists_check(insights_path=insights_path, exists=exists),
        _artifact_non_empty_check(text=text),
        _valid_json_check(text=text, parsed=parsed),
        _valid_schema_check(parsed=parsed, result=result),
        _contains_themes_check(result=result),
        _contains_raw_insight_summary_check(result=result),
        _contains_prompt_metadata_check(result=result),
        _contains_model_metadata_check(result=result),
        _contains_provider_metadata_check(result=result),
        _contains_usage_metadata_check(result=result),
    ]

    return EvaluationReport(
        run_id=run_id,
        artifact_path=insights_path,
        target_name=insights_path.name,
        target_type=TARGET_TYPE,
        evaluator_name=EVALUATOR_NAME,
        evaluator_version=EVALUATOR_VERSION,
        checks=checks,
    )


def _safe_parse_json(text: str | None) -> dict[str, Any] | None:
    if text is None or not text.strip():
        return None
    try:
        loaded = json.loads(text)
    except json.JSONDecodeError:
        return None
    if isinstance(loaded, dict):
        return loaded
    return None


def _safe_parse_result(
    parsed: dict[str, Any] | None,
) -> ReviewInsightExtractionResult | None:
    if parsed is None:
        return None
    try:
        return ReviewInsightExtractionResult.model_validate(parsed)
    except ValidationError:
        return None


def _artifact_exists_check(
    *,
    insights_path: Path,
    exists: bool,
) -> EvaluationCheckResult:
    if exists:
        return _passed("artifact_exists", "Review insights artifact exists.")
    return _failed_error(
        "artifact_exists",
        "Review insights artifact was not found.",
        details={"path": str(insights_path)},
    )


def _artifact_non_empty_check(text: str | None) -> EvaluationCheckResult:
    if text is None:
        return _skipped("artifact_non_empty", "Artifact content was not available.")
    if text.strip():
        return _passed("artifact_non_empty", "Review insights artifact is non-empty.")
    return _failed_error("artifact_non_empty", "Review insights artifact is empty.")


def _valid_json_check(
    *,
    text: str | None,
    parsed: dict[str, Any] | None,
) -> EvaluationCheckResult:
    if text is None or not text.strip():
        return _skipped("valid_json", "Artifact content was not available.")
    if parsed is not None:
        return _passed("valid_json", "Artifact is valid JSON.")
    return _failed_error("valid_json", "Artifact is not valid JSON.")


def _valid_schema_check(
    *,
    parsed: dict[str, Any] | None,
    result: ReviewInsightExtractionResult | None,
) -> EvaluationCheckResult:
    if parsed is None:
        return _skipped(
            "valid_review_insight_result_schema",
            "Parsed JSON was not available.",
        )
    if result is not None:
        return _passed(
            "valid_review_insight_result_schema",
            "Artifact matches the ReviewInsightExtractionResult schema.",
        )
    return _failed_error(
        "valid_review_insight_result_schema",
        "Artifact does not match the ReviewInsightExtractionResult schema.",
    )


def _contains_themes_check(
    result: ReviewInsightExtractionResult | None,
) -> EvaluationCheckResult:
    if result is None:
        return _skipped("contains_themes", "Parsed result was not available.")
    if result.themes:
        return _passed("contains_themes", "Themes are present.")
    return _failed_warning("contains_themes", "Themes list is empty.")


def _contains_raw_insight_summary_check(
    result: ReviewInsightExtractionResult | None,
) -> EvaluationCheckResult:
    if result is None:
        return _skipped("contains_raw_insight_summary", "Parsed result was not available.")
    if result.raw_insight_summary.strip():
        return _passed("contains_raw_insight_summary", "Raw insight summary is present.")
    return _failed_error("contains_raw_insight_summary", "Raw insight summary is empty.")


def _contains_prompt_metadata_check(
    result: ReviewInsightExtractionResult | None,
) -> EvaluationCheckResult:
    if result is None:
        return _skipped("contains_prompt_metadata", "Parsed result was not available.")
    if result.prompt_name.strip() and result.prompt_version.strip():
        return _passed("contains_prompt_metadata", "Prompt metadata is present.")
    return _failed_warning(
        "contains_prompt_metadata",
        "Prompt name or prompt version metadata is missing.",
    )


def _contains_model_metadata_check(
    result: ReviewInsightExtractionResult | None,
) -> EvaluationCheckResult:
    if result is None:
        return _skipped("contains_model_metadata", "Parsed result was not available.")
    if result.model_name.strip():
        return _passed("contains_model_metadata", "Model metadata is present.")
    return _failed_warning("contains_model_metadata", "Model name metadata is missing.")


def _contains_provider_metadata_check(
    result: ReviewInsightExtractionResult | None,
) -> EvaluationCheckResult:
    if result is None:
        return _skipped("contains_provider_metadata", "Parsed result was not available.")
    if result.provider:
        return _passed("contains_provider_metadata", "Provider metadata is present.")
    return _failed_warning("contains_provider_metadata", "Provider metadata is missing.")


def _contains_usage_metadata_check(
    result: ReviewInsightExtractionResult | None,
) -> EvaluationCheckResult:
    if result is None:
        return _skipped("contains_usage_metadata", "Parsed result was not available.")
    if (
        result.input_tokens is not None
        or result.output_tokens is not None
        or result.total_tokens is not None
        or result.estimated_cost_usd is not None
    ):
        return _passed("contains_usage_metadata", "Token or cost usage metadata is present.")
    return _failed_warning(
        "contains_usage_metadata",
        "Token and cost usage metadata are missing.",
    )


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
