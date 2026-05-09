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
