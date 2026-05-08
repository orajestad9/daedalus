"""Human-readable formatting for persisted workflow run inspection."""

from daedalus.model_clients.invocation_record import ModelInvocationRecord
from daedalus.orchestrator.artifact_record import ArtifactRecord
from daedalus.orchestrator.run_record import WorkflowRunRecord
from daedalus.orchestrator.step_record import WorkflowStepRecord


def format_run_inspection(
    record: WorkflowRunRecord,
    artifacts: list[ArtifactRecord],
    steps: list[WorkflowStepRecord],
    model_invocations: list[ModelInvocationRecord] | None = None,
) -> str:
    """Format a workflow run, artifacts, steps, and model calls for CLI inspection."""
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
    lines.append("Model Invocations:")
    lines.extend(_format_model_invocations(model_invocations or []))
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


def _format_model_invocations(model_invocations: list[ModelInvocationRecord]) -> list[str]:
    if not model_invocations:
        return ["No model invocations recorded."]

    lines: list[str] = []
    for invocation in model_invocations:
        fields = [
            f"provider={invocation.provider.value}",
            f"model_name={invocation.model_name}",
            f"prompt_name={invocation.prompt_name}",
            f"prompt_version={invocation.prompt_version}",
            f"status={invocation.status.value}",
            f"input_tokens={invocation.input_tokens}",
            f"output_tokens={invocation.output_tokens}",
            f"total_tokens={invocation.total_tokens}",
            f"estimated_cost_usd={invocation.estimated_cost_usd}",
            f"duration_ms={invocation.duration_ms}",
        ]
        if invocation.agent_name:
            fields.append(f"agent_name={invocation.agent_name}")
        if invocation.error_message:
            fields.append(f"error_message={invocation.error_message}")
        lines.append(f"- {' '.join(fields)}")

    return lines
