"""Command-line entry point for Daedalus.

The CLI is intentionally thin: it parses user intent, configures process-level
logging, and delegates workflow execution to domain or orchestrator functions.
Routing and approval enforcement live outside this module so future automation
can reuse the same behavior without shelling out to the CLI.
"""

import argparse
from collections.abc import Sequence
from pathlib import Path
from uuid import UUID

from daedalus.config import load_postgres_settings
from daedalus.domains.readysetrentables_reviews.workflow import (
    run_review_normalization_workflow,
)
from daedalus.memory.migrations import apply_migrations
from daedalus.memory.workflow_persistence import (
    WorkflowPersistenceError,
    WorkflowRunDetails,
    WorkflowRunNotFoundError,
    load_workflow_run_details,
    persist_review_normalization_workflow_result,
)
from daedalus.orchestrator.workflow_router import (
    UnsupportedWorkflowError,
    WorkflowApprovalRequiredError,
    run_workflow_from_manifest_path,
)
from daedalus.telemetry.logging import configure_logging


def main(argv: Sequence[str] | None = None) -> int:
    """Run the Daedalus CLI and return a process exit code."""
    parser = _build_parser()
    args = parser.parse_args(argv)
    configure_logging(args.log_level)

    if args.command == "normalize-reviews":
        result = run_review_normalization_workflow(
            input_csv_path=args.input,
            output_json_path=args.output,
        )
        print(
            f"Normalized {result.review_count} reviews "
            f"to {result.output_json_path} "
            f"metadata={result.metadata_json_path} "
            f"summary={result.summary_markdown_path} "
            f"run_record={result.run_record_json_path} "
            f"run_id={result.run_id}"
        )
        return 0

    if args.command == "run-workflow":
        try:
            result = run_workflow_from_manifest_path(
                args.manifest,
                approved=args.approve,
            )
        except (UnsupportedWorkflowError, WorkflowApprovalRequiredError) as exc:
            parser.error(str(exc))
        persisted_artifact_count = None
        if args.persist:
            try:
                persisted_artifact_count = persist_review_normalization_workflow_result(result)
            except (ValueError, WorkflowPersistenceError) as exc:
                parser.error(str(exc))
        print(
            f"Ran workflow run_id={result.run_id} "
            f"review_count={result.review_count} "
            f"output={result.output_json_path} "
            f"metadata={result.metadata_json_path} "
            f"summary={result.summary_markdown_path} "
            f"run_record={result.run_record_json_path}"
        )
        if persisted_artifact_count is not None:
            print(
                f"Persisted workflow run {result.run_id} "
                f"with {persisted_artifact_count} artifact record(s)."
            )
        return 0

    if args.command == "migrate-db":
        try:
            settings = load_postgres_settings()
        except ValueError as exc:
            parser.error(str(exc))

        applied_migrations = apply_migrations(settings)
        print(f"Applied {len(applied_migrations)} migration files")
        return 0

    if args.command == "show-run":
        try:
            details = load_workflow_run_details(args.run_id)
        except (ValueError, WorkflowPersistenceError, WorkflowRunNotFoundError) as exc:
            parser.error(str(exc))

        print(_format_workflow_run_details(details))
        return 0

    parser.error("A command is required")


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="daedalus",
        description="Run deterministic Daedalus workflows.",
    )
    parser.add_argument(
        "--log-level",
        default="INFO",
        help="Logging level to use for Daedalus logs.",
    )
    subparsers = parser.add_subparsers(dest="command")

    normalize_reviews = subparsers.add_parser(
        "normalize-reviews",
        help="Normalize Airbnb review CSV data into a JSON artifact.",
    )
    normalize_reviews.add_argument(
        "--input",
        required=True,
        type=Path,
        help="Path to the Airbnb review CSV input.",
    )
    normalize_reviews.add_argument(
        "--output",
        required=True,
        type=Path,
        help="Path where the normalized JSON artifact should be written.",
    )

    run_workflow = subparsers.add_parser(
        "run-workflow",
        help="Run a workflow from a YAML manifest.",
    )
    run_workflow.add_argument(
        "--manifest",
        required=True,
        type=Path,
        help="Path to the workflow manifest YAML file.",
    )
    run_workflow.add_argument(
        "--approve",
        action="store_true",
        help="Confirm approval for workflows that require human approval.",
    )
    run_workflow.add_argument(
        "--persist",
        action="store_true",
        help="Persist completed workflow run and artifact records to Postgres.",
    )

    subparsers.add_parser(
        "migrate-db",
        help="Apply committed SQL migrations to Postgres.",
    )

    show_run = subparsers.add_parser(
        "show-run",
        help="Inspect a persisted workflow run from Postgres.",
    )
    show_run.add_argument(
        "--run-id",
        required=True,
        type=_uuid_arg,
        help="Workflow run UUID to inspect.",
    )

    return parser


def _uuid_arg(value: str) -> UUID:
    try:
        return UUID(value)
    except ValueError as exc:
        msg = f"Invalid UUID: {value}"
        raise argparse.ArgumentTypeError(msg) from exc


def _format_workflow_run_details(details: WorkflowRunDetails) -> str:
    run = details.run_record
    lines = [
        f"Workflow run {run.run_id}",
        f"workflow_name: {run.workflow_name}",
        f"domain: {run.domain}",
        f"status: {run.status.value}",
        f"started_at_utc: {run.started_at_utc.isoformat()}",
        f"completed_at_utc: {run.completed_at_utc.isoformat()}",
        f"review_count: {run.review_count}",
        f"approval_required: {run.approval_required}",
        f"approved: {run.approved}",
        f"source_input_path: {run.source_input_path}",
        f"output_artifact_path: {run.output_artifact_path}",
        f"metadata_artifact_path: {run.metadata_artifact_path}",
        f"summary_artifact_path: {run.summary_artifact_path}",
        f"run_record_artifact_path: {run.run_record_artifact_path}",
        "artifacts:",
    ]
    if not details.artifact_records:
        lines.append("- none")
    else:
        lines.extend(
            f"- {artifact.artifact_type.value}: {artifact.artifact_path}"
            for artifact in details.artifact_records
        )

    return "\n".join(lines)


if __name__ == "__main__":
    raise SystemExit(main())
