import json
from datetime import datetime, timezone
from pathlib import Path
from uuid import UUID, uuid4

from daedalus.domains.readysetrentables_reviews.source_extraction_artifacts import (
    write_rsr_source_extract_json,
)
from daedalus.domains.readysetrentables_reviews.source_extraction_evaluator import (
    EVALUATOR_NAME,
    EVALUATOR_VERSION,
    TARGET_TYPE,
    evaluate_rsr_source_extract_json,
)
from daedalus.domains.readysetrentables_reviews.source_extraction_fixtures import (
    build_sample_rsr_source_extraction_result,
)
from daedalus.domains.readysetrentables_reviews.source_extraction_models import (
    RsrSourceExtractionRequest,
    RsrSourceExtractionResult,
    RsrSourceListingContext,
    RsrSourceNeighborhoodContext,
    RsrSourceReviewRecord,
)
from daedalus.evaluation import EvaluationCheckResult, EvaluationSeverity, EvaluationStatus


def test_valid_source_extract_produces_evaluation_report(tmp_path: Path) -> None:
    path, run_id = _write_valid_fixture(tmp_path)

    report = evaluate_rsr_source_extract_json(source_extract_path=path, run_id=run_id)

    assert report.artifact_path == path
    assert report.checks


def test_report_target_name_is_file_name(tmp_path: Path) -> None:
    path, run_id = _write_valid_fixture(tmp_path)

    report = evaluate_rsr_source_extract_json(source_extract_path=path, run_id=run_id)

    assert report.target_name == "rsr_source_extract.json"


def test_report_target_type_is_rsr_source_extract(tmp_path: Path) -> None:
    path, run_id = _write_valid_fixture(tmp_path)

    report = evaluate_rsr_source_extract_json(source_extract_path=path, run_id=run_id)

    assert report.target_type == TARGET_TYPE


def test_report_evaluator_identity_is_set(tmp_path: Path) -> None:
    path, run_id = _write_valid_fixture(tmp_path)

    report = evaluate_rsr_source_extract_json(source_extract_path=path, run_id=run_id)

    assert report.evaluator_name == EVALUATOR_NAME
    assert report.evaluator_version == EVALUATOR_VERSION


def test_report_run_id_is_preserved_when_provided(tmp_path: Path) -> None:
    path, run_id = _write_valid_fixture(tmp_path)

    report = evaluate_rsr_source_extract_json(source_extract_path=path, run_id=run_id)

    assert report.run_id == run_id


def test_valid_fixture_passes_required_checks(tmp_path: Path) -> None:
    path, run_id = _write_valid_fixture(tmp_path)

    report = evaluate_rsr_source_extract_json(source_extract_path=path, run_id=run_id)

    statuses = {check.check_name: check.status for check in report.checks}
    assert statuses["artifact_exists"] == EvaluationStatus.PASSED
    assert statuses["artifact_non_empty"] == EvaluationStatus.PASSED
    assert statuses["valid_json"] == EvaluationStatus.PASSED
    assert statuses["valid_source_extraction_schema"] == EvaluationStatus.PASSED
    assert statuses["contains_reviews"] == EvaluationStatus.PASSED
    assert statuses["contains_review_text"] == EvaluationStatus.PASSED
    assert statuses["contains_listing_context"] == EvaluationStatus.PASSED
    assert statuses["contains_neighborhood_context"] == EvaluationStatus.PASSED
    assert statuses["contains_source_metadata"] == EvaluationStatus.PASSED
    assert statuses["synthetic_fixture_marker"] == EvaluationStatus.PASSED


def test_valid_synthetic_fixture_marker_check_has_info_severity(tmp_path: Path) -> None:
    path, _ = _write_valid_fixture(tmp_path)

    report = evaluate_rsr_source_extract_json(source_extract_path=path)

    check = _find_check(report.checks, "synthetic_fixture_marker")
    assert check.status == EvaluationStatus.PASSED
    assert check.severity == EvaluationSeverity.INFO
    assert "Synthetic fixture markers are present." in check.message


def test_missing_artifact_produces_failed_artifact_exists_check(tmp_path: Path) -> None:
    path = tmp_path / "missing.json"

    report = evaluate_rsr_source_extract_json(source_extract_path=path)

    check = _find_check(report.checks, "artifact_exists")
    assert check.status == EvaluationStatus.FAILED
    assert check.severity == EvaluationSeverity.ERROR


def test_empty_artifact_produces_failed_artifact_non_empty_check(tmp_path: Path) -> None:
    path = tmp_path / "rsr_source_extract.json"
    path.write_text("", encoding="utf-8")

    report = evaluate_rsr_source_extract_json(source_extract_path=path)

    check = _find_check(report.checks, "artifact_non_empty")
    assert check.status == EvaluationStatus.FAILED
    assert check.severity == EvaluationSeverity.ERROR


def test_invalid_json_produces_failed_valid_json_check(tmp_path: Path) -> None:
    path = tmp_path / "rsr_source_extract.json"
    path.write_text("{not valid json", encoding="utf-8")

    report = evaluate_rsr_source_extract_json(source_extract_path=path)

    check = _find_check(report.checks, "valid_json")
    assert check.status == EvaluationStatus.FAILED
    assert check.severity == EvaluationSeverity.ERROR


def test_schema_invalid_produces_failed_schema_check(tmp_path: Path) -> None:
    path = tmp_path / "rsr_source_extract.json"
    path.write_text(json.dumps({"not_a_real_field": "value"}), encoding="utf-8")

    report = evaluate_rsr_source_extract_json(source_extract_path=path)

    check = _find_check(report.checks, "valid_source_extraction_schema")
    assert check.status == EvaluationStatus.FAILED
    assert check.severity == EvaluationSeverity.ERROR


def test_empty_reviews_produces_warning_contains_reviews_check(tmp_path: Path) -> None:
    path = tmp_path / "rsr_source_extract.json"
    write_rsr_source_extract_json(
        result=_result(reviews=[]),
        output_path=path,
    )

    report = evaluate_rsr_source_extract_json(source_extract_path=path)

    check = _find_check(report.checks, "contains_reviews")
    assert check.status == EvaluationStatus.FAILED
    assert check.severity == EvaluationSeverity.WARNING


def test_empty_listings_produces_warning_contains_listing_context_check(
    tmp_path: Path,
) -> None:
    path = tmp_path / "rsr_source_extract.json"
    write_rsr_source_extract_json(
        result=_result(listings=[]),
        output_path=path,
    )

    report = evaluate_rsr_source_extract_json(source_extract_path=path)

    check = _find_check(report.checks, "contains_listing_context")
    assert check.status == EvaluationStatus.FAILED
    assert check.severity == EvaluationSeverity.WARNING


def test_missing_neighborhood_produces_warning_contains_neighborhood_context_check(
    tmp_path: Path,
) -> None:
    path = tmp_path / "rsr_source_extract.json"
    result = RsrSourceExtractionResult(
        request=RsrSourceExtractionRequest(market_name="Sample Market"),
        extracted_at_utc=datetime(2024, 1, 1, tzinfo=timezone.utc),
        reviews=[
            RsrSourceReviewRecord(
                review_id="synthetic-review-001",
                review_text="Synthetic review: nice location.",
            )
        ],
        listings=[RsrSourceListingContext(listing_id="synthetic-listing-001")],
        neighborhood=None,
        metadata={"fixture": "true", "source": "synthetic"},
    )
    write_rsr_source_extract_json(result=result, output_path=path)

    report = evaluate_rsr_source_extract_json(source_extract_path=path)

    check = _find_check(report.checks, "contains_neighborhood_context")
    assert check.status == EvaluationStatus.FAILED
    assert check.severity == EvaluationSeverity.WARNING


def test_real_style_artifact_without_synthetic_marker_produces_warning_status(
    tmp_path: Path,
) -> None:
    path = _write_real_style_source_extract(tmp_path)

    report = evaluate_rsr_source_extract_json(source_extract_path=path)

    check = _find_check(report.checks, "synthetic_fixture_marker")
    assert check.status == EvaluationStatus.WARNING
    assert check.severity == EvaluationSeverity.WARNING
    assert "may represent real source data" in check.message


def test_real_style_artifact_without_synthetic_marker_has_no_failed_marker_check(
    tmp_path: Path,
) -> None:
    path = _write_real_style_source_extract(tmp_path)

    report = evaluate_rsr_source_extract_json(source_extract_path=path)

    check = _find_check(report.checks, "synthetic_fixture_marker")
    assert check.status != EvaluationStatus.FAILED


def test_valid_real_style_artifact_has_zero_failed_count(tmp_path: Path) -> None:
    path = _write_real_style_source_extract(tmp_path)

    report = evaluate_rsr_source_extract_json(source_extract_path=path)

    assert report.failed_count == 0


def test_valid_real_style_artifact_report_passed_remains_true(tmp_path: Path) -> None:
    path = _write_real_style_source_extract(tmp_path)

    report = evaluate_rsr_source_extract_json(source_extract_path=path)

    assert report.passed is True


def test_synthetic_fixture_marker_messages_do_not_include_artifact_contents(
    tmp_path: Path,
) -> None:
    path = _write_real_style_source_extract(tmp_path)

    report = evaluate_rsr_source_extract_json(source_extract_path=path)

    messages = "\n".join(check.message for check in report.checks)
    assert "Synthetic review: nice location." not in messages
    assert "synthetic-review-001" not in messages
    assert "synthetic-listing-001" not in messages


def test_empty_metadata_produces_warning_contains_source_metadata_check(
    tmp_path: Path,
) -> None:
    path = tmp_path / "rsr_source_extract.json"
    write_rsr_source_extract_json(
        result=_result(metadata={}),
        output_path=path,
    )

    report = evaluate_rsr_source_extract_json(source_extract_path=path)

    check = _find_check(report.checks, "contains_source_metadata")
    assert check.status == EvaluationStatus.FAILED
    assert check.severity == EvaluationSeverity.WARNING


def test_evaluator_does_not_call_model_providers(tmp_path: Path) -> None:
    path, _ = _write_valid_fixture(tmp_path)

    report = evaluate_rsr_source_extract_json(source_extract_path=path)

    assert report.checks


def test_evaluator_does_not_require_db_access(tmp_path: Path) -> None:
    path, _ = _write_valid_fixture(tmp_path)

    report = evaluate_rsr_source_extract_json(source_extract_path=path)

    assert report.artifact_path == path


def test_report_serialization_uses_enum_string_values(tmp_path: Path) -> None:
    path, run_id = _write_valid_fixture(tmp_path)

    report = evaluate_rsr_source_extract_json(source_extract_path=path, run_id=run_id)
    data = json.loads(report.model_dump_json())

    for check in data["checks"]:
        assert check["status"] in {"passed", "failed", "warning", "skipped"}
        assert check["severity"] in {"info", "warning", "error"}


# --- helpers ---


def _write_valid_fixture(tmp_path: Path) -> tuple[Path, UUID]:
    run_id = uuid4()
    path = tmp_path / "rsr_source_extract.json"
    write_rsr_source_extract_json(
        result=build_sample_rsr_source_extraction_result(),
        output_path=path,
    )
    return path, run_id


def _write_real_style_source_extract(tmp_path: Path) -> Path:
    path = tmp_path / "rsr_source_extract.json"
    write_rsr_source_extract_json(
        result=_result(
            metadata={
                "extraction_mode": "read_only",
                "repository": "RsrSourceReadOnlyRepository",
            }
        ),
        output_path=path,
    )
    return path


def _result(
    *,
    reviews: list[RsrSourceReviewRecord] | None = None,
    listings: list[RsrSourceListingContext] | None = None,
    neighborhood: RsrSourceNeighborhoodContext | None = None,
    metadata: dict[str, str] | None = None,
) -> RsrSourceExtractionResult:
    default_reviews = [
        RsrSourceReviewRecord(
            review_id="synthetic-review-001",
            review_text="Synthetic review: nice location.",
        )
    ]
    default_listings = [RsrSourceListingContext(listing_id="synthetic-listing-001")]
    default_neighborhood = RsrSourceNeighborhoodContext(
        market_name="Sample Market",
        neighborhood_name="Sample Neighborhood",
    )
    return RsrSourceExtractionResult(
        request=RsrSourceExtractionRequest(market_name="Sample Market"),
        extracted_at_utc=datetime(2024, 1, 1, tzinfo=timezone.utc),
        reviews=reviews if reviews is not None else default_reviews,
        listings=listings if listings is not None else default_listings,
        neighborhood=neighborhood if neighborhood is not None else default_neighborhood,
        metadata=metadata if metadata is not None else {"fixture": "true", "source": "synthetic"},
    )


def _find_check(
    checks: list[EvaluationCheckResult],
    name: str,
) -> EvaluationCheckResult:
    for check in checks:
        if check.check_name == name:
            return check
    raise AssertionError(f"check {name} not found")
