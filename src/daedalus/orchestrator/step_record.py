"""Workflow step records for future step-level observability."""

from datetime import datetime
from uuid import UUID, uuid4

from pydantic import BaseModel

from daedalus.orchestrator.run_lifecycle import calculate_duration_ms, utc_now
from daedalus.orchestrator.status import WorkflowStatus


class WorkflowStepRecord(BaseModel):
    """Machine-readable record of one observable step inside a workflow run."""

    step_id: UUID
    run_id: UUID
    step_name: str
    status: WorkflowStatus
    started_at_utc: datetime
    completed_at_utc: datetime | None
    duration_ms: int | None
    error_message: str | None

    @classmethod
    def start(cls, run_id: UUID, step_name: str) -> "WorkflowStepRecord":
        """Create a running step record with generated identity and UTC start time."""
        return cls(
            step_id=uuid4(),
            run_id=run_id,
            step_name=step_name,
            status=WorkflowStatus.RUNNING,
            started_at_utc=utc_now(),
            completed_at_utc=None,
            duration_ms=None,
            error_message=None,
        )

    def complete(self) -> "WorkflowStepRecord":
        """Return a completed copy of this step record."""
        completed_at_utc = utc_now()
        return self.model_copy(
            update={
                "status": WorkflowStatus.COMPLETED,
                "completed_at_utc": completed_at_utc,
                "duration_ms": calculate_duration_ms(
                    self.started_at_utc,
                    completed_at_utc,
                ),
                "error_message": None,
            }
        )

    def fail(self, error_message: str) -> "WorkflowStepRecord":
        """Return a failed copy of this step record."""
        completed_at_utc = utc_now()
        return self.model_copy(
            update={
                "status": WorkflowStatus.FAILED,
                "completed_at_utc": completed_at_utc,
                "duration_ms": calculate_duration_ms(
                    self.started_at_utc,
                    completed_at_utc,
                ),
                "error_message": error_message,
            }
        )
