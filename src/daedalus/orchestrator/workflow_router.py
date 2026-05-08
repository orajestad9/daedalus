"""Manifest-driven workflow routing for Daedalus.

The CLI, future jobs, API handlers, and agents should all call this layer rather
than owning routing decisions themselves. Keeping routing in the orchestrator
gives Daedalus one place to enforce platform rules such as approval gates and
unsupported-workflow failures.
"""

import logging
from pathlib import Path

from daedalus.domains.readysetrentables_reviews.workflow import (
    ReviewNormalizationWorkflowResult,
    run_review_normalization_workflow,
)
from daedalus.orchestrator.workflow_identity import WorkflowDomain, WorkflowName
from daedalus.shared.workflow_manifest import WorkflowManifest, load_workflow_manifest


logger = logging.getLogger(__name__)


class UnsupportedWorkflowError(ValueError):
    """Raised when a manifest names a workflow Daedalus cannot run yet."""


class WorkflowApprovalRequiredError(PermissionError):
    """Raised when a manifest requires approval and no approval was supplied."""


def run_workflow_from_manifest_path(
    manifest_path: Path,
    *,
    approved: bool = False,
) -> ReviewNormalizationWorkflowResult:
    """Load a manifest, enforce platform gates, and run the routed workflow.

    Approval is checked before workflow routing so a manifest cannot trigger
    domain work until the human-approved intent is explicit. Unsupported
    manifests fail loudly because silent no-ops would hide bad automation,
    mistyped manifests, or incomplete Phase 1 routing work.
    """
    logger.info("Loading workflow manifest manifest_path=%s", manifest_path)
    manifest = load_workflow_manifest(manifest_path)
    logger.info(
        "Routing workflow manifest workflow_name=%s domain=%s manifest_path=%s",
        manifest.workflow_name,
        manifest.domain,
        manifest_path,
    )
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

    result = run_review_normalization_workflow(
        input_csv_path=manifest.input_csv_path,
        output_json_path=manifest.output_json_path,
        approval_required=manifest.requires_human_approval,
        approved=approved,
    )
    logger.info(
        "Completed routed workflow run_id=%s workflow_name=%s domain=%s",
        result.run_id,
        manifest.workflow_name,
        manifest.domain,
    )
    return result


def _is_readysetrentables_review_manifest(manifest: WorkflowManifest) -> bool:
    return (
        manifest.workflow_name == WorkflowName.READYSETRENTABLES_REVIEW_NORMALIZATION
        or manifest.domain == WorkflowDomain.READYSETRENTABLES_REVIEWS
    )
