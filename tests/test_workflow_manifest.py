from pathlib import Path

import pytest
from pydantic import ValidationError

from daedalus.shared.workflow_manifest import (
    WorkflowExecutionEngine,
    load_workflow_manifest,
)


SAMPLE_MANIFEST_PATH = Path("workflows/readysetrentables_review_normalization.yaml")
LANGGRAPH_SAMPLE_MANIFEST_PATH = Path(
    "workflows/readysetrentables_review_normalization_langgraph.yaml"
)


def test_loads_committed_workflow_manifest() -> None:
    manifest = load_workflow_manifest(SAMPLE_MANIFEST_PATH)

    assert manifest.workflow_name == "readysetrentables_review_normalization"
    assert manifest.domain == "readysetrentables_reviews"
    assert manifest.input_csv_path == Path(
        "sample_data/readysetrentables_reviews/airbnb_reviews_sample.csv"
    )
    assert manifest.output_json_path == Path("artifacts/readysetrentables/normalized_reviews.json")
    assert manifest.execution_engine == WorkflowExecutionEngine.DETERMINISTIC


def test_loads_committed_langgraph_workflow_manifest() -> None:
    manifest = load_workflow_manifest(LANGGRAPH_SAMPLE_MANIFEST_PATH)

    assert manifest.workflow_name == "readysetrentables_review_normalization"
    assert manifest.domain == "readysetrentables_reviews"
    assert manifest.execution_engine == WorkflowExecutionEngine.LANGGRAPH


def test_manifest_without_execution_engine_defaults_to_deterministic(tmp_path: Path) -> None:
    manifest_path = tmp_path / "default_engine.yaml"
    manifest_path.write_text(
        "\n".join(
            [
                "workflow_name: readysetrentables_review_normalization",
                "domain: readysetrentables_reviews",
                "input_csv_path: sample.csv",
                "output_json_path: output.json",
            ]
        ),
        encoding="utf-8",
    )

    manifest = load_workflow_manifest(manifest_path)

    assert manifest.execution_engine == WorkflowExecutionEngine.DETERMINISTIC


def test_manifest_rejects_unsupported_execution_engine(tmp_path: Path) -> None:
    manifest_path = tmp_path / "unsupported_engine.yaml"
    manifest_path.write_text(
        "\n".join(
            [
                "workflow_name: readysetrentables_review_normalization",
                "domain: readysetrentables_reviews",
                "input_csv_path: sample.csv",
                "output_json_path: output.json",
                "execution_engine: unsupported",
            ]
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValidationError):
        load_workflow_manifest(manifest_path)


def test_missing_workflow_manifest_raises_file_not_found() -> None:
    with pytest.raises(FileNotFoundError):
        load_workflow_manifest(Path("workflows/missing.yaml"))
