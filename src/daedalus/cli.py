import argparse
from collections.abc import Sequence
from pathlib import Path

from daedalus.domains.readysetrentables_reviews.workflow import (
    run_review_normalization_workflow,
)
from daedalus.shared.workflow_manifest import WorkflowManifest, load_workflow_manifest
from daedalus.telemetry.logging import configure_logging


READYSETRENTABLES_REVIEW_WORKFLOW_NAME = "readysetrentables_review_normalization"
READYSETRENTABLES_REVIEW_DOMAIN = "readysetrentables_reviews"


def main(argv: Sequence[str] | None = None) -> int:
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
            f"run_id={result.run_id}"
        )
        return 0

    if args.command == "run-workflow":
        manifest = load_workflow_manifest(args.manifest)
        if not _is_readysetrentables_review_manifest(manifest):
            parser.error(
                "Unsupported workflow manifest: "
                f"workflow_name={manifest.workflow_name!r} domain={manifest.domain!r}"
            )

        result = run_review_normalization_workflow(
            input_csv_path=manifest.input_csv_path,
            output_json_path=manifest.output_json_path,
        )
        print(
            f"Ran workflow run_id={result.run_id} "
            f"review_count={result.review_count} "
            f"output={result.output_json_path} "
            f"metadata={result.metadata_json_path} "
            f"summary={result.summary_markdown_path}"
        )
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

    return parser


def _is_readysetrentables_review_manifest(manifest: WorkflowManifest) -> bool:
    return (
        manifest.workflow_name == READYSETRENTABLES_REVIEW_WORKFLOW_NAME
        or manifest.domain == READYSETRENTABLES_REVIEW_DOMAIN
    )


if __name__ == "__main__":
    raise SystemExit(main())
