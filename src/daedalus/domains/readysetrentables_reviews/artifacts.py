"""Artifact writers for the ReadySetRentables review workflow.

The normalized JSON and metadata artifacts are machine-readable contracts for
later validators, storage, and agents. The markdown summary is intentionally
human-readable so a reviewer or future review agent can understand a run without
opening the full JSON payload.
"""

from datetime import datetime
from pathlib import Path
from uuid import UUID

from pydantic import BaseModel

from daedalus.domains.readysetrentables_reviews.models import ReviewBatch
from daedalus.orchestrator.artifact_type import ArtifactType


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
) -> Path:
    """Write the compact human-readable run summary artifact."""
    summary_markdown_path.parent.mkdir(parents=True, exist_ok=True)
    markdown = "\n".join(
        [
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
    )
    summary_markdown_path.write_text(markdown, encoding="utf-8")
    return summary_markdown_path
