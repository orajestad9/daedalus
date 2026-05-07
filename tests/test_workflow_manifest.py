from pathlib import Path

import pytest

from daedalus.shared.workflow_manifest import load_workflow_manifest


SAMPLE_MANIFEST_PATH = Path("workflows/readysetrentables_review_normalization.yaml")


def test_loads_committed_workflow_manifest() -> None:
    manifest = load_workflow_manifest(SAMPLE_MANIFEST_PATH)

    assert manifest.workflow_name == "readysetrentables_review_normalization"
    assert manifest.domain == "readysetrentables_reviews"
    assert manifest.input_csv_path == Path(
        "sample_data/readysetrentables_reviews/airbnb_reviews_sample.csv"
    )
    assert manifest.output_json_path == Path("artifacts/readysetrentables/normalized_reviews.json")


def test_missing_workflow_manifest_raises_file_not_found() -> None:
    with pytest.raises(FileNotFoundError):
        load_workflow_manifest(Path("workflows/missing.yaml"))
