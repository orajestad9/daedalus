import logging
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID, uuid4

from pydantic import BaseModel

from daedalus.domains.readysetrentables_reviews.artifacts import (
    ReviewBatchArtifactMetadata,
    write_review_batch_json,
    write_review_batch_metadata_json,
)
from daedalus.domains.readysetrentables_reviews.ingestion import load_airbnb_reviews_csv


logger = logging.getLogger(__name__)
WORKFLOW_NAME = "readysetrentables_review_normalization"
REVIEW_BATCH_ARTIFACT_TYPE = "normalized_review_batch"


class ReviewNormalizationWorkflowResult(BaseModel):
    """Result returned after normalizing review CSV data into a JSON artifact."""

    source_csv_path: Path
    output_json_path: Path
    metadata_json_path: Path
    review_count: int
    run_id: UUID


def run_review_normalization_workflow(
    input_csv_path: Path,
    output_json_path: Path,
) -> ReviewNormalizationWorkflowResult:
    """Run the deterministic review normalization workflow."""
    run_id = uuid4()

    logger.info("Starting review normalization workflow run_id=%s", run_id)
    logger.info("Input CSV path: %s run_id=%s", input_csv_path, run_id)
    logger.info("Output JSON path: %s run_id=%s", output_json_path, run_id)

    batch = load_airbnb_reviews_csv(input_csv_path)
    artifact_path = write_review_batch_json(batch, output_json_path)
    metadata_path = _metadata_path_for(artifact_path)
    metadata = ReviewBatchArtifactMetadata(
        run_id=run_id,
        workflow_name=WORKFLOW_NAME,
        artifact_type=REVIEW_BATCH_ARTIFACT_TYPE,
        source_csv_path=input_csv_path,
        output_json_path=artifact_path,
        created_at_utc=datetime.now(UTC),
        review_count=batch.review_count,
    )
    write_review_batch_metadata_json(metadata, metadata_path)

    logger.info("Review count: %s run_id=%s", batch.review_count, run_id)
    logger.info("Metadata JSON path: %s run_id=%s", metadata_path, run_id)
    logger.info("Completed review normalization workflow run_id=%s", run_id)

    return ReviewNormalizationWorkflowResult(
        source_csv_path=input_csv_path,
        output_json_path=artifact_path,
        metadata_json_path=metadata_path,
        review_count=batch.review_count,
        run_id=run_id,
    )


def _metadata_path_for(output_json_path: Path) -> Path:
    return output_json_path.with_name(f"{output_json_path.stem}.metadata.json")
