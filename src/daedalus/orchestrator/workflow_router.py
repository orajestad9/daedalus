"""Manifest-driven workflow routing for Daedalus.

The CLI, future jobs, API handlers, and agents should all call this layer rather
than owning routing decisions themselves. Keeping routing in the orchestrator
gives Daedalus one place to enforce platform rules such as approval gates and
unsupported-workflow failures.
"""

import logging
from pathlib import Path

from daedalus.domains.readysetrentables_reviews.graph_state import (
    ReadySetRentablesReviewGraphState,
)
from daedalus.domains.readysetrentables_reviews.graph_workflow import (
    run_readysetrentables_review_graph,
)
from daedalus.domains.readysetrentables_reviews.workflow import (
    ReviewNormalizationWorkflowResult,
    run_review_normalization_workflow,
)
from daedalus.orchestrator.workflow_identity import WorkflowDomain, WorkflowName
from daedalus.shared.workflow_manifest import (
    WorkflowExecutionEngine,
    WorkflowManifest,
    load_workflow_manifest,
)


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
        "Routing workflow manifest workflow_name=%s domain=%s execution_engine=%s manifest_path=%s",
        manifest.workflow_name,
        manifest.domain,
        manifest.execution_engine.value,
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

    result = _run_readysetrentables_review_manifest(manifest, approved=approved)
    logger.info(
        "Completed routed workflow run_id=%s workflow_name=%s domain=%s execution_engine=%s",
        result.run_id,
        manifest.workflow_name,
        manifest.domain,
        manifest.execution_engine.value,
    )
    return result


def _is_readysetrentables_review_manifest(manifest: WorkflowManifest) -> bool:
    return (
        manifest.workflow_name == WorkflowName.READYSETRENTABLES_REVIEW_NORMALIZATION
        or manifest.domain == WorkflowDomain.READYSETRENTABLES_REVIEWS
    )


def _run_readysetrentables_review_manifest(
    manifest: WorkflowManifest,
    *,
    approved: bool,
) -> ReviewNormalizationWorkflowResult:
    if manifest.execution_engine == WorkflowExecutionEngine.DETERMINISTIC:
        return run_review_normalization_workflow(
            input_csv_path=manifest.input_csv_path,
            output_json_path=manifest.output_json_path,
            approval_required=manifest.requires_human_approval,
            approved=approved,
        )

    if manifest.execution_engine == WorkflowExecutionEngine.LANGGRAPH:
        graph_state = run_readysetrentables_review_graph(
            input_csv_path=manifest.input_csv_path,
            output_json_path=manifest.output_json_path,
            approval_required=manifest.requires_human_approval,
            approved=approved,
        )
        return _review_result_from_graph_state(graph_state)

    msg = f"Unsupported execution engine: {manifest.execution_engine!r}"
    raise UnsupportedWorkflowError(msg)


def _review_result_from_graph_state(
    state: ReadySetRentablesReviewGraphState,
) -> ReviewNormalizationWorkflowResult:
    if state.batch is None:
        msg = "LangGraph review workflow did not produce a review batch."
        raise ValueError(msg)
    if state.metadata_json_path is None:
        msg = "LangGraph review workflow did not produce metadata_json_path."
        raise ValueError(msg)
    if state.summary_markdown_path is None:
        msg = "LangGraph review workflow did not produce summary_markdown_path."
        raise ValueError(msg)
    if state.run_record_json_path is None:
        msg = "LangGraph review workflow did not produce run_record_json_path."
        raise ValueError(msg)

    return ReviewNormalizationWorkflowResult(
        source_csv_path=state.input_csv_path,
        output_json_path=state.output_json_path,
        metadata_json_path=state.metadata_json_path,
        summary_markdown_path=state.summary_markdown_path,
        run_record_json_path=state.run_record_json_path,
        review_count=state.batch.review_count,
        run_id=state.run_id,
        approval_required=state.approval_required,
        approved=state.approved,
        steps=state.steps,
    )
