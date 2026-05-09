from decimal import Decimal
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

import pytest

from daedalus.domains.readysetrentables_reviews.theme_summary_artifacts import (
    write_review_theme_summary_markdown,
)
from daedalus.domains.readysetrentables_reviews.theme_summary_evaluator import (
    EVALUATOR_NAME,
    EVALUATOR_VERSION,
    TARGET_TYPE,
    evaluate_review_theme_summary_markdown,
)
from daedalus.domains.readysetrentables_reviews.theme_summary_models import (
    DEFAULT_REVIEW_THEME_PROMPT_NAME,
    DEFAULT_REVIEW_THEME_PROMPT_VERSION,
    ReviewThemeSummaryResult,
)
from daedalus.evaluation import EvaluationCheckResult, EvaluationSeverity, EvaluationStatus
from daedalus.model_clients import FakeModelClient, OllamaModelClient
from daedalus.model_clients.types import ModelProvider


def test_valid_review_theme_summary_markdown_produces_evaluation_report(
    tmp_path: Path,
) -> None:
    summary_path, run_id = _write_valid_summary(tmp_path)

    report = evaluate_review_theme_summary_markdown(
        summary_path=summary_path,
        run_id=run_id,
    )

    assert report.artifact_path == summary_path
    assert report.checks


def test_report_target_name_is_file_name(tmp_path: Path) -> None:
    summary_path, run_id = _write_valid_summary(tmp_path)

    report = evaluate_review_theme_summary_markdown(
        summary_path=summary_path,
        run_id=run_id,
    )

    assert report.target_name == "review_theme_summary.md"


def test_report_target_type_is_review_theme_summary(tmp_path: Path) -> None:
    summary_path, run_id = _write_valid_summary(tmp_path)

    report = evaluate_review_theme_summary_markdown(
        summary_path=summary_path,
        run_id=run_id,
    )

    assert report.target_type == TARGET_TYPE


def test_report_evaluator_identity_is_set(tmp_path: Path) -> None:
    summary_path, run_id = _write_valid_summary(tmp_path)

    report = evaluate_review_theme_summary_markdown(
        summary_path=summary_path,
        run_id=run_id,
    )

    assert report.evaluator_name == EVALUATOR_NAME
    assert report.evaluator_version == EVALUATOR_VERSION


def test_report_run_id_is_preserved_when_provided(tmp_path: Path) -> None:
    summary_path, run_id = _write_valid_summary(tmp_path)

    report = evaluate_review_theme_summary_markdown(
        summary_path=summary_path,
        run_id=run_id,
    )

    assert report.run_id == run_id


def test_valid_artifact_passes_required_checks(tmp_path: Path) -> None:
    summary_path, run_id = _write_valid_summary(tmp_path)

    report = evaluate_review_theme_summary_markdown(
        summary_path=summary_path,
        run_id=run_id,
    )

    assert {check.status for check in report.checks} == {EvaluationStatus.PASSED}


def test_missing_artifact_produces_failed_artifact_exists_check(tmp_path: Path) -> None:
    summary_path = tmp_path / "missing_review_theme_summary.md"

    report = evaluate_review_theme_summary_markdown(summary_path=summary_path)

    check = _check_by_name(report.checks, "artifact_exists")
    assert check.status == EvaluationStatus.FAILED
    assert check.severity == EvaluationSeverity.ERROR


def test_empty_artifact_produces_failed_artifact_non_empty_check(tmp_path: Path) -> None:
    summary_path = tmp_path / "review_theme_summary.md"
    summary_path.write_text("", encoding="utf-8")

    report = evaluate_review_theme_summary_markdown(summary_path=summary_path)

    check = _check_by_name(report.checks, "artifact_non_empty")
    assert check.status == EvaluationStatus.FAILED
    assert check.severity == EvaluationSeverity.ERROR


def test_missing_title_produces_failed_contains_title_check(tmp_path: Path) -> None:
    summary_path, run_id = _write_valid_summary(tmp_path)
    _replace_text(summary_path, "# ReadySetRentables Review Theme Summary\n\n", "")

    report = evaluate_review_theme_summary_markdown(
        summary_path=summary_path,
        run_id=run_id,
    )

    check = _check_by_name(report.checks, "contains_title")
    assert check.status == EvaluationStatus.FAILED
    assert check.severity == EvaluationSeverity.WARNING


def test_missing_run_id_produces_failed_contains_run_id_check_when_run_id_provided(
    tmp_path: Path,
) -> None:
    summary_path, run_id = _write_valid_summary(tmp_path)
    _replace_text(summary_path, str(run_id), str(uuid4()))

    report = evaluate_review_theme_summary_markdown(
        summary_path=summary_path,
        run_id=run_id,
    )

    check = _check_by_name(report.checks, "contains_run_id")
    assert check.status == EvaluationStatus.FAILED
    assert check.severity == EvaluationSeverity.WARNING


def test_missing_prompt_metadata_produces_failed_contains_prompt_metadata_check(
    tmp_path: Path,
) -> None:
    summary_path, run_id = _write_valid_summary(tmp_path)
    _replace_text(summary_path, f"- Prompt: `{DEFAULT_REVIEW_THEME_PROMPT_NAME}`\n", "")

    report = evaluate_review_theme_summary_markdown(
        summary_path=summary_path,
        run_id=run_id,
    )

    check = _check_by_name(report.checks, "contains_prompt_metadata")
    assert check.status == EvaluationStatus.FAILED
    assert check.severity == EvaluationSeverity.WARNING


def test_missing_model_metadata_produces_failed_contains_model_metadata_check(
    tmp_path: Path,
) -> None:
    summary_path, run_id = _write_valid_summary(tmp_path)
    _replace_text(summary_path, "- Model provider: `fake`\n", "")

    report = evaluate_review_theme_summary_markdown(
        summary_path=summary_path,
        run_id=run_id,
    )

    check = _check_by_name(report.checks, "contains_model_metadata")
    assert check.status == EvaluationStatus.FAILED
    assert check.severity == EvaluationSeverity.WARNING


def test_missing_summary_section_produces_failed_contains_summary_section_check(
    tmp_path: Path,
) -> None:
    summary_path, run_id = _write_valid_summary(tmp_path)
    _replace_text(summary_path, "## Summary", "## Overview")

    report = evaluate_review_theme_summary_markdown(
        summary_path=summary_path,
        run_id=run_id,
    )

    check = _check_by_name(report.checks, "contains_summary_section")
    assert check.status == EvaluationStatus.FAILED
    assert check.severity == EvaluationSeverity.ERROR


def test_empty_summary_section_produces_failed_summary_section_non_empty_check(
    tmp_path: Path,
) -> None:
    summary_path = tmp_path / "review_theme_summary.md"
    run_id = uuid4()
    summary_path.write_text(_summary_markdown(run_id=run_id, summary_text=""), encoding="utf-8")

    report = evaluate_review_theme_summary_markdown(
        summary_path=summary_path,
        run_id=run_id,
    )

    check = _check_by_name(report.checks, "summary_section_non_empty")
    assert check.status == EvaluationStatus.FAILED
    assert check.severity == EvaluationSeverity.ERROR


def test_placeholder_only_output_produces_failed_placeholder_only_output_check(
    tmp_path: Path,
) -> None:
    summary_path = tmp_path / "review_theme_summary.md"
    run_id = uuid4()
    summary_path.write_text(
        _summary_markdown(run_id=run_id, summary_text="fake model response"),
        encoding="utf-8",
    )

    report = evaluate_review_theme_summary_markdown(
        summary_path=summary_path,
        run_id=run_id,
    )

    check = _check_by_name(report.checks, "placeholder_only_output")
    assert check.status == EvaluationStatus.FAILED
    assert check.severity == EvaluationSeverity.ERROR


def test_evaluator_does_not_require_live_ollama(tmp_path: Path) -> None:
    summary_path, run_id = _write_valid_summary(tmp_path)

    report = evaluate_review_theme_summary_markdown(
        summary_path=summary_path,
        run_id=run_id,
    )

    assert report.passed is True


def test_evaluator_does_not_call_any_model_provider(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    summary_path, run_id = _write_valid_summary(tmp_path)

    def fail_if_called(*_args: Any, **_kwargs: Any) -> None:
        raise AssertionError("model provider should not be called")

    monkeypatch.setattr(FakeModelClient, "complete", fail_if_called)
    monkeypatch.setattr(OllamaModelClient, "complete", fail_if_called)

    report = evaluate_review_theme_summary_markdown(
        summary_path=summary_path,
        run_id=run_id,
    )

    assert report.passed is True


def _write_valid_summary(tmp_path: Path) -> tuple[Path, UUID]:
    run_id = uuid4()
    output_path = tmp_path / "review_theme_summary.md"
    result = ReviewThemeSummaryResult(
        run_id=run_id,
        summary_text="Guests praise the clear check-in details and convenient location.",
        prompt_name=DEFAULT_REVIEW_THEME_PROMPT_NAME,
        prompt_version=DEFAULT_REVIEW_THEME_PROMPT_VERSION,
        model_provider=ModelProvider.FAKE,
        model_name="fake-model",
        input_tokens=10,
        output_tokens=20,
        total_tokens=30,
        estimated_cost_usd=Decimal("0"),
    )
    write_review_theme_summary_markdown(result=result, output_path=output_path)
    return output_path, run_id


def _summary_markdown(
    *,
    run_id: UUID,
    summary_text: str,
) -> str:
    return "\n".join(
        [
            "# ReadySetRentables Review Theme Summary",
            "",
            f"- Run ID: `{run_id}`",
            f"- Prompt: `{DEFAULT_REVIEW_THEME_PROMPT_NAME}`",
            f"- Prompt version: `{DEFAULT_REVIEW_THEME_PROMPT_VERSION}`",
            "- Model provider: `fake`",
            "- Model name: `fake-model`",
            "",
            "## Summary",
            "",
            summary_text,
            "",
            "## Token And Cost Metadata",
            "",
            "- Input tokens: 10",
            "- Output tokens: 20",
            "- Total tokens: 30",
            "- Estimated cost USD: 0",
            "",
        ]
    )


def _replace_text(path: Path, old_text: str, new_text: str) -> None:
    path.write_text(path.read_text(encoding="utf-8").replace(old_text, new_text), encoding="utf-8")


def _check_by_name(
    checks: list[EvaluationCheckResult],
    check_name: str,
) -> EvaluationCheckResult:
    return next(check for check in checks if check.check_name == check_name)
