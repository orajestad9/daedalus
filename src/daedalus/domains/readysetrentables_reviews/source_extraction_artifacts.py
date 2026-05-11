"""Artifact writers for ReadySetRentables source extraction outputs."""

import json
from pathlib import Path

from daedalus.domains.readysetrentables_reviews.source_extraction_models import (
    RsrSourceExtractionResult,
)


def write_rsr_source_extract_json(
    *,
    result: RsrSourceExtractionResult,
    output_path: Path,
) -> Path:
    """Write a sanitized JSON artifact for an RSR source extraction result."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.loads(result.model_dump_json())
    output_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return output_path
