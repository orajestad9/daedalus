"""Deterministic evaluator for ReadySetRentables source extraction artifacts."""

import json
from pathlib import Path
from typing import Any
from uuid import UUID

from pydantic import ValidationError

from daedalus.domains.readysetrentables_reviews.source_extraction_models import (
    RsrSourceExtractionResult,
)
from daedalus.evaluation import (
    EvaluationCheckResult,
    EvaluationReport,
    EvaluationSeverity,
    EvaluationStatus,
)

EVALUATOR_NAME = "readysetrentables_source_extract_basic"
EVALUATOR_VERSION = "v0"
TARGET_TYPE = "rsr_source_extract"


def evaluate_rsr_source_extract_json(
    *,
    source_extract_path: Path,
    run_id: UUID | None = None,
) -> EvaluationReport:
    """Evaluate an rsr_source_extract.json artifact with deterministic local checks."""
    exists = source_extract_path.is_file()
    text = source_extract_path.read_text(encoding="utf-8") if exists else None
    parsed = _safe_parse_json(text)
    result = _safe_parse_result(parsed)

    checks = [
        _artifact_exists_check(source_extract_path=source_extract_path, exists=exists),
        _artifact_non_empty_check(text=text),
        _valid_json_check(text=text, parsed=parsed),
        _valid_schema_check(parsed=parsed, result=result),
        _contains_reviews_check(result=result),
        _contains_review_text_check(result=result),
        _contains_listing_context_check(result=result),
        _contains_neighborhood_context_check(result=result),
        _contains_source_metadata_check(result=result),
        _synthetic_fixture_marker_check(result=result),
    ]

    return EvaluationReport(
        run_id=run_id,
        artifact_path=source_extract_path,
        target_name=source_extract_path.name,
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
) -> RsrSourceExtractionResult | None:
    if parsed is None:
        return None
    try:
        return RsrSourceExtractionResult.model_validate(parsed)
    except ValidationError:
        return None


def _artifact_exists_check(
    *,
    source_extract_path: Path,
    exists: bool,
) -> EvaluationCheckResult:
    if exists:
        return _passed("artifact_exists", "Source extract artifact exists.")
    return _failed_error(
        "artifact_exists",
        "Source extract artifact was not found.",
        details={"path": str(source_extract_path)},
    )


def _artifact_non_empty_check(text: str | None) -> EvaluationCheckResult:
    if text is None:
        return _skipped("artifact_non_empty", "Artifact content was not available.")
    if text.strip():
        return _passed("artifact_non_empty", "Source extract artifact is non-empty.")
    return _failed_error("artifact_non_empty", "Source extract artifact is empty.")


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
    result: RsrSourceExtractionResult | None,
) -> EvaluationCheckResult:
    if parsed is None:
        return _skipped(
            "valid_source_extraction_schema",
            "Parsed JSON was not available.",
        )
    if result is not None:
        return _passed(
            "valid_source_extraction_schema",
            "Artifact matches the RsrSourceExtractionResult schema.",
        )
    return _failed_error(
        "valid_source_extraction_schema",
        "Artifact does not match the RsrSourceExtractionResult schema.",
    )


def _contains_reviews_check(
    result: RsrSourceExtractionResult | None,
) -> EvaluationCheckResult:
    if result is None:
        return _skipped("contains_reviews", "Parsed result was not available.")
    if result.reviews:
        return _passed("contains_reviews", "Reviews are present.")
    return _failed_warning("contains_reviews", "Reviews list is empty.")


def _contains_review_text_check(
    result: RsrSourceExtractionResult | None,
) -> EvaluationCheckResult:
    if result is None:
        return _skipped("contains_review_text", "Parsed result was not available.")
    if not result.reviews:
        return _skipped("contains_review_text", "No reviews to inspect.")
    if all(review.review_text.strip() for review in result.reviews):
        return _passed("contains_review_text", "All reviews have non-empty review_text.")
    return _failed_error(
        "contains_review_text",
        "One or more reviews have empty review_text.",
    )


def _contains_listing_context_check(
    result: RsrSourceExtractionResult | None,
) -> EvaluationCheckResult:
    if result is None:
        return _skipped("contains_listing_context", "Parsed result was not available.")
    if result.listings:
        return _passed("contains_listing_context", "Listing context is present.")
    return _failed_warning("contains_listing_context", "Listings list is empty.")


def _contains_neighborhood_context_check(
    result: RsrSourceExtractionResult | None,
) -> EvaluationCheckResult:
    if result is None:
        return _skipped("contains_neighborhood_context", "Parsed result was not available.")
    if result.neighborhood is not None:
        return _passed(
            "contains_neighborhood_context",
            "Neighborhood context is present.",
        )
    return _failed_warning(
        "contains_neighborhood_context",
        "Neighborhood context is missing.",
    )


def _contains_source_metadata_check(
    result: RsrSourceExtractionResult | None,
) -> EvaluationCheckResult:
    if result is None:
        return _skipped("contains_source_metadata", "Parsed result was not available.")
    if result.source_name.strip() and result.source_version.strip() and result.metadata:
        return _passed(
            "contains_source_metadata",
            "Source name, version, and metadata are present.",
        )
    return _failed_warning(
        "contains_source_metadata",
        "Source name, version, or metadata is missing or empty.",
    )


def _synthetic_fixture_marker_check(
    result: RsrSourceExtractionResult | None,
) -> EvaluationCheckResult:
    if result is None:
        return _skipped("synthetic_fixture_marker", "Parsed result was not available.")
    if result.metadata.get("fixture") == "true" and result.metadata.get("source") == "synthetic":
        return _passed(
            "synthetic_fixture_marker",
            "Synthetic fixture markers are present.",
        )
    return _warning(
        "synthetic_fixture_marker",
        "Artifact does not carry synthetic fixture markers and may represent real source data.",
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
