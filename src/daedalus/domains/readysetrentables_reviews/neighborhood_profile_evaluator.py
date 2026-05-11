"""Deterministic evaluators for ReadySetRentables neighborhood profile artifacts."""

import json
import re
from pathlib import Path
from typing import Any, TypeGuard
from uuid import UUID

from pydantic import ValidationError

from daedalus.domains.readysetrentables_reviews.neighborhood_profile_models import (
    NeighborhoodProfileResult,
)
from daedalus.evaluation import (
    EvaluationCheckResult,
    EvaluationReport,
    EvaluationSeverity,
    EvaluationStatus,
)

MARKDOWN_EVALUATOR_NAME = "readysetrentables_neighborhood_profile_markdown_basic"
MARKDOWN_EVALUATOR_VERSION = "v0"
MARKDOWN_TARGET_TYPE = "neighborhood_profile_markdown"

JSON_EVALUATOR_NAME = "readysetrentables_neighborhood_profile_json_basic"
JSON_EVALUATOR_VERSION = "v0"
JSON_TARGET_TYPE = "neighborhood_profile_json"

_METADATA_HEADER_MARKER = "<!-- Neighborhood Profile Metadata -->"
_HTML_COMMENT_PATTERN = re.compile(r"^\s*<!--.*-->\s*$")
_TITLE_PATTERN = re.compile(r"^#\s+\S", re.MULTILINE)
_RISK_KEYWORDS = ("risk", "caveat", "consideration")
_PLACEHOLDER_BODIES = {
    "placeholder",
    "tbd",
    "todo",
    "fake model response",
}


def evaluate_neighborhood_profile_markdown(
    *,
    profile_path: Path,
    run_id: UUID | None = None,
) -> EvaluationReport:
    """Evaluate a neighborhood_profile.md artifact with deterministic local checks."""
    exists = profile_path.is_file()
    text = profile_path.read_text(encoding="utf-8") if exists else None

    checks = [
        _artifact_exists_check(
            target="Neighborhood profile markdown",
            profile_path=profile_path,
            exists=exists,
        ),
        _artifact_non_empty_check(
            target="Neighborhood profile markdown",
            text=text,
        ),
        _contains_title_check(text=text),
        _contains_metadata_header_check(text=text),
        _contains_summary_or_intro_check(text=text),
        _contains_risks_or_caveats_check(text=text),
        _placeholder_only_output_check(text=text),
    ]

    return EvaluationReport(
        run_id=run_id,
        artifact_path=profile_path,
        target_name=profile_path.name,
        target_type=MARKDOWN_TARGET_TYPE,
        evaluator_name=MARKDOWN_EVALUATOR_NAME,
        evaluator_version=MARKDOWN_EVALUATOR_VERSION,
        checks=checks,
    )


def evaluate_neighborhood_profile_json(
    *,
    profile_path: Path,
    run_id: UUID | None = None,
) -> EvaluationReport:
    """Evaluate a neighborhood_profile.json artifact with deterministic local checks."""
    exists = profile_path.is_file()
    text = profile_path.read_text(encoding="utf-8") if exists else None
    parsed = _safe_parse_json(text)
    result = _safe_parse_result(parsed)

    checks = [
        _artifact_exists_check(
            target="Neighborhood profile JSON",
            profile_path=profile_path,
            exists=exists,
        ),
        _artifact_non_empty_check(
            target="Neighborhood profile JSON",
            text=text,
        ),
        _valid_json_check(text=text, parsed=parsed),
        _valid_schema_check(parsed=parsed, result=result),
        _contains_sections_check(result=result),
        _contains_summary_check(result=result),
        _contains_prompt_metadata_check(result=result),
        _contains_model_metadata_check(result=result),
        _contains_provider_metadata_check(result=result),
        _contains_usage_metadata_check(result=result),
    ]

    return EvaluationReport(
        run_id=run_id,
        artifact_path=profile_path,
        target_name=profile_path.name,
        target_type=JSON_TARGET_TYPE,
        evaluator_name=JSON_EVALUATOR_NAME,
        evaluator_version=JSON_EVALUATOR_VERSION,
        checks=checks,
    )


# --- Markdown helpers ---


def _contains_title_check(text: str | None) -> EvaluationCheckResult:
    if not _has_inspectable_text(text):
        return _skipped("contains_title", "Artifact content was not available.")
    if _TITLE_PATTERN.search(text):
        return _passed("contains_title", "Markdown title heading is present.")
    return _failed_error("contains_title", "Markdown title heading is missing.")


def _contains_metadata_header_check(text: str | None) -> EvaluationCheckResult:
    if not _has_inspectable_text(text):
        return _skipped("contains_metadata_header", "Artifact content was not available.")
    if _METADATA_HEADER_MARKER in text:
        return _passed("contains_metadata_header", "Metadata header is present.")
    return _failed_warning(
        "contains_metadata_header",
        "Metadata header is missing.",
    )


def _contains_summary_or_intro_check(text: str | None) -> EvaluationCheckResult:
    if not _has_inspectable_text(text):
        return _skipped("contains_summary_or_intro", "Artifact content was not available.")
    body = _strip_metadata_header(text)
    body_after_title = _remove_first_title(body)
    if body_after_title.strip():
        return _passed("contains_summary_or_intro", "Summary or intro content is present.")
    return _failed_error(
        "contains_summary_or_intro",
        "Summary or intro content after the title is missing.",
    )


def _contains_risks_or_caveats_check(text: str | None) -> EvaluationCheckResult:
    if not _has_inspectable_text(text):
        return _skipped("contains_risks_or_caveats", "Artifact content was not available.")
    body = _strip_metadata_header(text).lower()
    if any(keyword in body for keyword in _RISK_KEYWORDS):
        return _passed(
            "contains_risks_or_caveats",
            "Risks or caveats content is present.",
        )
    return _failed_warning(
        "contains_risks_or_caveats",
        "No risks or caveats keywords found in the profile body.",
    )


def _placeholder_only_output_check(text: str | None) -> EvaluationCheckResult:
    if not _has_inspectable_text(text):
        return _skipped("placeholder_only_output", "Artifact content was not available.")
    body = _strip_metadata_header(text).strip()
    if not body:
        return _skipped("placeholder_only_output", "Profile body was not available.")
    normalized = " ".join(body.lower().split())
    if normalized in _PLACEHOLDER_BODIES:
        return _failed_error(
            "placeholder_only_output",
            "Profile appears to contain only placeholder output.",
        )
    return _passed(
        "placeholder_only_output",
        "Profile does not look placeholder-only.",
    )


def _strip_metadata_header(text: str) -> str:
    lines = text.split("\n")
    body_lines = [line for line in lines if not _HTML_COMMENT_PATTERN.match(line)]
    return "\n".join(body_lines)


def _remove_first_title(text: str) -> str:
    match = _TITLE_PATTERN.search(text)
    if match is None:
        return text
    end_of_line = text.find("\n", match.end())
    if end_of_line == -1:
        return ""
    return text[end_of_line + 1 :]


# --- JSON helpers ---


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
) -> NeighborhoodProfileResult | None:
    if parsed is None:
        return None
    try:
        return NeighborhoodProfileResult.model_validate(parsed)
    except ValidationError:
        return None


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
    result: NeighborhoodProfileResult | None,
) -> EvaluationCheckResult:
    if parsed is None:
        return _skipped(
            "valid_neighborhood_profile_result_schema",
            "Parsed JSON was not available.",
        )
    if result is not None:
        return _passed(
            "valid_neighborhood_profile_result_schema",
            "Artifact matches the NeighborhoodProfileResult schema.",
        )
    return _failed_error(
        "valid_neighborhood_profile_result_schema",
        "Artifact does not match the NeighborhoodProfileResult schema.",
    )


def _contains_sections_check(
    result: NeighborhoodProfileResult | None,
) -> EvaluationCheckResult:
    if result is None:
        return _skipped("contains_sections", "Parsed result was not available.")
    if result.sections:
        return _passed("contains_sections", "Sections are present.")
    return _failed_warning("contains_sections", "Sections list is empty.")


def _contains_summary_check(
    result: NeighborhoodProfileResult | None,
) -> EvaluationCheckResult:
    if result is None:
        return _skipped("contains_summary", "Parsed result was not available.")
    if result.summary.strip():
        return _passed("contains_summary", "Summary is present.")
    return _failed_error("contains_summary", "Summary is empty.")


def _contains_prompt_metadata_check(
    result: NeighborhoodProfileResult | None,
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
    result: NeighborhoodProfileResult | None,
) -> EvaluationCheckResult:
    if result is None:
        return _skipped("contains_model_metadata", "Parsed result was not available.")
    if result.model_name.strip():
        return _passed("contains_model_metadata", "Model metadata is present.")
    return _failed_warning("contains_model_metadata", "Model name metadata is missing.")


def _contains_provider_metadata_check(
    result: NeighborhoodProfileResult | None,
) -> EvaluationCheckResult:
    if result is None:
        return _skipped("contains_provider_metadata", "Parsed result was not available.")
    if result.provider:
        return _passed("contains_provider_metadata", "Provider metadata is present.")
    return _failed_warning("contains_provider_metadata", "Provider metadata is missing.")


def _contains_usage_metadata_check(
    result: NeighborhoodProfileResult | None,
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


# --- shared helpers ---


def _artifact_exists_check(
    *,
    target: str,
    profile_path: Path,
    exists: bool,
) -> EvaluationCheckResult:
    if exists:
        return _passed("artifact_exists", f"{target} artifact exists.")
    return _failed_error(
        "artifact_exists",
        f"{target} artifact was not found.",
        details={"path": str(profile_path)},
    )


def _artifact_non_empty_check(
    *,
    target: str,
    text: str | None,
) -> EvaluationCheckResult:
    if text is None:
        return _skipped("artifact_non_empty", "Artifact content was not available.")
    if text.strip():
        return _passed("artifact_non_empty", f"{target} artifact is non-empty.")
    return _failed_error("artifact_non_empty", f"{target} artifact is empty.")


def _has_inspectable_text(text: str | None) -> TypeGuard[str]:
    return text is not None and bool(text.strip())


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
