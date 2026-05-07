import json
from typing import Any, cast
from uuid import uuid4

from daedalus.orchestrator.status import WorkflowStatus
from daedalus.orchestrator.step_record import WorkflowStepRecord


def test_workflow_step_record_start_creates_running_step() -> None:
    run_id = uuid4()

    step = WorkflowStepRecord.start(run_id=run_id, step_name="load_csv")

    assert step.run_id == run_id
    assert step.step_name == "load_csv"
    assert step.status == WorkflowStatus.RUNNING
    assert step.completed_at_utc is None
    assert step.duration_ms is None
    assert step.error_message is None
    assert step.started_at_utc.tzinfo is not None


def test_workflow_step_record_complete_marks_step_completed() -> None:
    step = WorkflowStepRecord.start(run_id=uuid4(), step_name="normalize_reviews")

    completed_step = step.complete()

    assert completed_step.step_id == step.step_id
    assert completed_step.status == WorkflowStatus.COMPLETED
    assert completed_step.completed_at_utc is not None
    assert completed_step.duration_ms is not None
    assert completed_step.duration_ms >= 0
    assert completed_step.error_message is None
    assert step.status == WorkflowStatus.RUNNING


def test_workflow_step_record_fail_marks_step_failed() -> None:
    step = WorkflowStepRecord.start(run_id=uuid4(), step_name="write_artifact")

    failed_step = step.fail("artifact write failed")

    assert failed_step.step_id == step.step_id
    assert failed_step.status == WorkflowStatus.FAILED
    assert failed_step.completed_at_utc is not None
    assert failed_step.duration_ms is not None
    assert failed_step.duration_ms >= 0
    assert failed_step.error_message == "artifact write failed"
    assert step.status == WorkflowStatus.RUNNING


def test_workflow_step_record_json_serializes_status_value() -> None:
    step = WorkflowStepRecord.start(run_id=uuid4(), step_name="load_csv").complete()

    data = cast(dict[str, Any], json.loads(step.model_dump_json()))

    assert data["status"] == "completed"
