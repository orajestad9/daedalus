import json
from pathlib import Path
from typing import Any, cast
from uuid import UUID, uuid4

import pytest
from pydantic import ValidationError

from daedalus.evaluation import (
    EvaluationCheckResult,
    EvaluationReport,
    EvaluationSeverity,
    EvaluationStatus,
)


def test_evaluation_status_values() -> None:
    assert EvaluationStatus.PASSED.value == "passed"
    assert EvaluationStatus.FAILED.value == "failed"
    assert EvaluationStatus.WARNING.value == "warning"
    assert EvaluationStatus.SKIPPED.value == "skipped"


def test_evaluation_severity_values() -> None:
    assert EvaluationSeverity.INFO.value == "info"
    assert EvaluationSeverity.WARNING.value == "warning"
    assert EvaluationSeverity.ERROR.value == "error"


def test_evaluation_check_result_accepts_valid_data() -> None:
    result = EvaluationCheckResult(
        check_name="artifact_exists",
        status=EvaluationStatus.PASSED,
        severity=EvaluationSeverity.INFO,
        message="Artifact exists.",
        details={"path": "artifacts/result.md"},
    )

    assert result.check_name == "artifact_exists"
    assert result.status == EvaluationStatus.PASSED
    assert result.severity == EvaluationSeverity.INFO
    assert result.message == "Artifact exists."
    assert result.details == {"path": "artifacts/result.md"}


@pytest.mark.parametrize("check_name", ["", "   "])
def test_evaluation_check_result_rejects_empty_check_name(check_name: str) -> None:
    with pytest.raises(ValidationError):
        EvaluationCheckResult(
            check_name=check_name,
            status=EvaluationStatus.PASSED,
            severity=EvaluationSeverity.INFO,
            message="Artifact exists.",
        )


@pytest.mark.parametrize("message", ["", "   "])
def test_evaluation_check_result_rejects_empty_message(message: str) -> None:
    with pytest.raises(ValidationError):
        EvaluationCheckResult(
            check_name="artifact_exists",
            status=EvaluationStatus.PASSED,
            severity=EvaluationSeverity.INFO,
            message=message,
        )


def test_evaluation_check_result_details_default_dict_is_independent() -> None:
    first = _check_result()
    second = _check_result()

    first.details["path"] = "artifacts/result.md"

    assert second.details == {}


def test_evaluation_report_accepts_valid_data() -> None:
    run_id = uuid4()
    report = EvaluationReport(
        run_id=run_id,
        artifact_path=Path("artifacts/result.md"),
        target_name="review_theme_summary",
        target_type="markdown_artifact",
        evaluator_name="generic_structure",
        evaluator_version="v0",
        checks=[_check_result()],
        metadata={"provider": "fake"},
    )

    assert report.run_id == run_id
    assert report.artifact_path == Path("artifacts/result.md")
    assert report.target_name == "review_theme_summary"
    assert report.target_type == "markdown_artifact"
    assert report.evaluator_name == "generic_structure"
    assert report.evaluator_version == "v0"
    assert len(report.checks) == 1
    assert report.metadata == {"provider": "fake"}


def test_evaluation_report_generates_report_id() -> None:
    report = _report()

    assert isinstance(report.report_id, UUID)


def test_evaluation_report_created_at_utc_is_timezone_aware() -> None:
    report = _report()

    assert report.created_at_utc.tzinfo is not None
    assert report.created_at_utc.utcoffset() is not None


def test_evaluation_report_checks_default_list_is_independent() -> None:
    first = _report()
    second = _report()

    first.checks.append(_check_result())

    assert second.checks == []


def test_evaluation_report_metadata_default_dict_is_independent() -> None:
    first = _report()
    second = _report()

    first.metadata["provider"] = "fake"

    assert second.metadata == {}


@pytest.mark.parametrize(
    ("field_name", "value"),
    [
        ("target_name", ""),
        ("target_name", "   "),
        ("target_type", ""),
        ("target_type", "   "),
        ("evaluator_name", ""),
        ("evaluator_name", "   "),
        ("evaluator_version", ""),
        ("evaluator_version", "   "),
    ],
)
def test_evaluation_report_rejects_empty_identity_fields(
    field_name: str,
    value: str,
) -> None:
    with pytest.raises(ValidationError):
        if field_name == "target_name":
            _report(target_name=value)
        elif field_name == "target_type":
            _report(target_type=value)
        elif field_name == "evaluator_name":
            _report(evaluator_name=value)
        else:
            _report(evaluator_version=value)


def test_evaluation_report_passed_is_true_when_no_failed_error_checks_exist() -> None:
    report = _report(
        checks=[
            _check_result(status=EvaluationStatus.PASSED, severity=EvaluationSeverity.INFO),
            _check_result(status=EvaluationStatus.WARNING, severity=EvaluationSeverity.WARNING),
            _check_result(status=EvaluationStatus.FAILED, severity=EvaluationSeverity.WARNING),
        ]
    )

    assert report.passed is True


def test_evaluation_report_passed_is_false_when_failed_error_checks_exist() -> None:
    report = _report(
        checks=[
            _check_result(status=EvaluationStatus.FAILED, severity=EvaluationSeverity.ERROR),
        ]
    )

    assert report.passed is False


def test_evaluation_report_count_properties() -> None:
    report = _report(
        checks=[
            _check_result(status=EvaluationStatus.PASSED, severity=EvaluationSeverity.INFO),
            _check_result(status=EvaluationStatus.WARNING, severity=EvaluationSeverity.WARNING),
            _check_result(status=EvaluationStatus.FAILED, severity=EvaluationSeverity.WARNING),
            _check_result(status=EvaluationStatus.FAILED, severity=EvaluationSeverity.ERROR),
        ]
    )

    assert report.failed_count == 2
    assert report.warning_count == 1
    assert report.error_count == 1


def test_evaluation_report_json_serialization_uses_enum_string_values() -> None:
    report = _report(
        checks=[
            _check_result(status=EvaluationStatus.PASSED, severity=EvaluationSeverity.INFO),
        ]
    )

    data = cast(dict[str, Any], json.loads(report.model_dump_json()))

    assert data["checks"][0]["status"] == "passed"
    assert data["checks"][0]["severity"] == "info"


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
    )


def _report(
    *,
    checks: list[EvaluationCheckResult] | None = None,
    target_name: str = "review_theme_summary",
    target_type: str = "markdown_artifact",
    evaluator_name: str = "generic_structure",
    evaluator_version: str = "v0",
) -> EvaluationReport:
    return EvaluationReport(
        target_name=target_name,
        target_type=target_type,
        evaluator_name=evaluator_name,
        evaluator_version=evaluator_version,
        checks=checks or [],
    )
