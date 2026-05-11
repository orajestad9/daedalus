"""Artifact writers for ReadySetRentables review insight extraction outputs."""

import json
from pathlib import Path

from daedalus.domains.readysetrentables_reviews.review_insight_models import (
    ReviewInsightExtractionResult,
)


def write_review_insights_json(
    *,
    result: ReviewInsightExtractionResult,
    output_path: Path,
) -> Path:
    """Write a structured JSON artifact for a review insight extraction result."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.loads(result.model_dump_json())
    output_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return output_path
