import json
from decimal import Decimal
from pathlib import Path
from uuid import UUID, uuid4

from daedalus.domains.readysetrentables_reviews.review_insight_artifacts import (
    write_review_insights_json,
)
from daedalus.domains.readysetrentables_reviews.review_insight_evaluator import (
    EVALUATOR_NAME,
    EVALUATOR_VERSION,
    TARGET_TYPE,
    evaluate_review_insights_json,
)
from daedalus.domains.readysetrentables_reviews.review_insight_models import (
    DEFAULT_REVIEW_INSIGHT_PROMPT_NAME,
    DEFAULT_REVIEW_INSIGHT_PROMPT_VERSION,
    ReviewInsightExtractionResult,
    ReviewInsightTheme,
)
from daedalus.evaluation import EvaluationCheckResult, EvaluationSeverity, EvaluationStatus
from daedalus.model_clients.types import ModelProvider


def test_valid_review_insights_json_produces_evaluation_report(tmp_path: Path) -> None:
    insights_path, run_id = _write_valid_insights(tmp_path)

    report = evaluate_review_insights_json(insights_path=insights_path, run_id=run_id)

    assert report.artifact_path == insights_path
    assert report.checks


def test_report_target_name_is_file_name(tmp_path: Path) -> None:
    insights_path, run_id = _write_valid_insights(tmp_path)

    report = evaluate_review_insights_json(insights_path=insights_path, run_id=run_id)

    assert report.target_name == "review_insights.json"


def test_report_target_type_is_review_insights(tmp_path: Path) -> None:
    insights_path, run_id = _write_valid_insights(tmp_path)

    report = evaluate_review_insights_json(insights_path=insights_path, run_id=run_id)

    assert report.target_type == TARGET_TYPE


def test_report_evaluator_identity_is_set(tmp_path: Path) -> None:
    insights_path, run_id = _write_valid_insights(tmp_path)

    report = evaluate_review_insights_json(insights_path=insights_path, run_id=run_id)

    assert report.evaluator_name == EVALUATOR_NAME
    assert report.evaluator_version == EVALUATOR_VERSION


def test_report_run_id_is_preserved_when_provided(tmp_path: Path) -> None:
    insights_path, run_id = _write_valid_insights(tmp_path)

    report = evaluate_review_insights_json(insights_path=insights_path, run_id=run_id)

    assert report.run_id == run_id


def test_report_run_id_none_when_not_provided(tmp_path: Path) -> None:
    insights_path, _ = _write_valid_insights(tmp_path)

    report = evaluate_review_insights_json(insights_path=insights_path)

    assert report.run_id is None


def test_valid_artifact_passes_required_checks(tmp_path: Path) -> None:
    insights_path, run_id = _write_valid_insights(tmp_path)

    report = evaluate_review_insights_json(insights_path=insights_path, run_id=run_id)

    statuses = {check.check_name: check.status for check in report.checks}
    assert statuses["artifact_exists"] == EvaluationStatus.PASSED
    assert statuses["artifact_non_empty"] == EvaluationStatus.PASSED
    assert statuses["valid_json"] == EvaluationStatus.PASSED
    assert statuses["valid_review_insight_result_schema"] == EvaluationStatus.PASSED
    assert statuses["contains_themes"] == EvaluationStatus.PASSED
    assert statuses["contains_raw_insight_summary"] == EvaluationStatus.PASSED
    assert statuses["contains_prompt_metadata"] == EvaluationStatus.PASSED
    assert statuses["contains_model_metadata"] == EvaluationStatus.PASSED
    assert statuses["contains_provider_metadata"] == EvaluationStatus.PASSED
    assert statuses["contains_usage_metadata"] == EvaluationStatus.PASSED


def test_missing_artifact_produces_failed_artifact_exists_check(tmp_path: Path) -> None:
    insights_path = tmp_path / "missing_review_insights.json"

    report = evaluate_review_insights_json(insights_path=insights_path)

    artifact_exists_check = _find_check(report.checks, "artifact_exists")
    assert artifact_exists_check.status == EvaluationStatus.FAILED
    assert artifact_exists_check.severity == EvaluationSeverity.ERROR


def test_empty_artifact_produces_failed_artifact_non_empty_check(tmp_path: Path) -> None:
    insights_path = tmp_path / "review_insights.json"
    insights_path.write_text("", encoding="utf-8")

    report = evaluate_review_insights_json(insights_path=insights_path)

    non_empty_check = _find_check(report.checks, "artifact_non_empty")
    assert non_empty_check.status == EvaluationStatus.FAILED
    assert non_empty_check.severity == EvaluationSeverity.ERROR


def test_invalid_json_produces_failed_valid_json_check(tmp_path: Path) -> None:
    insights_path = tmp_path / "review_insights.json"
    insights_path.write_text("{not valid json", encoding="utf-8")

    report = evaluate_review_insights_json(insights_path=insights_path)

    valid_json_check = _find_check(report.checks, "valid_json")
    assert valid_json_check.status == EvaluationStatus.FAILED
    assert valid_json_check.severity == EvaluationSeverity.ERROR


def test_schema_invalid_json_produces_failed_schema_check(tmp_path: Path) -> None:
    insights_path = tmp_path / "review_insights.json"
    insights_path.write_text(json.dumps({"not_a_real_field": "value"}), encoding="utf-8")

    report = evaluate_review_insights_json(insights_path=insights_path)

    schema_check = _find_check(report.checks, "valid_review_insight_result_schema")
    assert schema_check.status == EvaluationStatus.FAILED
    assert schema_check.severity == EvaluationSeverity.ERROR


def test_missing_themes_produces_failed_warning_contains_themes(tmp_path: Path) -> None:
    insights_path = tmp_path / "review_insights.json"
    write_review_insights_json(
        result=_extraction_result(themes=[]),
        output_path=insights_path,
    )

    report = evaluate_review_insights_json(insights_path=insights_path)

    themes_check = _find_check(report.checks, "contains_themes")
    assert themes_check.status == EvaluationStatus.FAILED
    assert themes_check.severity == EvaluationSeverity.WARNING


def test_missing_usage_metadata_produces_warning_not_error(tmp_path: Path) -> None:
    insights_path = tmp_path / "review_insights.json"
    write_review_insights_json(
        result=_extraction_result(),
        output_path=insights_path,
    )

    report = evaluate_review_insights_json(insights_path=insights_path)

    usage_check = _find_check(report.checks, "contains_usage_metadata")
    assert usage_check.status == EvaluationStatus.FAILED
    assert usage_check.severity == EvaluationSeverity.WARNING


def test_usage_metadata_present_passes(tmp_path: Path) -> None:
    insights_path = tmp_path / "review_insights.json"
    write_review_insights_json(
        result=_extraction_result(
            input_tokens=10,
            output_tokens=20,
            total_tokens=30,
            estimated_cost_usd=Decimal("0.001"),
        ),
        output_path=insights_path,
    )

    report = evaluate_review_insights_json(insights_path=insights_path)

    usage_check = _find_check(report.checks, "contains_usage_metadata")
    assert usage_check.status == EvaluationStatus.PASSED


def test_evaluator_does_not_call_model_providers(tmp_path: Path) -> None:
    insights_path, _ = _write_valid_insights(tmp_path)

    report = evaluate_review_insights_json(insights_path=insights_path)

    assert report.checks


def test_report_json_serialization_uses_enum_string_values(tmp_path: Path) -> None:
    insights_path, run_id = _write_valid_insights(tmp_path)

    report = evaluate_review_insights_json(insights_path=insights_path, run_id=run_id)
    data = json.loads(report.model_dump_json())

    for check in data["checks"]:
        assert check["status"] in {"passed", "failed", "warning", "skipped"}
        assert check["severity"] in {"info", "warning", "error"}


# --- helpers ---


def _write_valid_insights(tmp_path: Path) -> tuple[Path, UUID]:
    run_id = uuid4()
    insights_path = tmp_path / "review_insights.json"
    write_review_insights_json(
        result=_extraction_result(
            run_id=run_id,
            themes=[
                ReviewInsightTheme(
                    name="location",
                    sentiment="positive",
                    evidence_count=3,
                    summary="Guests value the central location.",
                )
            ],
            input_tokens=10,
            output_tokens=20,
            total_tokens=30,
            estimated_cost_usd=Decimal("0.001"),
        ),
        output_path=insights_path,
    )
    return insights_path, run_id


def _extraction_result(
    *,
    run_id: UUID | None = None,
    themes: list[ReviewInsightTheme] | None = None,
    input_tokens: int | None = None,
    output_tokens: int | None = None,
    total_tokens: int | None = None,
    estimated_cost_usd: Decimal | None = None,
) -> ReviewInsightExtractionResult:
    return ReviewInsightExtractionResult(
        run_id=run_id if run_id is not None else uuid4(),
        provider=ModelProvider.FAKE,
        model_name="fake-model",
        prompt_name=DEFAULT_REVIEW_INSIGHT_PROMPT_NAME,
        prompt_version=DEFAULT_REVIEW_INSIGHT_PROMPT_VERSION,
        themes=themes if themes is not None else [],
        raw_insight_summary="Location and cleanliness dominate guest feedback.",
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        total_tokens=total_tokens,
        estimated_cost_usd=estimated_cost_usd,
    )


def _find_check(
    checks: list[EvaluationCheckResult],
    name: str,
) -> EvaluationCheckResult:
    for check in checks:
        if check.check_name == name:
            return check
    raise AssertionError(f"check {name} not found")
