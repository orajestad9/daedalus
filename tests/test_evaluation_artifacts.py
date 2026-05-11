import json
from pathlib import Path
from typing import Any, cast
from uuid import uuid4

from daedalus.evaluation import (
    EvaluationCheckResult,
    EvaluationComparisonItem,
    EvaluationComparisonReport,
    EvaluationComparisonStatus,
    EvaluationReport,
    EvaluationSeverity,
    EvaluationStatus,
    write_evaluation_comparison_report_json,
    write_evaluation_comparison_report_markdown,
    write_evaluation_report_json,
    write_evaluation_report_markdown,
)


def test_write_evaluation_report_json_writes_artifact(tmp_path: Path) -> None:
    output_path = tmp_path / "evaluation.json"

    write_evaluation_report_json(report=_report(), output_path=output_path)

    assert output_path.is_file()


def test_write_evaluation_report_json_creates_parent_directory(tmp_path: Path) -> None:
    output_path = tmp_path / "nested" / "reports" / "evaluation.json"

    write_evaluation_report_json(report=_report(), output_path=output_path)

    assert output_path.parent.is_dir()


def test_write_evaluation_report_json_returns_output_path(tmp_path: Path) -> None:
    output_path = tmp_path / "evaluation.json"

    returned_path = write_evaluation_report_json(report=_report(), output_path=output_path)

    assert returned_path == output_path


def test_write_evaluation_report_json_includes_report_id(tmp_path: Path) -> None:
    report = _report()
    output_path = tmp_path / "evaluation.json"

    write_evaluation_report_json(report=report, output_path=output_path)

    data = _read_json(output_path)
    assert data["report_id"] == str(report.report_id)


def test_write_evaluation_report_json_includes_enum_string_values(tmp_path: Path) -> None:
    output_path = tmp_path / "evaluation.json"

    write_evaluation_report_json(report=_report(), output_path=output_path)

    data = _read_json(output_path)
    assert data["checks"][0]["status"] == "passed"
    assert data["checks"][0]["severity"] == "info"


def test_write_evaluation_report_json_includes_checks(tmp_path: Path) -> None:
    output_path = tmp_path / "evaluation.json"

    write_evaluation_report_json(report=_report(), output_path=output_path)

    data = _read_json(output_path)
    assert data["checks"][0]["check_name"] == "artifact_exists"
    assert data["checks"][0]["message"] == "Artifact exists."


def test_write_evaluation_report_markdown_writes_artifact(tmp_path: Path) -> None:
    output_path = tmp_path / "evaluation.md"

    write_evaluation_report_markdown(report=_report(), output_path=output_path)

    assert output_path.is_file()


def test_write_evaluation_report_markdown_creates_parent_directory(tmp_path: Path) -> None:
    output_path = tmp_path / "nested" / "reports" / "evaluation.md"

    write_evaluation_report_markdown(report=_report(), output_path=output_path)

    assert output_path.parent.is_dir()


def test_write_evaluation_report_markdown_returns_output_path(tmp_path: Path) -> None:
    output_path = tmp_path / "evaluation.md"

    returned_path = write_evaluation_report_markdown(report=_report(), output_path=output_path)

    assert returned_path == output_path


def test_write_evaluation_report_markdown_includes_target_name(tmp_path: Path) -> None:
    output_path = tmp_path / "evaluation.md"

    write_evaluation_report_markdown(report=_report(), output_path=output_path)

    markdown = output_path.read_text(encoding="utf-8")
    assert "Target name: `review_theme_summary`" in markdown


def test_write_evaluation_report_markdown_includes_target_type(tmp_path: Path) -> None:
    output_path = tmp_path / "evaluation.md"

    write_evaluation_report_markdown(report=_report(), output_path=output_path)

    markdown = output_path.read_text(encoding="utf-8")
    assert "Target type: `markdown_artifact`" in markdown


def test_write_evaluation_report_markdown_includes_evaluator_identity(
    tmp_path: Path,
) -> None:
    output_path = tmp_path / "evaluation.md"

    write_evaluation_report_markdown(report=_report(), output_path=output_path)

    markdown = output_path.read_text(encoding="utf-8")
    assert "Evaluator name: `generic_structure`" in markdown
    assert "Evaluator version: `v0`" in markdown


def test_write_evaluation_report_markdown_includes_passed(tmp_path: Path) -> None:
    output_path = tmp_path / "evaluation.md"

    write_evaluation_report_markdown(report=_report(), output_path=output_path)

    markdown = output_path.read_text(encoding="utf-8")
    assert "Passed: `True`" in markdown


def test_write_evaluation_report_markdown_includes_counts(tmp_path: Path) -> None:
    output_path = tmp_path / "evaluation.md"
    report = _report(
        checks=[
            _check_result(status=EvaluationStatus.WARNING, severity=EvaluationSeverity.WARNING),
            _check_result(status=EvaluationStatus.FAILED, severity=EvaluationSeverity.ERROR),
        ]
    )

    write_evaluation_report_markdown(report=report, output_path=output_path)

    markdown = output_path.read_text(encoding="utf-8")
    assert "Failed count: `1`" in markdown
    assert "Warning count: `1`" in markdown
    assert "Error count: `1`" in markdown


def test_write_evaluation_report_markdown_includes_check_details(
    tmp_path: Path,
) -> None:
    output_path = tmp_path / "evaluation.md"

    write_evaluation_report_markdown(report=_report(), output_path=output_path)

    markdown = output_path.read_text(encoding="utf-8")
    assert "### artifact_exists" in markdown
    assert "Status: `passed`" in markdown
    assert "Severity: `info`" in markdown
    assert "Message: Artifact exists." in markdown
    assert "`path`: `artifacts/result.md`" in markdown


def test_write_evaluation_report_markdown_includes_no_checks_message(
    tmp_path: Path,
) -> None:
    output_path = tmp_path / "evaluation.md"

    write_evaluation_report_markdown(report=_report(checks=[]), output_path=output_path)

    markdown = output_path.read_text(encoding="utf-8")
    assert "No evaluation checks were recorded." in markdown


def _check_result(
    *,
    status: EvaluationStatus = EvaluationStatus.PASSED,
    severity: EvaluationSeverity = EvaluationSeverity.INFO,
) -> EvaluationCheckResult:
    return EvaluationCheckResult(
        check_name="artifact_exists",
        status=status,
        severity=severity,
        message="Artifact exists.",
        details={"path": "artifacts/result.md"},
    )


def _report(
    *,
    checks: list[EvaluationCheckResult] | None = None,
) -> EvaluationReport:
    return EvaluationReport(
        run_id=uuid4(),
        artifact_path=Path("artifacts/result.md"),
        target_name="review_theme_summary",
        target_type="markdown_artifact",
        evaluator_name="generic_structure",
        evaluator_version="v0",
        checks=[_check_result()] if checks is None else checks,
    )


def _read_json(path: Path) -> dict[str, Any]:
    return cast(dict[str, Any], json.loads(path.read_text(encoding="utf-8")))


# ---------------------------------------------------------------------------
# write_evaluation_comparison_report_json
# ---------------------------------------------------------------------------


def test_write_evaluation_comparison_report_json_writes_artifact(tmp_path: Path) -> None:
    output_path = tmp_path / "comparison.json"

    write_evaluation_comparison_report_json(report=_comparison_report(), output_path=output_path)

    assert output_path.is_file()


def test_write_evaluation_comparison_report_json_creates_parent_directory(
    tmp_path: Path,
) -> None:
    output_path = tmp_path / "nested" / "reports" / "comparison.json"

    write_evaluation_comparison_report_json(report=_comparison_report(), output_path=output_path)

    assert output_path.parent.is_dir()


def test_write_evaluation_comparison_report_json_returns_output_path(tmp_path: Path) -> None:
    output_path = tmp_path / "comparison.json"

    returned_path = write_evaluation_comparison_report_json(
        report=_comparison_report(), output_path=output_path
    )

    assert returned_path == output_path


def test_write_evaluation_comparison_report_json_includes_comparison_report_id(
    tmp_path: Path,
) -> None:
    report = _comparison_report()
    output_path = tmp_path / "comparison.json"

    write_evaluation_comparison_report_json(report=report, output_path=output_path)

    data = _read_json(output_path)
    assert data["comparison_report_id"] == str(report.comparison_report_id)


def test_write_evaluation_comparison_report_json_includes_enum_string_values(
    tmp_path: Path,
) -> None:
    output_path = tmp_path / "comparison.json"

    write_evaluation_comparison_report_json(report=_comparison_report(), output_path=output_path)

    data = _read_json(output_path)
    assert data["comparisons"][0]["status"] == "improved"
    assert data["comparisons"][0]["severity"] == "info"


def test_write_evaluation_comparison_report_json_includes_comparisons(tmp_path: Path) -> None:
    output_path = tmp_path / "comparison.json"

    write_evaluation_comparison_report_json(report=_comparison_report(), output_path=output_path)

    data = _read_json(output_path)
    assert data["comparisons"][0]["comparison_name"] == "token_count"
    assert data["comparisons"][0]["message"] == "Token count decreased."


# ---------------------------------------------------------------------------
# write_evaluation_comparison_report_markdown
# ---------------------------------------------------------------------------


def test_write_evaluation_comparison_report_markdown_writes_artifact(tmp_path: Path) -> None:
    output_path = tmp_path / "comparison.md"

    write_evaluation_comparison_report_markdown(
        report=_comparison_report(), output_path=output_path
    )

    assert output_path.is_file()


def test_write_evaluation_comparison_report_markdown_creates_parent_directory(
    tmp_path: Path,
) -> None:
    output_path = tmp_path / "nested" / "reports" / "comparison.md"

    write_evaluation_comparison_report_markdown(
        report=_comparison_report(), output_path=output_path
    )

    assert output_path.parent.is_dir()


def test_write_evaluation_comparison_report_markdown_returns_output_path(
    tmp_path: Path,
) -> None:
    output_path = tmp_path / "comparison.md"

    returned_path = write_evaluation_comparison_report_markdown(
        report=_comparison_report(), output_path=output_path
    )

    assert returned_path == output_path


def test_write_evaluation_comparison_report_markdown_includes_target_name(
    tmp_path: Path,
) -> None:
    output_path = tmp_path / "comparison.md"

    write_evaluation_comparison_report_markdown(
        report=_comparison_report(), output_path=output_path
    )

    markdown = output_path.read_text(encoding="utf-8")
    assert "Target name: `review_theme_summary`" in markdown


def test_write_evaluation_comparison_report_markdown_includes_target_type(
    tmp_path: Path,
) -> None:
    output_path = tmp_path / "comparison.md"

    write_evaluation_comparison_report_markdown(
        report=_comparison_report(), output_path=output_path
    )

    markdown = output_path.read_text(encoding="utf-8")
    assert "Target type: `markdown_artifact`" in markdown


def test_write_evaluation_comparison_report_markdown_includes_comparator_identity(
    tmp_path: Path,
) -> None:
    output_path = tmp_path / "comparison.md"

    write_evaluation_comparison_report_markdown(
        report=_comparison_report(), output_path=output_path
    )

    markdown = output_path.read_text(encoding="utf-8")
    assert "Comparator name: `structure_comparator`" in markdown
    assert "Comparator version: `v0`" in markdown


def test_write_evaluation_comparison_report_markdown_includes_passed(tmp_path: Path) -> None:
    output_path = tmp_path / "comparison.md"

    write_evaluation_comparison_report_markdown(
        report=_comparison_report(), output_path=output_path
    )

    markdown = output_path.read_text(encoding="utf-8")
    assert "Passed: `True`" in markdown


def test_write_evaluation_comparison_report_markdown_includes_counts(tmp_path: Path) -> None:
    output_path = tmp_path / "comparison.md"
    report = _comparison_report(
        comparisons=[
            _comparison_item(status=EvaluationComparisonStatus.DIFFERENT),
            _comparison_item(status=EvaluationComparisonStatus.IMPROVED),
            _comparison_item(status=EvaluationComparisonStatus.REGRESSED),
            _comparison_item(status=EvaluationComparisonStatus.INCONCLUSIVE),
        ]
    )

    write_evaluation_comparison_report_markdown(report=report, output_path=output_path)

    markdown = output_path.read_text(encoding="utf-8")
    assert "Different count: `1`" in markdown
    assert "Improved count: `1`" in markdown
    assert "Regressed count: `1`" in markdown
    assert "Inconclusive count: `1`" in markdown


def test_write_evaluation_comparison_report_markdown_includes_comparison_details(
    tmp_path: Path,
) -> None:
    output_path = tmp_path / "comparison.md"

    write_evaluation_comparison_report_markdown(
        report=_comparison_report(), output_path=output_path
    )

    markdown = output_path.read_text(encoding="utf-8")
    assert "### token_count" in markdown
    assert "Status: `improved`" in markdown
    assert "Severity: `info`" in markdown
    assert "Message: Token count decreased." in markdown
    assert "Baseline value: `500`" in markdown
    assert "Candidate value: `300`" in markdown
    assert "`unit`: `tokens`" in markdown


def test_write_evaluation_comparison_report_markdown_includes_no_comparisons_message(
    tmp_path: Path,
) -> None:
    output_path = tmp_path / "comparison.md"

    write_evaluation_comparison_report_markdown(
        report=_comparison_report(comparisons=[]), output_path=output_path
    )

    markdown = output_path.read_text(encoding="utf-8")
    assert "No evaluation comparisons were recorded." in markdown


def _comparison_item(
    *,
    status: EvaluationComparisonStatus = EvaluationComparisonStatus.IMPROVED,
    severity: EvaluationSeverity = EvaluationSeverity.INFO,
) -> EvaluationComparisonItem:
    return EvaluationComparisonItem(
        comparison_name="token_count",
        status=status,
        severity=severity,
        message="Token count decreased.",
        baseline_value="500",
        candidate_value="300",
        details={"unit": "tokens"},
    )


def _comparison_report(
    *,
    comparisons: list[EvaluationComparisonItem] | None = None,
) -> EvaluationComparisonReport:
    return EvaluationComparisonReport(
        baseline_artifact_path=Path("artifacts/baseline.md"),
        candidate_artifact_path=Path("artifacts/candidate.md"),
        target_name="review_theme_summary",
        target_type="markdown_artifact",
        comparator_name="structure_comparator",
        comparator_version="v0",
        comparisons=[_comparison_item()] if comparisons is None else comparisons,
    )
