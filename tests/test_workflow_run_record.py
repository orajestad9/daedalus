import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast
from uuid import uuid4

from daedalus.orchestrator.run_record import (
    WorkflowRunRecord,
    write_workflow_run_record_json,
)


def test_writes_workflow_run_record_json(tmp_path: Path) -> None:
    run_id = uuid4()
    record_path = tmp_path / "runs" / "normalized_reviews.run.json"
    record = WorkflowRunRecord(
        run_id=run_id,
        workflow_name="readysetrentables_review_normalization",
        domain="readysetrentables_reviews",
        status="completed",
        started_at_utc=datetime(2026, 5, 7, 10, 0, tzinfo=UTC),
        completed_at_utc=datetime(2026, 5, 7, 10, 1, tzinfo=UTC),
        source_input_path=Path("sample.csv"),
        output_artifact_path=Path("normalized_reviews.json"),
        metadata_artifact_path=Path("normalized_reviews.metadata.json"),
        summary_artifact_path=Path("normalized_reviews.summary.md"),
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
    assert data["review_count"] == 8
    assert data["approval_required"] is True
    assert data["approved"] is True
