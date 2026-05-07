import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast
from uuid import uuid4

from daedalus.orchestrator.run_record import (
    WorkflowRunRecord,
    write_workflow_run_record_json,
)
from daedalus.orchestrator.artifact_type import ArtifactType
from daedalus.orchestrator.status import WorkflowStatus
from daedalus.orchestrator.workflow_identity import WorkflowDomain, WorkflowName


def test_writes_workflow_run_record_json(tmp_path: Path) -> None:
    run_id = uuid4()
    record_path = tmp_path / "runs" / "normalized_reviews.run.json"
    record = WorkflowRunRecord(
        run_id=run_id,
        workflow_name="readysetrentables_review_normalization",
        domain="readysetrentables_reviews",
        status=WorkflowStatus.COMPLETED,
        started_at_utc=datetime(2026, 5, 7, 10, 0, tzinfo=UTC),
        completed_at_utc=datetime(2026, 5, 7, 10, 1, tzinfo=UTC),
        source_input_path=Path("sample.csv"),
        output_artifact_path=Path("normalized_reviews.json"),
        metadata_artifact_path=Path("normalized_reviews.metadata.json"),
        summary_artifact_path=Path("normalized_reviews.summary.md"),
        run_record_artifact_path=Path("normalized_reviews.run.json"),
        duration_ms=60_000,
        review_count=8,
        approval_required=True,
        approved=True,
    )

    returned_path = write_workflow_run_record_json(record, record_path)

    data = cast(dict[str, Any], json.loads(record_path.read_text(encoding="utf-8")))
    assert returned_path == record_path
    assert data["run_id"] == str(run_id)
    assert data["workflow_name"] == "readysetrentables_review_normalization"
    assert data["domain"] == "readysetrentables_reviews"
    assert data["status"] == "completed"
    assert data["run_record_artifact_path"] == "normalized_reviews.run.json"
    assert data["duration_ms"] == 60_000
    assert data["review_count"] == 8
    assert data["approval_required"] is True
    assert data["approved"] is True


def test_workflow_status_values_are_stable() -> None:
    assert WorkflowStatus.PENDING.value == "pending"
    assert WorkflowStatus.RUNNING.value == "running"
    assert WorkflowStatus.COMPLETED.value == "completed"
    assert WorkflowStatus.FAILED.value == "failed"
    assert WorkflowStatus.BLOCKED_APPROVAL_REQUIRED.value == "blocked_approval_required"


def test_artifact_type_values_are_stable() -> None:
    assert ArtifactType.NORMALIZED_REVIEWS.value == "normalized_reviews"
    assert ArtifactType.REVIEW_METADATA.value == "review_metadata"
    assert ArtifactType.WORKFLOW_SUMMARY.value == "workflow_summary"
    assert ArtifactType.WORKFLOW_RUN_RECORD.value == "workflow_run_record"
    assert ArtifactType.APPROVAL_RECORD.value == "approval_record"
    assert ArtifactType.AGENT_OUTPUT.value == "agent_output"
    assert ArtifactType.VALIDATION_REPORT.value == "validation_report"


def test_workflow_identity_values_are_stable() -> None:
    assert (
        WorkflowName.READYSETRENTABLES_REVIEW_NORMALIZATION.value
        == "readysetrentables_review_normalization"
    )
    assert WorkflowDomain.READYSETRENTABLES_REVIEWS.value == "readysetrentables_reviews"
