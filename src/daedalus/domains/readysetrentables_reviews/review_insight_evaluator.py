"""Deterministic evaluator for ReadySetRentables review insight extraction results."""

import json
from decimal import Decimal, InvalidOperation
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
ALLOWED_THEME_SENTIMENTS = frozenset({"positive", "negative", "mixed", "neutral"})
PLACEHOLDER_MARKERS = (
    "todo",
    "tbd",
    "lorem ipsum",
    "placeholder",
)


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
        _contains_run_id_check(parsed=parsed, result=result),
        _contains_provider_metadata_check(parsed=parsed, result=result),
        _contains_model_metadata_check(parsed=parsed, result=result),
        _contains_prompt_name_check(parsed=parsed, result=result),
        _contains_prompt_version_check(parsed=parsed, result=result),
        _contains_themes_check(result=result),
        _theme_names_non_empty_check(parsed=parsed, result=result),
        _theme_sentiments_allowed_check(parsed=parsed, result=result),
        _theme_evidence_counts_non_negative_check(parsed=parsed, result=result),
        _theme_summaries_non_empty_check(parsed=parsed, result=result),
        _strengths_present_check(parsed=parsed, result=result),
        _risks_present_check(parsed=parsed, result=result),
        _guest_expectations_present_check(parsed=parsed, result=result),
        _contains_raw_insight_summary_check(parsed=parsed, result=result),
        _usage_metadata_check(parsed=parsed, result=result),
        _placeholder_content_check(parsed=parsed),
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


def _contains_run_id_check(
    *,
    parsed: dict[str, Any] | None,
    result: ReviewInsightExtractionResult | None,
) -> EvaluationCheckResult:
    if parsed is None:
        return _skipped("contains_run_id", "Parsed JSON was not available.")
    if result is not None:
        return _passed("contains_run_id", "Run lineage is present.")
    if _non_empty_string(parsed.get("run_id")):
        return _passed("contains_run_id", "Run lineage is present.")
    return _failed_warning("contains_run_id", "Run lineage is missing.")


def _contains_provider_metadata_check(
    *,
    parsed: dict[str, Any] | None,
    result: ReviewInsightExtractionResult | None,
) -> EvaluationCheckResult:
    if parsed is None:
        return _skipped("contains_provider_metadata", "Parsed JSON was not available.")
    if result is not None and result.provider:
        return _passed("contains_provider_metadata", "Provider metadata is present.")
    if _non_empty_string(parsed.get("provider")):
        return _passed("contains_provider_metadata", "Provider metadata is present.")
    return _failed_error("contains_provider_metadata", "Provider metadata is missing.")


def _contains_model_metadata_check(
    *,
    parsed: dict[str, Any] | None,
    result: ReviewInsightExtractionResult | None,
) -> EvaluationCheckResult:
    if parsed is None:
        return _skipped("contains_model_metadata", "Parsed JSON was not available.")
    if result is not None and result.model_name.strip():
        return _passed("contains_model_metadata", "Model metadata is present.")
    if _non_empty_string(parsed.get("model_name")):
        return _passed("contains_model_metadata", "Model metadata is present.")
    return _failed_error("contains_model_metadata", "Model name metadata is missing.")


def _contains_prompt_name_check(
    *,
    parsed: dict[str, Any] | None,
    result: ReviewInsightExtractionResult | None,
) -> EvaluationCheckResult:
    if parsed is None:
        return _skipped("contains_prompt_name", "Parsed JSON was not available.")
    if result is not None and result.prompt_name.strip():
        return _passed("contains_prompt_name", "Prompt name metadata is present.")
    if _non_empty_string(parsed.get("prompt_name")):
        return _passed("contains_prompt_name", "Prompt name metadata is present.")
    return _failed_error("contains_prompt_name", "Prompt name metadata is missing.")


def _contains_prompt_version_check(
    *,
    parsed: dict[str, Any] | None,
    result: ReviewInsightExtractionResult | None,
) -> EvaluationCheckResult:
    if parsed is None:
        return _skipped("contains_prompt_version", "Parsed JSON was not available.")
    if result is not None and result.prompt_version.strip():
        return _passed("contains_prompt_version", "Prompt version metadata is present.")
    if _non_empty_string(parsed.get("prompt_version")):
        return _passed("contains_prompt_version", "Prompt version metadata is present.")
    return _failed_error("contains_prompt_version", "Prompt version metadata is missing.")


def _contains_themes_check(
    result: ReviewInsightExtractionResult | None,
) -> EvaluationCheckResult:
    if result is None:
        return _skipped("contains_themes", "Parsed result was not available.")
    if result.themes:
        return _passed("contains_themes", "Themes are present.")
    return _failed_error("contains_themes", "Themes list is empty.")


def _theme_names_non_empty_check(
    *,
    parsed: dict[str, Any] | None,
    result: ReviewInsightExtractionResult | None,
) -> EvaluationCheckResult:
    themes = _theme_dicts(parsed=parsed, result=result)
    if themes is None:
        return _skipped("theme_names_non_empty", "Theme data was not available.")
    if not themes:
        return _skipped("theme_names_non_empty", "No themes to inspect.")
    if all(_non_empty_string(theme.get("name")) for theme in themes):
        return _passed("theme_names_non_empty", "All themes have non-empty names.")
    return _failed_error("theme_names_non_empty", "One or more theme names are empty.")


def _theme_sentiments_allowed_check(
    *,
    parsed: dict[str, Any] | None,
    result: ReviewInsightExtractionResult | None,
) -> EvaluationCheckResult:
    themes = _theme_dicts(parsed=parsed, result=result)
    if themes is None:
        return _skipped("theme_sentiments_allowed", "Theme data was not available.")
    if not themes:
        return _skipped("theme_sentiments_allowed", "No themes to inspect.")
    invalid_count = sum(
        1
        for theme in themes
        if str(theme.get("sentiment", "")).strip().lower() not in ALLOWED_THEME_SENTIMENTS
    )
    if invalid_count == 0:
        return _passed("theme_sentiments_allowed", "All theme sentiments are allowed.")
    return _failed_error(
        "theme_sentiments_allowed",
        "One or more theme sentiments are outside the allowed set.",
        details={"invalid_count": str(invalid_count)},
    )


def _theme_evidence_counts_non_negative_check(
    *,
    parsed: dict[str, Any] | None,
    result: ReviewInsightExtractionResult | None,
) -> EvaluationCheckResult:
    themes = _theme_dicts(parsed=parsed, result=result)
    if themes is None:
        return _skipped("theme_evidence_counts_non_negative", "Theme data was not available.")
    if not themes:
        return _skipped("theme_evidence_counts_non_negative", "No themes to inspect.")
    invalid_count = sum(
        1
        for theme in themes
        if not isinstance(theme.get("evidence_count"), int) or theme["evidence_count"] < 0
    )
    if invalid_count == 0:
        return _passed(
            "theme_evidence_counts_non_negative",
            "All theme evidence counts are non-negative.",
        )
    return _failed_error(
        "theme_evidence_counts_non_negative",
        "One or more theme evidence counts are missing or negative.",
        details={"invalid_count": str(invalid_count)},
    )


def _theme_summaries_non_empty_check(
    *,
    parsed: dict[str, Any] | None,
    result: ReviewInsightExtractionResult | None,
) -> EvaluationCheckResult:
    themes = _theme_dicts(parsed=parsed, result=result)
    if themes is None:
        return _skipped("theme_summaries_non_empty", "Theme data was not available.")
    if not themes:
        return _skipped("theme_summaries_non_empty", "No themes to inspect.")
    if all(_non_empty_string(theme.get("summary")) for theme in themes):
        return _passed("theme_summaries_non_empty", "All themes have non-empty summaries.")
    return _failed_error("theme_summaries_non_empty", "One or more theme summaries are empty.")


def _strengths_present_check(
    *,
    parsed: dict[str, Any] | None,
    result: ReviewInsightExtractionResult | None,
) -> EvaluationCheckResult:
    return _string_list_check(
        parsed=parsed,
        result=result,
        field_name="strengths",
        allow_empty=False,
        check_name="strengths_present",
        label="Strengths",
    )


def _risks_present_check(
    *,
    parsed: dict[str, Any] | None,
    result: ReviewInsightExtractionResult | None,
) -> EvaluationCheckResult:
    return _string_list_check(
        parsed=parsed,
        result=result,
        field_name="risks",
        allow_empty=True,
        check_name="risks_present",
        label="Risks",
    )


def _guest_expectations_present_check(
    *,
    parsed: dict[str, Any] | None,
    result: ReviewInsightExtractionResult | None,
) -> EvaluationCheckResult:
    return _string_list_check(
        parsed=parsed,
        result=result,
        field_name="guest_expectations",
        allow_empty=False,
        check_name="guest_expectations_present",
        label="Guest expectations",
    )


def _contains_raw_insight_summary_check(
    *,
    parsed: dict[str, Any] | None,
    result: ReviewInsightExtractionResult | None,
) -> EvaluationCheckResult:
    if parsed is None:
        return _skipped("contains_raw_insight_summary", "Parsed JSON was not available.")
    if result is not None and result.raw_insight_summary.strip():
        return _passed("contains_raw_insight_summary", "Raw insight summary is present.")
    if _non_empty_string(parsed.get("raw_insight_summary")):
        return _passed("contains_raw_insight_summary", "Raw insight summary is present.")
    return _failed_error("contains_raw_insight_summary", "Raw insight summary is empty.")


def _usage_metadata_check(
    *,
    parsed: dict[str, Any] | None,
    result: ReviewInsightExtractionResult | None,
) -> EvaluationCheckResult:
    if parsed is None:
        return _skipped("usage_metadata_valid", "Parsed JSON was not available.")
    fields = ("input_tokens", "output_tokens", "total_tokens", "estimated_cost_usd")
    present_fields = [field for field in fields if field in parsed and parsed[field] is not None]
    if not present_fields:
        return _warning(
            "usage_metadata_valid",
            "Token and cost usage metadata are not present.",
        )
    if result is not None:
        return _passed("usage_metadata_valid", "Present token and cost metadata is valid.")
    invalid_count = sum(1 for field in present_fields if not _is_non_negative_number(parsed[field]))
    if invalid_count == 0:
        return _passed("usage_metadata_valid", "Present token and cost metadata is valid.")
    return _failed_error(
        "usage_metadata_valid",
        "One or more token or cost metadata fields are invalid.",
        details={"invalid_count": str(invalid_count)},
    )


def _placeholder_content_check(parsed: dict[str, Any] | None) -> EvaluationCheckResult:
    if parsed is None:
        return _skipped("placeholder_content", "Parsed JSON was not available.")
    strings = list(_iter_strings(parsed))
    placeholder_count = sum(
        1
        for value in strings
        if any(marker in value.strip().lower() for marker in PLACEHOLDER_MARKERS)
    )
    if placeholder_count == 0:
        return _passed("placeholder_content", "No obvious placeholder content was found.")
    return _warning(
        "placeholder_content",
        "Obvious placeholder content was found.",
        details={"placeholder_count": str(placeholder_count)},
    )


def _string_list_check(
    *,
    parsed: dict[str, Any] | None,
    result: ReviewInsightExtractionResult | None,
    field_name: str,
    allow_empty: bool,
    check_name: str,
    label: str,
) -> EvaluationCheckResult:
    if parsed is None:
        return _skipped(check_name, "Parsed JSON was not available.")
    value = getattr(result, field_name) if result is not None else parsed.get(field_name)
    if not isinstance(value, list):
        return _failed_error(check_name, f"{label} list is missing.")
    if not value and not allow_empty:
        return _failed_error(check_name, f"{label} list is empty.")
    if all(isinstance(entry, str) and entry.strip() for entry in value):
        return _passed(check_name, f"{label} list is present and valid.")
    return _failed_error(check_name, f"{label} list contains invalid entries.")


def _theme_dicts(
    *,
    parsed: dict[str, Any] | None,
    result: ReviewInsightExtractionResult | None,
) -> list[dict[str, Any]] | None:
    if result is not None:
        return [
            {
                "name": theme.name,
                "sentiment": theme.sentiment,
                "evidence_count": theme.evidence_count,
                "summary": theme.summary,
            }
            for theme in result.themes
        ]
    if parsed is None:
        return None
    themes = parsed.get("themes")
    if not isinstance(themes, list):
        return None
    return [theme for theme in themes if isinstance(theme, dict)]


def _non_empty_string(value: object) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _is_non_negative_number(value: object) -> bool:
    if not isinstance(value, int | float | str):
        return False
    try:
        parsed = Decimal(str(value))
    except InvalidOperation:
        return False
    return parsed >= 0


def _iter_strings(value: object) -> list[str]:
    strings: list[str] = []
    if isinstance(value, str):
        strings.append(value)
    elif isinstance(value, dict):
        for item in value.values():
            strings.extend(_iter_strings(item))
    elif isinstance(value, list):
        for item in value:
            strings.extend(_iter_strings(item))
    return strings


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


def _warning(
    check_name: str,
    message: str,
    *,
    details: dict[str, str] | None = None,
) -> EvaluationCheckResult:
    return EvaluationCheckResult(
        check_name=check_name,
        status=EvaluationStatus.WARNING,
        severity=EvaluationSeverity.WARNING,
        message=message,
        details=details or {},
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
