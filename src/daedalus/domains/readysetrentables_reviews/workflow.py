import logging
from pathlib import Path
from uuid import UUID, uuid4

from pydantic import BaseModel

from daedalus.domains.readysetrentables_reviews.artifacts import write_review_batch_json
from daedalus.domains.readysetrentables_reviews.ingestion import load_airbnb_reviews_csv


logger = logging.getLogger(__name__)


class ReviewNormalizationWorkflowResult(BaseModel):
    """Result returned after normalizing review CSV data into a JSON artifact."""

    source_csv_path: Path
    output_json_path: Path
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

    logger.info("Review count: %s run_id=%s", batch.review_count, run_id)
    logger.info("Completed review normalization workflow run_id=%s", run_id)

    return ReviewNormalizationWorkflowResult(
        source_csv_path=input_csv_path,
        output_json_path=artifact_path,
        review_count=batch.review_count,
        run_id=run_id,
    )
