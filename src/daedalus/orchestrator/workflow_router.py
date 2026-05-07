from pathlib import Path

from daedalus.domains.readysetrentables_reviews.workflow import (
    ReviewNormalizationWorkflowResult,
    run_review_normalization_workflow,
)
from daedalus.shared.workflow_manifest import WorkflowManifest, load_workflow_manifest


READYSETRENTABLES_REVIEW_WORKFLOW_NAME = "readysetrentables_review_normalization"
READYSETRENTABLES_REVIEW_DOMAIN = "readysetrentables_reviews"


class UnsupportedWorkflowError(ValueError):
    """Raised when a workflow manifest cannot be routed to an implementation."""


class WorkflowApprovalRequiredError(PermissionError):
    """Raised when a workflow manifest requires human approval before execution."""


def run_workflow_from_manifest_path(
    manifest_path: Path,
    *,
    approved: bool = False,
) -> ReviewNormalizationWorkflowResult:
    """Load a workflow manifest and route it to the matching workflow implementation."""
    manifest = load_workflow_manifest(manifest_path)
    if manifest.requires_human_approval and not approved:
        msg = (
            "Workflow requires human approval before execution: "
            f"workflow_name={manifest.workflow_name!r} manifest_path={manifest_path}"
        )
        raise WorkflowApprovalRequiredError(msg)

    if not _is_readysetrentables_review_manifest(manifest):
        msg = (
            "Unsupported workflow manifest: "
            f"workflow_name={manifest.workflow_name!r} domain={manifest.domain!r}"
        )
        raise UnsupportedWorkflowError(msg)

    return run_review_normalization_workflow(
        input_csv_path=manifest.input_csv_path,
        output_json_path=manifest.output_json_path,
        approval_required=manifest.requires_human_approval,
        approved=approved,
    )


def _is_readysetrentables_review_manifest(manifest: WorkflowManifest) -> bool:
    return (
        manifest.workflow_name == READYSETRENTABLES_REVIEW_WORKFLOW_NAME
        or manifest.domain == READYSETRENTABLES_REVIEW_DOMAIN
    )
