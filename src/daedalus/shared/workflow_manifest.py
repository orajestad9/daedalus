"""Workflow manifest loading and validation.

Manifests are the bridge between local Python calls and repeatable automation.
Docker containers, Kubernetes jobs, GitHub Actions, and future agents can all
point at the same YAML file instead of rebuilding workflow arguments by hand.
"""

from pathlib import Path
from typing import Any, cast

import yaml
from pydantic import BaseModel


class WorkflowManifest(BaseModel):
    """Validated declarative configuration for running a Daedalus workflow."""

    workflow_name: str
    domain: str
    description: str | None = None
    input_csv_path: Path
    output_json_path: Path
    requires_human_approval: bool = False


def load_workflow_manifest(manifest_path: Path) -> WorkflowManifest:
    """Load YAML and validate it with Pydantic before orchestration.

    Pydantic keeps path and boolean handling consistent at the platform boundary,
    which is important once manifests are produced by humans, CI jobs, or agents.
    """
    if not manifest_path.exists():
        raise FileNotFoundError(manifest_path)

    manifest_data = cast(
        dict[str, Any],
        yaml.safe_load(manifest_path.read_text(encoding="utf-8")),
    )
    return WorkflowManifest.model_validate(manifest_data)
