import json
from decimal import Decimal
from pathlib import Path
from uuid import UUID, uuid4

from daedalus.domains.readysetrentables_reviews.neighborhood_profile_artifacts import (
    write_neighborhood_profile_json,
    write_neighborhood_profile_markdown,
)
from daedalus.domains.readysetrentables_reviews.neighborhood_profile_evaluator import (
    JSON_EVALUATOR_NAME,
    JSON_EVALUATOR_VERSION,
    JSON_TARGET_TYPE,
    MARKDOWN_EVALUATOR_NAME,
    MARKDOWN_EVALUATOR_VERSION,
    MARKDOWN_TARGET_TYPE,
    evaluate_neighborhood_profile_json,
    evaluate_neighborhood_profile_markdown,
)
from daedalus.domains.readysetrentables_reviews.neighborhood_profile_models import (
    DEFAULT_NEIGHBORHOOD_PROFILE_PROMPT_NAME,
    DEFAULT_NEIGHBORHOOD_PROFILE_PROMPT_VERSION,
    NeighborhoodProfileResult,
    NeighborhoodProfileSection,
)
from daedalus.evaluation import EvaluationCheckResult, EvaluationSeverity, EvaluationStatus
from daedalus.model_clients.types import ModelProvider


# --- Markdown evaluator tests ---


def test_valid_neighborhood_profile_markdown_produces_evaluation_report(tmp_path: Path) -> None:
    profile_path, run_id = _write_valid_markdown(tmp_path)

    report = evaluate_neighborhood_profile_markdown(profile_path=profile_path, run_id=run_id)

    assert report.artifact_path == profile_path
    assert report.checks


def test_markdown_report_target_name_is_file_name(tmp_path: Path) -> None:
    profile_path, run_id = _write_valid_markdown(tmp_path)

    report = evaluate_neighborhood_profile_markdown(profile_path=profile_path, run_id=run_id)

    assert report.target_name == "neighborhood_profile.md"


def test_markdown_report_target_type_is_neighborhood_profile_markdown(tmp_path: Path) -> None:
    profile_path, run_id = _write_valid_markdown(tmp_path)

    report = evaluate_neighborhood_profile_markdown(profile_path=profile_path, run_id=run_id)

    assert report.target_type == MARKDOWN_TARGET_TYPE


def test_markdown_report_evaluator_identity_is_set(tmp_path: Path) -> None:
    profile_path, run_id = _write_valid_markdown(tmp_path)

    report = evaluate_neighborhood_profile_markdown(profile_path=profile_path, run_id=run_id)

    assert report.evaluator_name == MARKDOWN_EVALUATOR_NAME
    assert report.evaluator_version == MARKDOWN_EVALUATOR_VERSION


def test_markdown_report_run_id_is_preserved_when_provided(tmp_path: Path) -> None:
    profile_path, run_id = _write_valid_markdown(tmp_path)

    report = evaluate_neighborhood_profile_markdown(profile_path=profile_path, run_id=run_id)

    assert report.run_id == run_id


def test_markdown_valid_artifact_passes_required_checks(tmp_path: Path) -> None:
    profile_path, run_id = _write_valid_markdown(tmp_path)

    report = evaluate_neighborhood_profile_markdown(profile_path=profile_path, run_id=run_id)

    statuses = {check.check_name: check.status for check in report.checks}
    assert statuses["artifact_exists"] == EvaluationStatus.PASSED
    assert statuses["artifact_non_empty"] == EvaluationStatus.PASSED
    assert statuses["contains_title"] == EvaluationStatus.PASSED
    assert statuses["contains_metadata_header"] == EvaluationStatus.PASSED
    assert statuses["contains_summary_or_intro"] == EvaluationStatus.PASSED
    assert statuses["contains_risks_or_caveats"] == EvaluationStatus.PASSED
    assert statuses["placeholder_only_output"] == EvaluationStatus.PASSED


def test_markdown_missing_artifact_produces_failed_artifact_exists_check(tmp_path: Path) -> None:
    profile_path = tmp_path / "missing.md"

    report = evaluate_neighborhood_profile_markdown(profile_path=profile_path)

    check = _find_check(report.checks, "artifact_exists")
    assert check.status == EvaluationStatus.FAILED
    assert check.severity == EvaluationSeverity.ERROR


def test_markdown_empty_artifact_produces_failed_artifact_non_empty_check(tmp_path: Path) -> None:
    profile_path = tmp_path / "neighborhood_profile.md"
    profile_path.write_text("", encoding="utf-8")

    report = evaluate_neighborhood_profile_markdown(profile_path=profile_path)

    check = _find_check(report.checks, "artifact_non_empty")
    assert check.status == EvaluationStatus.FAILED
    assert check.severity == EvaluationSeverity.ERROR


def test_markdown_missing_title_produces_failed_contains_title_check(tmp_path: Path) -> None:
    profile_path = tmp_path / "neighborhood_profile.md"
    profile_path.write_text(
        "<!-- Neighborhood Profile Metadata -->\n<!-- run_id: x -->\n\nbody without title\n",
        encoding="utf-8",
    )

    report = evaluate_neighborhood_profile_markdown(profile_path=profile_path)

    check = _find_check(report.checks, "contains_title")
    assert check.status == EvaluationStatus.FAILED
    assert check.severity == EvaluationSeverity.ERROR


def test_markdown_missing_metadata_header_produces_failed_warning(tmp_path: Path) -> None:
    profile_path = tmp_path / "neighborhood_profile.md"
    profile_path.write_text(
        "# East Side Austin\n\nA vibrant neighborhood with risks worth noting.\n",
        encoding="utf-8",
    )

    report = evaluate_neighborhood_profile_markdown(profile_path=profile_path)

    check = _find_check(report.checks, "contains_metadata_header")
    assert check.status == EvaluationStatus.FAILED
    assert check.severity == EvaluationSeverity.WARNING


def test_markdown_placeholder_only_output_produces_failed_check(tmp_path: Path) -> None:
    profile_path = tmp_path / "neighborhood_profile.md"
    profile_path.write_text(
        "<!-- Neighborhood Profile Metadata -->\n<!-- run_id: x -->\n\nTODO\n",
        encoding="utf-8",
    )

    report = evaluate_neighborhood_profile_markdown(profile_path=profile_path)

    check = _find_check(report.checks, "placeholder_only_output")
    assert check.status == EvaluationStatus.FAILED
    assert check.severity == EvaluationSeverity.ERROR


def test_markdown_evaluator_does_not_call_model_providers(tmp_path: Path) -> None:
    profile_path, _ = _write_valid_markdown(tmp_path)

    report = evaluate_neighborhood_profile_markdown(profile_path=profile_path)

    assert report.checks


# --- JSON evaluator tests ---


def test_valid_neighborhood_profile_json_produces_evaluation_report(tmp_path: Path) -> None:
    profile_path, run_id = _write_valid_json(tmp_path)

    report = evaluate_neighborhood_profile_json(profile_path=profile_path, run_id=run_id)

    assert report.artifact_path == profile_path
    assert report.checks


def test_json_report_target_name_is_file_name(tmp_path: Path) -> None:
    profile_path, run_id = _write_valid_json(tmp_path)

    report = evaluate_neighborhood_profile_json(profile_path=profile_path, run_id=run_id)

    assert report.target_name == "neighborhood_profile.json"


def test_json_report_target_type_is_neighborhood_profile_json(tmp_path: Path) -> None:
    profile_path, run_id = _write_valid_json(tmp_path)

    report = evaluate_neighborhood_profile_json(profile_path=profile_path, run_id=run_id)

    assert report.target_type == JSON_TARGET_TYPE


def test_json_report_evaluator_identity_is_set(tmp_path: Path) -> None:
    profile_path, run_id = _write_valid_json(tmp_path)

    report = evaluate_neighborhood_profile_json(profile_path=profile_path, run_id=run_id)

    assert report.evaluator_name == JSON_EVALUATOR_NAME
    assert report.evaluator_version == JSON_EVALUATOR_VERSION


def test_json_report_run_id_is_preserved_when_provided(tmp_path: Path) -> None:
    profile_path, run_id = _write_valid_json(tmp_path)

    report = evaluate_neighborhood_profile_json(profile_path=profile_path, run_id=run_id)

    assert report.run_id == run_id


def test_json_valid_artifact_passes_required_checks(tmp_path: Path) -> None:
    profile_path, run_id = _write_valid_json(tmp_path)

    report = evaluate_neighborhood_profile_json(profile_path=profile_path, run_id=run_id)

    statuses = {check.check_name: check.status for check in report.checks}
    assert statuses["artifact_exists"] == EvaluationStatus.PASSED
    assert statuses["artifact_non_empty"] == EvaluationStatus.PASSED
    assert statuses["valid_json"] == EvaluationStatus.PASSED
    assert statuses["valid_neighborhood_profile_result_schema"] == EvaluationStatus.PASSED
    assert statuses["contains_sections"] == EvaluationStatus.PASSED
    assert statuses["contains_summary"] == EvaluationStatus.PASSED
    assert statuses["contains_prompt_metadata"] == EvaluationStatus.PASSED
    assert statuses["contains_model_metadata"] == EvaluationStatus.PASSED
    assert statuses["contains_provider_metadata"] == EvaluationStatus.PASSED
    assert statuses["contains_usage_metadata"] == EvaluationStatus.PASSED


def test_json_missing_artifact_produces_failed_artifact_exists_check(tmp_path: Path) -> None:
    profile_path = tmp_path / "missing.json"

    report = evaluate_neighborhood_profile_json(profile_path=profile_path)

    check = _find_check(report.checks, "artifact_exists")
    assert check.status == EvaluationStatus.FAILED
    assert check.severity == EvaluationSeverity.ERROR


def test_json_empty_artifact_produces_failed_artifact_non_empty_check(tmp_path: Path) -> None:
    profile_path = tmp_path / "neighborhood_profile.json"
    profile_path.write_text("", encoding="utf-8")

    report = evaluate_neighborhood_profile_json(profile_path=profile_path)

    check = _find_check(report.checks, "artifact_non_empty")
    assert check.status == EvaluationStatus.FAILED
    assert check.severity == EvaluationSeverity.ERROR


def test_json_invalid_json_produces_failed_valid_json_check(tmp_path: Path) -> None:
    profile_path = tmp_path / "neighborhood_profile.json"
    profile_path.write_text("{not valid json", encoding="utf-8")

    report = evaluate_neighborhood_profile_json(profile_path=profile_path)

    check = _find_check(report.checks, "valid_json")
    assert check.status == EvaluationStatus.FAILED
    assert check.severity == EvaluationSeverity.ERROR


def test_json_schema_invalid_produces_failed_schema_check(tmp_path: Path) -> None:
    profile_path = tmp_path / "neighborhood_profile.json"
    profile_path.write_text(json.dumps({"not_a_real_field": "value"}), encoding="utf-8")

    report = evaluate_neighborhood_profile_json(profile_path=profile_path)

    check = _find_check(report.checks, "valid_neighborhood_profile_result_schema")
    assert check.status == EvaluationStatus.FAILED
    assert check.severity == EvaluationSeverity.ERROR


def test_json_missing_sections_produces_failed_warning(tmp_path: Path) -> None:
    profile_path = tmp_path / "neighborhood_profile.json"
    write_neighborhood_profile_json(
        result=_profile_result(sections=[]),
        output_path=profile_path,
    )

    report = evaluate_neighborhood_profile_json(profile_path=profile_path)

    check = _find_check(report.checks, "contains_sections")
    assert check.status == EvaluationStatus.FAILED
    assert check.severity == EvaluationSeverity.WARNING


def test_json_missing_usage_metadata_produces_warning_not_error(tmp_path: Path) -> None:
    profile_path = tmp_path / "neighborhood_profile.json"
    write_neighborhood_profile_json(
        result=_profile_result(),
        output_path=profile_path,
    )

    report = evaluate_neighborhood_profile_json(profile_path=profile_path)

    check = _find_check(report.checks, "contains_usage_metadata")
    assert check.status == EvaluationStatus.FAILED
    assert check.severity == EvaluationSeverity.WARNING


def test_json_evaluator_does_not_call_model_providers(tmp_path: Path) -> None:
    profile_path, _ = _write_valid_json(tmp_path)

    report = evaluate_neighborhood_profile_json(profile_path=profile_path)

    assert report.checks


def test_json_report_serialization_uses_enum_string_values(tmp_path: Path) -> None:
    profile_path, run_id = _write_valid_json(tmp_path)

    report = evaluate_neighborhood_profile_json(profile_path=profile_path, run_id=run_id)
    data = json.loads(report.model_dump_json())

    for check in data["checks"]:
        assert check["status"] in {"passed", "failed", "warning", "skipped"}
        assert check["severity"] in {"info", "warning", "error"}


# --- helpers ---


def _write_valid_markdown(tmp_path: Path) -> tuple[Path, UUID]:
    run_id = uuid4()
    profile_path = tmp_path / "neighborhood_profile.md"
    write_neighborhood_profile_markdown(
        result=_profile_result(
            run_id=run_id,
            markdown=(
                "# East Side Austin\n\n"
                "A vibrant neighborhood with strong guest appeal.\n\n"
                "## Risks\n\n"
                "- Limited parking on weekends.\n"
            ),
        ),
        output_path=profile_path,
    )
    return profile_path, run_id


def _write_valid_json(tmp_path: Path) -> tuple[Path, UUID]:
    run_id = uuid4()
    profile_path = tmp_path / "neighborhood_profile.json"
    write_neighborhood_profile_json(
        result=_profile_result(
            run_id=run_id,
            sections=[
                NeighborhoodProfileSection(
                    heading="Location",
                    body="Walkable access to dining.",
                )
            ],
            input_tokens=10,
            output_tokens=20,
            total_tokens=30,
            estimated_cost_usd=Decimal("0.001"),
        ),
        output_path=profile_path,
    )
    return profile_path, run_id


def _profile_result(
    *,
    run_id: UUID | None = None,
    sections: list[NeighborhoodProfileSection] | None = None,
    markdown: str = "# East Side Austin\n\nA vibrant neighborhood with risk considerations.\n",
    input_tokens: int | None = None,
    output_tokens: int | None = None,
    total_tokens: int | None = None,
    estimated_cost_usd: Decimal | None = None,
) -> NeighborhoodProfileResult:
    return NeighborhoodProfileResult(
        run_id=run_id if run_id is not None else uuid4(),
        provider=ModelProvider.FAKE,
        model_name="fake-model",
        prompt_name=DEFAULT_NEIGHBORHOOD_PROFILE_PROMPT_NAME,
        prompt_version=DEFAULT_NEIGHBORHOOD_PROFILE_PROMPT_VERSION,
        market_name="Austin",
        neighborhood_name="East Side",
        profile_title="East Side Austin Neighborhood Profile",
        summary="A vibrant neighborhood with strong guest appeal.",
        sections=sections if sections is not None else [],
        markdown=markdown,
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
