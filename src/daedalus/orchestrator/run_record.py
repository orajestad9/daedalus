"""Workflow execution records shared across Daedalus workflows.

Phase 0 stores run records as local JSON artifacts. The model is intentionally
generic so the same shape can later back a Postgres `workflow_runs` table without
forcing each domain workflow to invent its own execution schema.
"""

from datetime import datetime
from pathlib import Path
from uuid import UUID

from pydantic import BaseModel

from daedalus.orchestrator.status import WorkflowStatus


class WorkflowRunRecord(BaseModel):
    """Machine-readable record of one workflow execution."""

    run_id: UUID
    workflow_name: str
    domain: str
    status: WorkflowStatus
    started_at_utc: datetime
    completed_at_utc: datetime
    source_input_path: Path
    output_artifact_path: Path
    metadata_artifact_path: Path
    summary_artifact_path: Path
    run_record_artifact_path: Path
    duration_ms: int
    review_count: int
    approval_required: bool
    approved: bool


def write_workflow_run_record_json(record: WorkflowRunRecord, output_path: Path) -> Path:
    """Write a local JSON run record artifact for auditing and future persistence."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(record.model_dump_json(indent=2) + "\n", encoding="utf-8")
    return output_path
