"""Artifact writers for the ReadySetRentables review workflow.

The normalized JSON and metadata artifacts are machine-readable contracts for
later validators, storage, and agents. The markdown summary is intentionally
human-readable so a reviewer or future review agent can understand a run without
opening the full JSON payload.
"""

import json
from datetime import datetime
from pathlib import Path
from uuid import UUID

from pydantic import BaseModel, ValidationError

from daedalus.domains.readysetrentables_reviews.models import ReviewBatch
from daedalus.orchestrator.artifact_type import ArtifactType
from daedalus.orchestrator.step_record import WorkflowStepRecord


class ReviewBatchArtifactMetadata(BaseModel):
    """Trace metadata for the normalized review JSON artifact."""

    run_id: UUID
    workflow_name: str
    artifact_type: ArtifactType
    source_csv_path: Path
    output_json_path: Path
    created_at_utc: datetime
    review_count: int


def write_review_batch_json(batch: ReviewBatch, output_path: Path) -> Path:
    """Write the normalized reviews artifact consumed by downstream automation."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(batch.model_dump_json(indent=2) + "\n", encoding="utf-8")
    return output_path


def load_review_batch_json(input_path: Path) -> ReviewBatch:
    """Load a normalized review batch JSON artifact from disk."""
    return ReviewBatch.model_validate_json(input_path.read_text(encoding="utf-8"))


def load_review_batch_metadata_json(input_path: Path) -> ReviewBatchArtifactMetadata:
    """Load trace metadata for a normalized review JSON artifact from disk."""
    if not input_path.is_file():
        msg = f"Review batch metadata path does not exist: {input_path}"
        raise FileNotFoundError(msg)

    try:
        parsed = json.loads(input_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        msg = "Review batch metadata artifact is not valid JSON."
        raise ValueError(msg) from exc

    try:
        return ReviewBatchArtifactMetadata.model_validate(parsed)
    except ValidationError as exc:
        msg = "Review batch metadata artifact does not match the expected schema."
        raise ValueError(msg) from exc


def write_review_batch_metadata_json(
    metadata: ReviewBatchArtifactMetadata,
    output_path: Path,
) -> Path:
    """Write metadata that connects the review artifact to a workflow run."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(metadata.model_dump_json(indent=2) + "\n", encoding="utf-8")
    return output_path


def write_review_normalization_summary_markdown(
    *,
    run_id: UUID,
    source_csv_path: Path,
    output_json_path: Path,
    metadata_json_path: Path,
    summary_markdown_path: Path,
    review_count: int,
    approval_required: bool,
    approved: bool,
    steps: list[WorkflowStepRecord] | None = None,
) -> Path:
    """Write the compact human-readable run summary artifact."""
    summary_markdown_path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# ReadySetRentables Review Normalization Summary",
        "",
        f"- Run ID: `{run_id}`",
        f"- Source CSV path: `{source_csv_path}`",
        f"- Normalized JSON path: `{output_json_path}`",
        f"- Metadata JSON path: `{metadata_json_path}`",
        f"- Review count: {review_count}",
        f"- Approval required: {approval_required}",
        f"- Approved: {approved}",
        "- Status: Completed successfully.",
        "",
    ]
    if steps is not None:
        lines.extend(["## Workflow Steps", ""])
        if steps:
            lines.extend(f"- {step.step_name}: {step.status.value}" for step in steps)
        else:
            lines.append("- No workflow steps recorded before summary generation.")
        lines.append("")

    markdown = "\n".join(lines)
    summary_markdown_path.write_text(markdown, encoding="utf-8")
    return summary_markdown_path
