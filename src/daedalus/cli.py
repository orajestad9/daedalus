"""Command-line entry point for Daedalus.

The CLI is intentionally thin: it parses user intent, configures process-level
logging, and delegates workflow execution to domain or orchestrator functions.
Routing and approval enforcement live outside this module so future automation
can reuse the same behavior without shelling out to the CLI.
"""

import argparse
from collections.abc import Sequence
from pathlib import Path

from daedalus.config import load_postgres_settings
from daedalus.domains.readysetrentables_reviews.workflow import (
    run_review_normalization_workflow,
)
from daedalus.memory.migrations import apply_migrations
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
        print(
            f"Ran workflow run_id={result.run_id} "
            f"review_count={result.review_count} "
            f"output={result.output_json_path} "
            f"metadata={result.metadata_json_path} "
            f"summary={result.summary_markdown_path} "
            f"run_record={result.run_record_json_path}"
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

    subparsers.add_parser(
        "migrate-db",
        help="Apply committed SQL migrations to Postgres.",
    )

    return parser


if __name__ == "__main__":
    raise SystemExit(main())
