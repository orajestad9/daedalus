from pathlib import Path

import pytest

from daedalus.orchestrator.workflow_router import (
    UnsupportedWorkflowError,
    WorkflowApprovalRequiredError,
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
    assert result.approval_required is False
    assert result.approved is False


def test_run_workflow_from_manifest_requires_approval(tmp_path: Path) -> None:
    manifest_path = _write_readysetrentables_manifest(
        tmp_path,
        requires_human_approval=True,
    )

    with pytest.raises(WorkflowApprovalRequiredError, match="requires human approval"):
        run_workflow_from_manifest_path(manifest_path)


def test_run_workflow_from_approved_manifest_succeeds(tmp_path: Path) -> None:
    manifest_path = _write_readysetrentables_manifest(
        tmp_path,
        requires_human_approval=True,
    )

    result = run_workflow_from_manifest_path(manifest_path, approved=True)

    assert result.output_json_path.is_file()
    assert result.metadata_json_path.is_file()
    assert result.summary_markdown_path.is_file()
    assert result.approval_required is True
    assert result.approved is True

    summary = result.summary_markdown_path.read_text(encoding="utf-8")
    assert "Approval required: True" in summary
    assert "Approved: True" in summary


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


def _write_readysetrentables_manifest(
    tmp_path: Path,
    *,
    requires_human_approval: bool,
) -> Path:
    output_path = tmp_path / "normalized_reviews.json"
    manifest_path = tmp_path / "readysetrentables.yaml"
    manifest_path.write_text(
        "\n".join(
            [
                "workflow_name: readysetrentables_review_normalization",
                "domain: readysetrentables_reviews",
                "description: Approval gate test workflow.",
                f"input_csv_path: {SAMPLE_CSV_PATH}",
                f"output_json_path: {output_path}",
                f"requires_human_approval: {str(requires_human_approval).lower()}",
            ]
        ),
        encoding="utf-8",
    )
    return manifest_path
