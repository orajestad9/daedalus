"""Typed LangGraph state for the ReadySetRentables review workflow.

This state model is the structured handoff between deterministic LangGraph
nodes. Keeping state typed here lets graph execution exchange domain objects,
artifact paths, and workflow steps instead of loose prompt text.
"""

from datetime import datetime
from pathlib import Path
from uuid import UUID, uuid4

from pydantic import BaseModel, Field

from daedalus.domains.readysetrentables_reviews.models import ReviewBatch
from daedalus.orchestrator.run_lifecycle import utc_now
from daedalus.orchestrator.step_record import WorkflowStepRecord


class ReadySetRentablesReviewGraphState(BaseModel):
    """Structured state passed between ReadySetRentables LangGraph nodes."""

    run_id: UUID
    started_at_utc: datetime
    input_csv_path: Path
    output_json_path: Path
    batch: ReviewBatch | None = None
    metadata_json_path: Path | None = None
    summary_markdown_path: Path | None = None
    run_record_json_path: Path | None = None
    steps: list[WorkflowStepRecord] = Field(default_factory=list)
    approval_required: bool = False
    approved: bool = False

    @classmethod
    def create(
        cls,
        input_csv_path: Path,
        output_json_path: Path,
        approval_required: bool = False,
        approved: bool = False,
    ) -> "ReadySetRentablesReviewGraphState":
        """Create initial graph state with generated workflow identity."""
        return cls(
            run_id=uuid4(),
            started_at_utc=utc_now(),
            input_csv_path=input_csv_path,
            output_json_path=output_json_path,
            approval_required=approval_required,
            approved=approved,
        )
