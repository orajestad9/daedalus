from pathlib import Path

from daedalus.domains.readysetrentables_reviews.models import ReviewBatch


def write_review_batch_json(batch: ReviewBatch, output_path: Path) -> Path:
    """Write a normalized review batch as a pretty-formatted JSON artifact."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(batch.model_dump_json(indent=2) + "\n", encoding="utf-8")
    return output_path
