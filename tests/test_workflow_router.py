from pathlib import Path

import pytest

from daedalus.orchestrator.workflow_router import (
    UnsupportedWorkflowError,
    run_workflow_from_manifest_path,
)


SAMPLE_CSV_PATH = Path("sample_data/readysetrentables_reviews/airbnb_reviews_sample.csv")
SAMPLE_MANIFEST_PATH = Path("workflows/readysetrentables_review_normalization.yaml")


def test_run_workflow_from_committed_manifest_succeeds() -> None:
    result = run_workflow_from_manifest_path(SAMPLE_MANIFEST_PATH)

    assert result.output_json_path.is_file()
    assert result.metadata_json_path.is_file()
    assert result.summary_markdown_path.is_file()
    assert result.review_count == 8


def test_run_workflow_from_manifest_rejects_unsupported_manifest(tmp_path: Path) -> None:
    manifest_path = tmp_path / "unsupported.yaml"
    manifest_path.write_text(
        "\n".join(
            [
                "workflow_name: unsupported_workflow",
                "domain: unsupported_domain",
                "description: Unsupported test workflow.",
                f"input_csv_path: {SAMPLE_CSV_PATH}",
                "output_json_path: artifacts/unsupported/output.json",
                "requires_human_approval: false",
            ]
        ),
        encoding="utf-8",
    )

    with pytest.raises(UnsupportedWorkflowError, match="unsupported_workflow"):
        run_workflow_from_manifest_path(manifest_path)
