"""Human-readable formatting for persisted workflow run inspection."""

from daedalus.orchestrator.artifact_record import ArtifactRecord
from daedalus.orchestrator.run_record import WorkflowRunRecord
from daedalus.orchestrator.step_record import WorkflowStepRecord


def format_run_inspection(
    record: WorkflowRunRecord,
    artifacts: list[ArtifactRecord],
    steps: list[WorkflowStepRecord],
) -> str:
    """Format a workflow run, artifacts, and steps for CLI inspection."""
    lines = [
        f"Workflow run {record.run_id}",
        f"workflow_name: {record.workflow_name}",
        f"domain: {record.domain}",
        f"status: {record.status.value}",
        f"started_at_utc: {record.started_at_utc.isoformat()}",
        f"completed_at_utc: {record.completed_at_utc.isoformat()}",
        f"duration_ms: {record.duration_ms}",
        f"review_count: {record.review_count}",
        f"approval_required: {record.approval_required}",
        f"approved: {record.approved}",
        f"source_input_path: {record.source_input_path}",
        f"output_artifact_path: {record.output_artifact_path}",
        f"metadata_artifact_path: {record.metadata_artifact_path}",
        f"summary_artifact_path: {record.summary_artifact_path}",
        f"run_record_artifact_path: {record.run_record_artifact_path}",
        "artifacts:",
    ]
    lines.extend(_format_artifacts(artifacts))
    lines.append("steps:")
    lines.extend(_format_steps(steps))
    return "\n".join(lines)


def _format_artifacts(artifacts: list[ArtifactRecord]) -> list[str]:
    if not artifacts:
        return ["No artifact records found."]

    return [f"- {artifact.artifact_type.value}: {artifact.artifact_path}" for artifact in artifacts]


def _format_steps(steps: list[WorkflowStepRecord]) -> list[str]:
    if not steps:
        return ["No workflow steps recorded."]

    lines: list[str] = []
    for step in steps:
        line = f"- {step.step_name}: status={step.status.value} duration_ms={step.duration_ms}"
        if step.error_message:
            line = f"{line} error_message={step.error_message}"
        lines.append(line)

    return lines
