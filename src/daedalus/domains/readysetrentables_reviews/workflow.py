from pathlib import Path

from pydantic import BaseModel

from daedalus.domains.readysetrentables_reviews.artifacts import write_review_batch_json
from daedalus.domains.readysetrentables_reviews.ingestion import load_airbnb_reviews_csv


class ReviewNormalizationWorkflowResult(BaseModel):
    """Result returned after normalizing review CSV data into a JSON artifact."""

    source_csv_path: Path
    output_json_path: Path
    review_count: int


def run_review_normalization_workflow(
    input_csv_path: Path,
    output_json_path: Path,
) -> ReviewNormalizationWorkflowResult:
    """Run the deterministic review normalization workflow."""

    batch = load_airbnb_reviews_csv(input_csv_path)
    artifact_path = write_review_batch_json(batch, output_json_path)

    return ReviewNormalizationWorkflowResult(
        source_csv_path=input_csv_path,
        output_json_path=artifact_path,
        review_count=batch.review_count,
    )
