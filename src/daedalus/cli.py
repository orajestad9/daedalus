"""Command-line entry point for Daedalus.

The CLI is intentionally thin: it parses user intent, configures process-level
logging, and delegates workflow execution to domain or orchestrator functions.
Routing and approval enforcement live outside this module so future automation
can reuse the same behavior without shelling out to the CLI.
"""

import argparse
from collections.abc import Sequence
from decimal import Decimal
from pathlib import Path
from uuid import UUID, uuid4

from daedalus.config import load_postgres_settings
from daedalus.domains.readysetrentables_reviews.artifacts import load_review_batch_json
from daedalus.domains.readysetrentables_reviews.graph_workflow import (
    run_readysetrentables_review_graph,
)
from daedalus.domains.readysetrentables_reviews.theme_summary_agent import (
    ReviewThemeSummaryAgent,
)
from daedalus.domains.readysetrentables_reviews.theme_summary_artifacts import (
    write_review_theme_summary_markdown,
)
from daedalus.domains.readysetrentables_reviews.theme_summary_input_builder import (
    build_review_theme_summary_input,
)
from daedalus.domains.readysetrentables_reviews.workflow import (
    run_review_normalization_workflow,
)
from daedalus.memory.artifact_repository import ArtifactRepository
from daedalus.memory.model_invocation_repository import ModelInvocationRepository
from daedalus.memory.migrations import apply_migrations
from daedalus.memory.postgres import connect_postgres
from daedalus.memory.workflow_persistence import (
    WorkflowPersistenceError,
    WorkflowRunNotFoundError,
    load_recent_workflow_runs,
    load_workflow_run_details,
    persist_review_normalization_workflow_result,
)
from daedalus.memory.workflow_run_repository import (
    MAX_LIST_RECENT_LIMIT,
    MIN_LIST_RECENT_LIMIT,
)
from daedalus.model_clients.fake import FakeModelClient
from daedalus.model_clients.invocation_recorder import ModelInvocationRecorder
from daedalus.model_clients.ollama import OllamaModelClient, OllamaModelClientError
from daedalus.model_clients.ollama_settings import OllamaModelClientSettings
from daedalus.model_clients.recording import RecordingModelClient
from daedalus.model_clients.types import ModelBudget, ModelProvider, ModelRequest, ModelResponse
from daedalus.orchestrator.artifact_record import ArtifactRecord
from daedalus.orchestrator.artifact_type import ArtifactType
from daedalus.orchestrator.run_inspection_formatter import format_run_inspection
from daedalus.orchestrator.run_record import WorkflowRunRecord
from daedalus.orchestrator.workflow_router import (
    UnsupportedWorkflowError,
    WorkflowApprovalRequiredError,
    run_workflow_from_manifest_path,
)
from daedalus.shared.workflow_manifest import WorkflowExecutionEngine
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

    if args.command == "run-review-graph":
        graph_result = run_readysetrentables_review_graph(
            input_csv_path=args.input,
            output_json_path=args.output,
        )
        review_count = graph_result.batch.review_count if graph_result.batch is not None else 0
        print(
            f"Ran review graph run_id={graph_result.run_id} "
            f"review_count={review_count} "
            f"output={graph_result.output_json_path} "
            f"metadata={graph_result.metadata_json_path} "
            f"summary={graph_result.summary_markdown_path} "
            f"run_record={graph_result.run_record_json_path} "
            f"steps={len(graph_result.steps)}"
        )
        return 0

    if args.command == "run-workflow":
        try:
            result = run_workflow_from_manifest_path(
                args.manifest,
                approved=args.approve,
                execution_engine_override=args.execution_engine,
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

        print(
            format_run_inspection(
                record=details.run_record,
                artifacts=details.artifact_records,
                steps=details.step_records,
                model_invocations=details.model_invocation_records,
            )
        )
        return 0

    if args.command == "record-fake-model-invocation":
        try:
            response = _record_fake_model_invocation(args.run_id)
        except (ValueError, WorkflowPersistenceError) as exc:
            parser.error(str(exc))

        print(
            "Recorded fake model invocation "
            f"provider={response.provider.value} "
            f"model_name={response.model_name} "
            f"total_tokens={response.total_tokens} "
            f"estimated_cost_usd={response.estimated_cost_usd}"
        )
        return 0

    if args.command == "record-review-theme-summary-artifact":
        try:
            artifact_record = _record_review_theme_summary_artifact(
                run_id=args.run_id,
                artifact_path=args.path,
            )
        except (FileNotFoundError, ValueError, WorkflowPersistenceError) as exc:
            parser.error(str(exc))

        print(
            "Recorded review theme summary artifact "
            f"run_id={artifact_record.run_id} "
            f"artifact_type={artifact_record.artifact_type.value} "
            f"artifact_path={artifact_record.artifact_path}"
        )
        return 0

    if args.command == "summarize-review-themes-fake":
        try:
            run_id = args.run_id or uuid4()
            batch = load_review_batch_json(args.input)
            input_data = build_review_theme_summary_input(
                run_id=run_id,
                batch=batch,
                max_representative_reviews=args.max_representative_reviews,
            )
            agent = ReviewThemeSummaryAgent(model_client=FakeModelClient())
            theme_summary_result = agent.summarize(input_data)
            write_review_theme_summary_markdown(
                result=theme_summary_result,
                output_path=args.output,
            )
        except (FileNotFoundError, ValueError) as exc:
            parser.error(str(exc))

        print(
            "Wrote fake review theme summary "
            f"run_id={theme_summary_result.run_id} "
            f"output={args.output} "
            f"provider={theme_summary_result.model_provider.value} "
            f"model_name={theme_summary_result.model_name} "
            f"total_tokens={theme_summary_result.total_tokens} "
            f"estimated_cost_usd={theme_summary_result.estimated_cost_usd}"
        )
        return 0

    if args.command == "ollama-smoke-check":
        try:
            response = _run_ollama_smoke_check(
                model_name=args.model,
                base_url=args.base_url,
                timeout_seconds=args.timeout_seconds,
                prompt=args.prompt,
            )
        except (ValueError, OllamaModelClientError) as exc:
            parser.error(str(exc))

        print(
            "Ollama smoke check succeeded "
            f"provider={response.provider.value} "
            f"model_name={response.model_name} "
            f"input_tokens={response.input_tokens} "
            f"output_tokens={response.output_tokens} "
            f"total_tokens={response.total_tokens} "
            f"estimated_cost_usd={response.estimated_cost_usd}"
        )
        return 0

    if args.command == "list-runs":
        try:
            runs = load_recent_workflow_runs(
                limit=args.limit,
                domain=args.domain,
                status=args.status,
            )
        except (ValueError, WorkflowPersistenceError) as exc:
            parser.error(str(exc))

        print(_format_workflow_run_list(runs))
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

    run_review_graph = subparsers.add_parser(
        "run-review-graph",
        help="Run the ReadySetRentables review normalization LangGraph workflow.",
    )
    run_review_graph.add_argument(
        "--input",
        required=True,
        type=Path,
        help="Path to the Airbnb review CSV input.",
    )
    run_review_graph.add_argument(
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
    run_workflow.add_argument(
        "--execution-engine",
        default=None,
        type=_execution_engine_arg,
        metavar="{deterministic,langgraph}",
        help="Override the manifest execution engine for this run.",
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

    record_fake_model_invocation = subparsers.add_parser(
        "record-fake-model-invocation",
        help="Record one local fake model invocation for a persisted workflow run.",
    )
    record_fake_model_invocation.add_argument(
        "--run-id",
        required=True,
        type=_uuid_arg,
        help="Workflow run UUID to attach the fake model invocation to.",
    )

    record_review_theme_summary_artifact = subparsers.add_parser(
        "record-review-theme-summary-artifact",
        help="Record a review theme summary markdown artifact for a persisted workflow run.",
    )
    record_review_theme_summary_artifact.add_argument(
        "--run-id",
        required=True,
        type=_uuid_arg,
        help="Workflow run UUID to attach the review theme summary artifact to.",
    )
    record_review_theme_summary_artifact.add_argument(
        "--path",
        required=True,
        type=Path,
        help="Path to an existing review theme summary markdown artifact.",
    )

    summarize_review_themes_fake = subparsers.add_parser(
        "summarize-review-themes-fake",
        help="Run the review theme summary agent locally with FakeModelClient.",
    )
    summarize_review_themes_fake.add_argument(
        "--input",
        required=True,
        type=Path,
        help="Path to a normalized reviews JSON artifact.",
    )
    summarize_review_themes_fake.add_argument(
        "--output",
        required=True,
        type=Path,
        help="Path where the fake review theme summary markdown should be written.",
    )
    summarize_review_themes_fake.add_argument(
        "--run-id",
        default=None,
        type=_uuid_arg,
        help="Optional workflow run UUID to associate with the summary.",
    )
    summarize_review_themes_fake.add_argument(
        "--max-representative-reviews",
        default=5,
        type=_non_negative_int_arg,
        help="Maximum number of representative review texts to include in fake input.",
    )

    ollama_smoke_check = subparsers.add_parser(
        "ollama-smoke-check",
        help="Optionally test local Ollama connectivity without workflow wiring.",
    )
    ollama_smoke_check.add_argument(
        "--model",
        required=True,
        help="Local Ollama model name to use for the smoke check.",
    )
    ollama_smoke_check.add_argument(
        "--base-url",
        default="http://localhost:11434",
        help="Local Ollama base URL.",
    )
    ollama_smoke_check.add_argument(
        "--timeout-seconds",
        default=30.0,
        type=_positive_float_arg,
        help="Timeout in seconds for the local Ollama request.",
    )
    ollama_smoke_check.add_argument(
        "--prompt",
        default="Reply with a short confirmation that local Ollama is reachable.",
        help="Synthetic prompt for the optional local smoke check.",
    )

    list_runs = subparsers.add_parser(
        "list-runs",
        help="List recent persisted workflow runs from Postgres.",
    )
    list_runs.add_argument(
        "--limit",
        default=10,
        type=_list_limit_arg,
        help="Maximum number of workflow runs to list.",
    )
    list_runs.add_argument(
        "--domain",
        default=None,
        help="Optional workflow domain filter.",
    )
    list_runs.add_argument(
        "--status",
        default=None,
        help="Optional workflow status filter.",
    )

    return parser


def _record_fake_model_invocation(run_id: UUID) -> ModelResponse:
    settings = load_postgres_settings()
    connection = connect_postgres(settings)
    try:
        repository = ModelInvocationRepository(connection)
        recorder = ModelInvocationRecorder(repository)
        client = RecordingModelClient(
            inner_client=FakeModelClient(output_text="fake local summary"),
            recorder=recorder,
            agent_name="fake_local_check",
            input_artifact_path=Path("artifacts/fake-model-input.txt"),
            output_artifact_path=Path("artifacts/fake-model-output.txt"),
        )
        request = ModelRequest(
            run_id=run_id,
            agent_name="fake_local_check",
            provider=ModelProvider.FAKE,
            model_name="fake-model",
            prompt_name="fake_review_theme_summary",
            prompt_version="v0",
            input_text="Synthetic local fake model check text.",
            input_artifact_path=Path("artifacts/fake-model-input.txt"),
            output_artifact_path=Path("artifacts/fake-model-output.txt"),
            budget=ModelBudget(
                max_input_tokens=100,
                max_output_tokens=100,
                max_total_tokens=200,
                max_estimated_cost_usd=Decimal("0.01"),
                allowed_providers=(ModelProvider.FAKE,),
            ),
        )
        response = client.complete(request)
        connection.commit()
    except Exception as exc:
        connection.rollback()
        msg = "Failed to record fake model invocation"
        raise WorkflowPersistenceError(msg) from exc
    finally:
        connection.close()

    return response


def _record_review_theme_summary_artifact(
    *,
    run_id: UUID,
    artifact_path: Path,
) -> ArtifactRecord:
    if not artifact_path.is_file():
        msg = f"Review theme summary artifact path does not exist: {artifact_path}"
        raise FileNotFoundError(msg)

    settings = load_postgres_settings()
    connection = connect_postgres(settings)
    try:
        artifact_record = ArtifactRecord.create(
            run_id=run_id,
            artifact_type=ArtifactType.REVIEW_THEME_SUMMARY,
            artifact_path=artifact_path,
        )
        ArtifactRepository(connection).save(artifact_record)
        connection.commit()
    except Exception as exc:
        connection.rollback()
        msg = "Failed to record review theme summary artifact"
        raise WorkflowPersistenceError(msg) from exc
    finally:
        connection.close()

    return artifact_record


def _run_ollama_smoke_check(
    *,
    model_name: str,
    base_url: str,
    timeout_seconds: float,
    prompt: str,
) -> ModelResponse:
    settings = OllamaModelClientSettings(
        enabled=True,
        base_url=base_url,
        model_name=model_name,
        request_timeout_seconds=timeout_seconds,
    )
    client = OllamaModelClient(settings=settings)
    request = ModelRequest(
        run_id=uuid4(),
        agent_name="ollama_smoke_check",
        provider=ModelProvider.OLLAMA,
        model_name=model_name,
        prompt_name="ollama_smoke_check",
        prompt_version="v0",
        input_text=prompt,
        input_artifact_path=Path("prompts/ollama_smoke_check/v0"),
    )
    return client.complete(request)


def _uuid_arg(value: str) -> UUID:
    try:
        return UUID(value)
    except ValueError as exc:
        msg = f"Invalid UUID: {value}"
        raise argparse.ArgumentTypeError(msg) from exc


def _execution_engine_arg(value: str) -> WorkflowExecutionEngine:
    try:
        return WorkflowExecutionEngine(value)
    except ValueError as exc:
        supported = ", ".join(engine.value for engine in WorkflowExecutionEngine)
        msg = f"Invalid execution engine: {value}. Supported values: {supported}"
        raise argparse.ArgumentTypeError(msg) from exc


def _list_limit_arg(value: str) -> int:
    try:
        limit = int(value)
    except ValueError as exc:
        msg = f"Invalid limit: {value}"
        raise argparse.ArgumentTypeError(msg) from exc

    if limit < MIN_LIST_RECENT_LIMIT or limit > MAX_LIST_RECENT_LIMIT:
        msg = f"Limit must be between {MIN_LIST_RECENT_LIMIT} and {MAX_LIST_RECENT_LIMIT}"
        raise argparse.ArgumentTypeError(msg)

    return limit


def _non_negative_int_arg(value: str) -> int:
    try:
        parsed_value = int(value)
    except ValueError as exc:
        msg = f"Invalid integer: {value}"
        raise argparse.ArgumentTypeError(msg) from exc

    if parsed_value < 0:
        msg = f"Value must be non-negative: {value}"
        raise argparse.ArgumentTypeError(msg)

    return parsed_value


def _positive_float_arg(value: str) -> float:
    try:
        parsed_value = float(value)
    except ValueError as exc:
        msg = f"Invalid number: {value}"
        raise argparse.ArgumentTypeError(msg) from exc

    if parsed_value <= 0:
        msg = f"Value must be positive: {value}"
        raise argparse.ArgumentTypeError(msg)

    return parsed_value


def _format_workflow_run_list(runs: Sequence[WorkflowRunRecord]) -> str:
    if not runs:
        return "No workflow runs found."

    lines = ["Workflow runs:"]
    lines.extend(
        " | ".join(
            [
                f"run_id={run.run_id}",
                f"workflow_name={run.workflow_name}",
                f"domain={run.domain}",
                f"status={run.status.value}",
                f"duration_ms={run.duration_ms}",
                f"review_count={run.review_count}",
                f"completed_at_utc={run.completed_at_utc.isoformat()}",
            ]
        )
        for run in runs
    )
    return "\n".join(lines)


if __name__ == "__main__":
    raise SystemExit(main())
