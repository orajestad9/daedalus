from datetime import datetime
from pathlib import Path
from uuid import UUID

from pydantic import BaseModel

from daedalus.domains.readysetrentables_reviews.models import ReviewBatch


class ReviewBatchArtifactMetadata(BaseModel):
    """Metadata describing a generated normalized review batch artifact."""

    run_id: UUID
    workflow_name: str
    artifact_type: str
    source_csv_path: Path
    output_json_path: Path
    created_at_utc: datetime
    review_count: int


def write_review_batch_json(batch: ReviewBatch, output_path: Path) -> Path:
    """Write a normalized review batch as a pretty-formatted JSON artifact."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(batch.model_dump_json(indent=2) + "\n", encoding="utf-8")
    return output_path


def write_review_batch_metadata_json(
    metadata: ReviewBatchArtifactMetadata,
    output_path: Path,
) -> Path:
    """Write normalized review batch metadata as a pretty-formatted JSON artifact."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(metadata.model_dump_json(indent=2) + "\n", encoding="utf-8")
    return output_path
