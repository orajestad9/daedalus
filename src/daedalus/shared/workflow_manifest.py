from pathlib import Path
from typing import Any, cast

import yaml
from pydantic import BaseModel


class WorkflowManifest(BaseModel):
    """Declarative configuration for running a Daedalus workflow."""

    workflow_name: str
    domain: str
    description: str | None = None
    input_csv_path: Path
    output_json_path: Path
    requires_human_approval: bool = False


def load_workflow_manifest(manifest_path: Path) -> WorkflowManifest:
    """Load and validate a workflow manifest from YAML."""
    if not manifest_path.exists():
        raise FileNotFoundError(manifest_path)

    manifest_data = cast(
        dict[str, Any],
        yaml.safe_load(manifest_path.read_text(encoding="utf-8")),
    )
    return WorkflowManifest.model_validate(manifest_data)
