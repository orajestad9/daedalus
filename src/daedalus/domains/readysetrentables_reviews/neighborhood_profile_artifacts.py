"""Artifact writers for ReadySetRentables neighborhood profile outputs."""

import json
from pathlib import Path

from daedalus.domains.readysetrentables_reviews.neighborhood_profile_models import (
    NeighborhoodProfileResult,
)


def write_neighborhood_profile_json(
    *,
    result: NeighborhoodProfileResult,
    output_path: Path,
) -> Path:
    """Write a structured JSON artifact for a neighborhood profile result."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.loads(result.model_dump_json())
    output_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return output_path


def write_neighborhood_profile_markdown(
    *,
    result: NeighborhoodProfileResult,
    output_path: Path,
) -> Path:
    """Write a markdown artifact for a neighborhood profile result."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(_neighborhood_profile_markdown(result), encoding="utf-8")
    return output_path


def _neighborhood_profile_markdown(result: NeighborhoodProfileResult) -> str:
    lines = [
        "<!-- Neighborhood Profile Metadata -->",
        f"<!-- run_id: {result.run_id} -->",
        f"<!-- provider: {result.provider.value} -->",
        f"<!-- model_name: {result.model_name} -->",
        f"<!-- prompt_name: {result.prompt_name} -->",
        f"<!-- prompt_version: {result.prompt_version} -->",
        f"<!-- market_name: {result.market_name} -->",
        f"<!-- neighborhood_name: {result.neighborhood_name} -->",
        "",
        result.markdown,
    ]
    return "\n".join(lines).rstrip() + "\n"
