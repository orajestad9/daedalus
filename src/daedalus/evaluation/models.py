"""Generic evaluation result models.

These models intentionally avoid domain-specific scoring rules. Domain modules
can use them to report deterministic checks for artifacts, model outputs, and
future provider comparisons without hardcoding a domain into the platform layer.
"""

from datetime import datetime
from enum import StrEnum
from pathlib import Path
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, field_validator

from daedalus.orchestrator.run_lifecycle import utc_now


class EvaluationStatus(StrEnum):
    """Outcome status for an evaluation check."""

    PASSED = "passed"
    FAILED = "failed"
    WARNING = "warning"
    SKIPPED = "skipped"


class EvaluationSeverity(StrEnum):
    """Severity for an evaluation check result."""

    INFO = "info"
    WARNING = "warning"
    ERROR = "error"


class EvaluationCheckResult(BaseModel):
    """Result for one generic evaluation check."""

    check_name: str
    status: EvaluationStatus
    severity: EvaluationSeverity
    message: str
    details: dict[str, str] = Field(default_factory=dict)

    @field_validator("check_name", "message")
    @classmethod
    def _validate_non_empty_text(cls, value: str) -> str:
        stripped_value = value.strip()
        if not stripped_value:
            msg = "Evaluation text fields must not be empty"
            raise ValueError(msg)

        return stripped_value


class EvaluationReport(BaseModel):
    """Aggregated generic evaluation report for an artifact or target."""

    report_id: UUID = Field(default_factory=uuid4)
    run_id: UUID | None = None
    artifact_path: Path | None = None
    target_name: str
    target_type: str
    evaluator_name: str
    evaluator_version: str
    created_at_utc: datetime = Field(default_factory=utc_now)
    checks: list[EvaluationCheckResult] = Field(default_factory=list)
    metadata: dict[str, str] = Field(default_factory=dict)

    @field_validator("target_name", "target_type", "evaluator_name", "evaluator_version")
    @classmethod
    def _validate_non_empty_text(cls, value: str) -> str:
        stripped_value = value.strip()
        if not stripped_value:
            msg = "Evaluation report identity fields must not be empty"
            raise ValueError(msg)

        return stripped_value

    @property
    def passed(self) -> bool:
        """Return True when no failed error-severity checks are present."""
        return all(
            not (
                check.status == EvaluationStatus.FAILED
                and check.severity == EvaluationSeverity.ERROR
            )
            for check in self.checks
        )

    @property
    def failed_count(self) -> int:
        """Count failed checks."""
        return sum(1 for check in self.checks if check.status == EvaluationStatus.FAILED)

    @property
    def warning_count(self) -> int:
        """Count warning-status checks."""
        return sum(1 for check in self.checks if check.status == EvaluationStatus.WARNING)

    @property
    def error_count(self) -> int:
        """Count error-severity checks."""
        return sum(1 for check in self.checks if check.severity == EvaluationSeverity.ERROR)


class EvaluationComparisonStatus(StrEnum):
    """Outcome status for a single comparison between two evaluation targets."""

    MATCH = "match"
    DIFFERENT = "different"
    IMPROVED = "improved"
    REGRESSED = "regressed"
    INCONCLUSIVE = "inconclusive"


class EvaluationComparisonItem(BaseModel):
    """Result for one generic comparison between a baseline and candidate."""

    comparison_name: str
    status: EvaluationComparisonStatus
    severity: EvaluationSeverity
    message: str
    baseline_value: str | None = None
    candidate_value: str | None = None
    details: dict[str, str] = Field(default_factory=dict)

    @field_validator("comparison_name", "message")
    @classmethod
    def _validate_non_empty_text(cls, value: str) -> str:
        stripped_value = value.strip()
        if not stripped_value:
            msg = "Comparison text fields must not be empty"
            raise ValueError(msg)
        return stripped_value


class EvaluationComparisonReport(BaseModel):
    """Aggregated generic comparison report across two evaluation targets or runs."""

    comparison_report_id: UUID = Field(default_factory=uuid4)
    baseline_report_id: UUID | None = None
    candidate_report_id: UUID | None = None
    baseline_artifact_path: Path | None = None
    candidate_artifact_path: Path | None = None
    target_name: str
    target_type: str
    comparator_name: str
    comparator_version: str
    created_at_utc: datetime = Field(default_factory=utc_now)
    comparisons: list[EvaluationComparisonItem] = Field(default_factory=list)
    metadata: dict[str, str] = Field(default_factory=dict)

    @field_validator("target_name", "target_type", "comparator_name", "comparator_version")
    @classmethod
    def _validate_non_empty_text(cls, value: str) -> str:
        stripped_value = value.strip()
        if not stripped_value:
            msg = "Comparison report identity fields must not be empty"
            raise ValueError(msg)
        return stripped_value

    @property
    def passed(self) -> bool:
        """Return True when no regressions or error-severity non-match comparisons exist."""
        return all(
            not (
                item.status == EvaluationComparisonStatus.REGRESSED
                or (
                    item.severity == EvaluationSeverity.ERROR
                    and item.status != EvaluationComparisonStatus.MATCH
                )
            )
            for item in self.comparisons
        )

    @property
    def different_count(self) -> int:
        """Count comparisons with DIFFERENT status."""
        return sum(
            1 for item in self.comparisons if item.status == EvaluationComparisonStatus.DIFFERENT
        )

    @property
    def improved_count(self) -> int:
        """Count comparisons with IMPROVED status."""
        return sum(
            1 for item in self.comparisons if item.status == EvaluationComparisonStatus.IMPROVED
        )

    @property
    def regressed_count(self) -> int:
        """Count comparisons with REGRESSED status."""
        return sum(
            1 for item in self.comparisons if item.status == EvaluationComparisonStatus.REGRESSED
        )

    @property
    def inconclusive_count(self) -> int:
        """Count comparisons with INCONCLUSIVE status."""
        return sum(
            1 for item in self.comparisons if item.status == EvaluationComparisonStatus.INCONCLUSIVE
        )
