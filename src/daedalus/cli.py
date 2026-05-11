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
from daedalus.domains.readysetrentables_reviews.theme_summary_comparison import (
    compare_review_theme_summary_markdown,
)
from daedalus.domains.readysetrentables_reviews.source_extraction_evaluator import (
    evaluate_rsr_source_extract_json,
)
from daedalus.domains.readysetrentables_reviews.theme_summary_evaluator import (
    evaluate_review_theme_summary_markdown,
)
from daedalus.domains.readysetrentables_reviews.theme_summary_input_builder import (
    build_review_theme_summary_input,
)
from daedalus.domains.readysetrentables_reviews.workflow import (
    run_review_normalization_workflow,
)
from daedalus.evaluation import (
    write_evaluation_comparison_report_json,
    write_evaluation_comparison_report_markdown,
    write_evaluation_report_json,
    write_evaluation_report_markdown,
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
from daedalus.model_clients.client import ModelClient
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

import logging

logger = logging.getLogger(__name__)


def main(argv: Sequence[str] | None = None) -> int:
    """Run the Daedalus CLI and return a process exit code."""
    parser = _build_parser()
    args = parser.parse_args(argv)
    configure_logging(args.log_level)

    if args.command == "normalize-reviews":
        logger.info(f"Starting normalize-reviews with input={args.input} output={args.output}")
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
        logger.info(f"Starting run-review-graph with input={args.input} output={args.output}")
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
            logger.info(f"Starting run-workflow with manifest={args.manifest}")
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

        logger.info(f"Inspecting workflow run {args.run_id}")
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

    if args.command == "record-evaluation-report-artifact":
        try:
            artifact_record = _record_evaluation_report_artifact(
                run_id=args.run_id,
                artifact_path=args.path,
            )
        except (FileNotFoundError, ValueError, WorkflowPersistenceError) as exc:
            parser.error(str(exc))

        print(
            "Recorded evaluation report artifact "
            f"run_id={artifact_record.run_id} "
            f"artifact_type={artifact_record.artifact_type.value} "
            f"artifact_path={artifact_record.artifact_path}"
        )
        return 0

    if args.command == "record-evaluation-comparison-report-artifact":
        try:
            artifact_record = _record_evaluation_comparison_report_artifact(
                run_id=args.run_id,
                artifact_path=args.path,
            )
        except (FileNotFoundError, ValueError, WorkflowPersistenceError) as exc:
            parser.error(str(exc))

        print(
            "Recorded evaluation comparison report artifact "
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

    if args.command == "summarize-review-themes-ollama":
        connection = None
        try:
            if (args.persist_invocation or args.persist_artifact) and args.run_id is None:
                parser.error("--persist-invocation or --persist-artifact requires --run-id")
            run_id = args.run_id or uuid4()
            batch = load_review_batch_json(args.input)
            input_data = build_review_theme_summary_input(
                run_id=run_id,
                batch=batch,
                max_representative_reviews=args.max_representative_reviews,
            )
            ollama_settings = OllamaModelClientSettings(
                enabled=True,
                base_url=args.base_url,
                model_name=args.model,
                request_timeout_seconds=args.timeout_seconds,
            )
            model_client: ModelClient = OllamaModelClient(settings=ollama_settings)
            if args.persist_invocation or args.persist_artifact:
                connection = connect_postgres(load_postgres_settings())
            if args.persist_invocation:
                assert connection is not None
                repository = ModelInvocationRepository(connection)
                recorder = ModelInvocationRecorder(repository)
                model_client = RecordingModelClient(
                    inner_client=model_client,
                    recorder=recorder,
                    agent_name="review_theme_summary_agent",
                    output_artifact_path=args.output,
                )
            agent = ReviewThemeSummaryAgent(
                model_client=model_client,
                model_provider=ModelProvider.OLLAMA,
                model_name=args.model,
            )
            theme_summary_result = agent.summarize(input_data)
            write_review_theme_summary_markdown(
                result=theme_summary_result,
                output_path=args.output,
            )
            if args.persist_artifact:
                assert connection is not None
                artifact_record = ArtifactRecord.create(
                    run_id=run_id,
                    artifact_type=ArtifactType.REVIEW_THEME_SUMMARY,
                    artifact_path=args.output,
                )
                ArtifactRepository(connection).save(artifact_record)
            if connection is not None:
                connection.commit()
        except (FileNotFoundError, ValueError, OllamaModelClientError) as exc:
            if connection is not None:
                connection.rollback()
                connection.close()
            parser.error(str(exc))
        except Exception:
            if connection is not None:
                connection.rollback()
                connection.close()
            msg = "Failed to persist Ollama summary metadata"
            parser.error(msg)
        else:
            if connection is not None:
                connection.close()

        print(
            "Wrote Ollama review theme summary "
            f"run_id={theme_summary_result.run_id} "
            f"output={args.output} "
            f"provider={theme_summary_result.model_provider.value} "
            f"model_name={theme_summary_result.model_name} "
            f"total_tokens={theme_summary_result.total_tokens} "
            f"estimated_cost_usd={theme_summary_result.estimated_cost_usd} "
            f"artifact_persisted={'yes' if args.persist_artifact else 'no'} "
            f"invocation_persisted={'yes' if args.persist_invocation else 'no'}"
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

    if args.command == "evaluate-review-theme-summary":
        output_json_path = args.output_json
        output_md_path = args.output_md
        if output_json_path is None and output_md_path is None:
            output_json_path = _default_evaluation_json_path(args.summary)

        report = evaluate_review_theme_summary_markdown(
            summary_path=args.summary,
            run_id=args.run_id,
        )
        written_paths: list[Path] = []
        if output_json_path is not None:
            written_paths.append(
                write_evaluation_report_json(
                    report=report,
                    output_path=output_json_path,
                )
            )
        if output_md_path is not None:
            written_paths.append(
                write_evaluation_report_markdown(
                    report=report,
                    output_path=output_md_path,
                )
            )

        print(
            "Wrote review theme summary evaluation "
            f"target_name={report.target_name} "
            f"passed={report.passed} "
            f"failed_count={report.failed_count} "
            f"warning_count={report.warning_count} "
            f"error_count={report.error_count} "
            f"outputs={','.join(str(path) for path in written_paths)}"
        )
        return 0

    if args.command == "evaluate-rsr-source-extract":
        source_extract_output_json = args.output_json
        source_extract_output_md = args.output_md
        if source_extract_output_json is None and source_extract_output_md is None:
            source_extract_output_json = _default_evaluation_json_path(args.source_extract)

        source_extract_report = evaluate_rsr_source_extract_json(
            source_extract_path=args.source_extract,
            run_id=args.run_id,
        )
        source_extract_written_paths: list[Path] = []
        if source_extract_output_json is not None:
            source_extract_written_paths.append(
                write_evaluation_report_json(
                    report=source_extract_report,
                    output_path=source_extract_output_json,
                )
            )
        if source_extract_output_md is not None:
            source_extract_written_paths.append(
                write_evaluation_report_markdown(
                    report=source_extract_report,
                    output_path=source_extract_output_md,
                )
            )

        print(
            "Wrote rsr source extract evaluation "
            f"target_name={source_extract_report.target_name} "
            f"passed={source_extract_report.passed} "
            f"failed_count={source_extract_report.failed_count} "
            f"warning_count={source_extract_report.warning_count} "
            f"error_count={source_extract_report.error_count} "
            f"outputs={','.join(str(path) for path in source_extract_written_paths)}"
        )
        return 0

    if args.command == "compare-review-theme-summaries":
        output_json_path = args.output_json
        output_md_path = args.output_md
        if output_json_path is None and output_md_path is None:
            output_json_path = _default_comparison_json_path(args.candidate)

        comparison_report = compare_review_theme_summary_markdown(
            baseline_path=args.baseline,
            candidate_path=args.candidate,
            baseline_report_id=args.baseline_report_id,
            candidate_report_id=args.candidate_report_id,
        )
        comparison_written_paths: list[Path] = []
        if output_json_path is not None:
            comparison_written_paths.append(
                write_evaluation_comparison_report_json(
                    report=comparison_report,
                    output_path=output_json_path,
                )
            )
        if output_md_path is not None:
            comparison_written_paths.append(
                write_evaluation_comparison_report_markdown(
                    report=comparison_report,
                    output_path=output_md_path,
                )
            )

        print(
            "Wrote review theme summary comparison "
            f"target_name={comparison_report.target_name} "
            f"passed={comparison_report.passed} "
            f"different_count={comparison_report.different_count} "
            f"improved_count={comparison_report.improved_count} "
            f"regressed_count={comparison_report.regressed_count} "
            f"inconclusive_count={comparison_report.inconclusive_count} "
            f"outputs={','.join(str(path) for path in comparison_written_paths)}"
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

        logger.info(
            f"Listing recent workflow runs with limit={args.limit} domain={args.domain} status={args.status}"
        )
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

    record_evaluation_report_artifact = subparsers.add_parser(
        "record-evaluation-report-artifact",
        help="Record an evaluation report artifact for a persisted workflow run.",
    )
    record_evaluation_report_artifact.add_argument(
        "--run-id",
        required=True,
        type=_uuid_arg,
        help="Workflow run UUID to attach the evaluation report artifact to.",
    )
    record_evaluation_report_artifact.add_argument(
        "--path",
        required=True,
        type=Path,
        help="Path to an existing evaluation report artifact.",
    )

    record_evaluation_comparison_report_artifact = subparsers.add_parser(
        "record-evaluation-comparison-report-artifact",
        help="Record an evaluation comparison report artifact for a persisted workflow run.",
    )
    record_evaluation_comparison_report_artifact.add_argument(
        "--run-id",
        required=True,
        type=_uuid_arg,
        help="Workflow run UUID to attach the evaluation comparison report artifact to.",
    )
    record_evaluation_comparison_report_artifact.add_argument(
        "--path",
        required=True,
        type=Path,
        help="Path to an existing evaluation comparison report artifact.",
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

    summarize_review_themes_ollama = subparsers.add_parser(
        "summarize-review-themes-ollama",
        help="Run the review theme summary agent explicitly with local Ollama.",
    )
    summarize_review_themes_ollama.add_argument(
        "--input",
        required=True,
        type=Path,
        help="Path to a normalized reviews JSON artifact.",
    )
    summarize_review_themes_ollama.add_argument(
        "--output",
        required=True,
        type=Path,
        help="Path where the Ollama review theme summary markdown should be written.",
    )
    summarize_review_themes_ollama.add_argument(
        "--model",
        required=True,
        help="Local Ollama model name to use for the review theme summary.",
    )
    summarize_review_themes_ollama.add_argument(
        "--base-url",
        default="http://localhost:11434",
        help="Local Ollama base URL.",
    )
    summarize_review_themes_ollama.add_argument(
        "--timeout-seconds",
        default=60.0,
        type=_positive_float_arg,
        help="Timeout in seconds for the local Ollama request.",
    )
    summarize_review_themes_ollama.add_argument(
        "--run-id",
        default=None,
        type=_uuid_arg,
        help="Optional workflow run UUID to associate with the summary.",
    )
    summarize_review_themes_ollama.add_argument(
        "--max-representative-reviews",
        default=5,
        type=_non_negative_int_arg,
        help="Maximum number of representative review texts to include in compact input.",
    )
    summarize_review_themes_ollama.add_argument(
        "--persist-invocation",
        action="store_true",
        help="Persist the Ollama model invocation metadata for an existing --run-id.",
    )
    summarize_review_themes_ollama.add_argument(
        "--persist-artifact",
        action="store_true",
        help="Persist the generated review theme summary artifact for an existing --run-id.",
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

    evaluate_review_theme_summary = subparsers.add_parser(
        "evaluate-review-theme-summary",
        help="Evaluate a review_theme_summary.md artifact with deterministic local checks.",
    )
    evaluate_review_theme_summary.add_argument(
        "--summary",
        required=True,
        type=Path,
        help="Path to a review_theme_summary.md artifact.",
    )
    evaluate_review_theme_summary.add_argument(
        "--run-id",
        default=None,
        type=_uuid_arg,
        help="Optional workflow run UUID expected in the summary artifact.",
    )
    evaluate_review_theme_summary.add_argument(
        "--output-json",
        default=None,
        type=Path,
        help="Optional path for the JSON evaluation report artifact.",
    )
    evaluate_review_theme_summary.add_argument(
        "--output-md",
        default=None,
        type=Path,
        help="Optional path for the Markdown evaluation report artifact.",
    )

    evaluate_rsr_source_extract = subparsers.add_parser(
        "evaluate-rsr-source-extract",
        help="Evaluate an rsr_source_extract.json artifact with deterministic local checks.",
    )
    evaluate_rsr_source_extract.add_argument(
        "--source-extract",
        required=True,
        type=Path,
        help="Path to an rsr_source_extract.json artifact.",
    )
    evaluate_rsr_source_extract.add_argument(
        "--run-id",
        default=None,
        type=_uuid_arg,
        help="Optional workflow run UUID to associate with the evaluation report.",
    )
    evaluate_rsr_source_extract.add_argument(
        "--output-json",
        default=None,
        type=Path,
        help="Optional path for the JSON evaluation report artifact.",
    )
    evaluate_rsr_source_extract.add_argument(
        "--output-md",
        default=None,
        type=Path,
        help="Optional path for the Markdown evaluation report artifact.",
    )

    compare_review_theme_summaries = subparsers.add_parser(
        "compare-review-theme-summaries",
        help="Compare two review_theme_summary.md artifacts with deterministic local checks.",
    )
    compare_review_theme_summaries.add_argument(
        "--baseline",
        required=True,
        type=Path,
        help="Path to the baseline review_theme_summary.md artifact.",
    )
    compare_review_theme_summaries.add_argument(
        "--candidate",
        required=True,
        type=Path,
        help="Path to the candidate review_theme_summary.md artifact.",
    )
    compare_review_theme_summaries.add_argument(
        "--baseline-report-id",
        default=None,
        type=_uuid_arg,
        help="Optional UUID of the baseline evaluation report.",
    )
    compare_review_theme_summaries.add_argument(
        "--candidate-report-id",
        default=None,
        type=_uuid_arg,
        help="Optional UUID of the candidate evaluation report.",
    )
    compare_review_theme_summaries.add_argument(
        "--output-json",
        default=None,
        type=Path,
        help="Optional path for the JSON comparison report artifact.",
    )
    compare_review_theme_summaries.add_argument(
        "--output-md",
        default=None,
        type=Path,
        help="Optional path for the Markdown comparison report artifact.",
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


def _record_evaluation_report_artifact(
    *,
    run_id: UUID,
    artifact_path: Path,
) -> ArtifactRecord:
    if not artifact_path.is_file():
        msg = f"Evaluation report artifact path does not exist: {artifact_path}"
        raise FileNotFoundError(msg)

    settings = load_postgres_settings()
    connection = connect_postgres(settings)
    try:
        artifact_record = ArtifactRecord.create(
            run_id=run_id,
            artifact_type=ArtifactType.EVALUATION_REPORT,
            artifact_path=artifact_path,
        )
        ArtifactRepository(connection).save(artifact_record)
        connection.commit()
    except Exception as exc:
        connection.rollback()
        msg = "Failed to record evaluation report artifact"
        raise WorkflowPersistenceError(msg) from exc
    finally:
        connection.close()

    return artifact_record


def _record_evaluation_comparison_report_artifact(
    *,
    run_id: UUID,
    artifact_path: Path,
) -> ArtifactRecord:
    if not artifact_path.is_file():
        msg = f"Evaluation comparison report artifact path does not exist: {artifact_path}"
        raise FileNotFoundError(msg)

    settings = load_postgres_settings()
    connection = connect_postgres(settings)
    try:
        artifact_record = ArtifactRecord.create(
            run_id=run_id,
            artifact_type=ArtifactType.EVALUATION_COMPARISON_REPORT,
            artifact_path=artifact_path,
        )
        ArtifactRepository(connection).save(artifact_record)
        connection.commit()
    except Exception as exc:
        connection.rollback()
        msg = "Failed to record evaluation comparison report artifact"
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


def _default_evaluation_json_path(summary_path: Path) -> Path:
    return summary_path.with_name(f"{summary_path.stem}.evaluation.json")


def _default_comparison_json_path(candidate_path: Path) -> Path:
    return candidate_path.with_name(f"{candidate_path.stem}.comparison.json")


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
