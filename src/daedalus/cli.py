import argparse
import json
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from uuid import UUID, uuid4

from pydantic import ValidationError

from daedalus.config import load_postgres_settings
from daedalus.domains.readysetrentables_reviews.artifacts import load_review_batch_json
from daedalus.domains.readysetrentables_reviews.graph_workflow import (
    run_readysetrentables_review_graph,
)
from daedalus.domains.readysetrentables_reviews.review_insight_input_builder import (
    build_review_insight_extraction_input_from_source_extract,
)
from daedalus.domains.readysetrentables_reviews.review_insight_agent import (
    ReviewInsightExtractionAgent,
)
from daedalus.domains.readysetrentables_reviews.review_insight_artifacts import (
    write_review_insights_json,
)
from daedalus.domains.readysetrentables_reviews.review_insight_evaluator import (
    evaluate_review_insights_json,
)
from daedalus.domains.readysetrentables_reviews.review_insight_models import (
    ReviewInsightExtractionInput,
    ReviewInsightExtractionResult,
)
from daedalus.domains.readysetrentables_reviews.review_insight_output_parser import (
    MODEL_OUTPUT_EMPTY_MESSAGE,
    MODEL_OUTPUT_INVALID_JSON_MESSAGE,
    MODEL_OUTPUT_NO_JSON_OBJECT_MESSAGE,
    MODEL_OUTPUT_SCHEMA_MESSAGE,
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
from daedalus.domains.readysetrentables_reviews.source_db_connection import (
    connect_rsr_source_postgres,
)
from daedalus.domains.readysetrentables_reviews.source_db_settings import (
    load_rsr_source_postgres_settings,
)
from daedalus.domains.readysetrentables_reviews.source_extraction_artifacts import (
    write_rsr_source_extract_json,
)
from daedalus.domains.readysetrentables_reviews.source_extraction_models import (
    RsrSourceExtractionRequest,
    RsrSourceExtractionResult,
)
from daedalus.domains.readysetrentables_reviews.source_readonly_repository import (
    RsrSourceReadOnlyRepository,
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
from daedalus.model_clients.ollama import (
    OLLAMA_REQUEST_TIMEOUT_MESSAGE,
    OllamaModelClient,
    OllamaModelClientError,
)
from daedalus.model_clients.ollama_settings import OllamaModelClientSettings
from daedalus.model_clients.recording import RecordingModelClient
from daedalus.model_clients.types import (
    ModelBudget,
    ModelInvocationStatus as ModelResponseStatus,
    ModelProvider,
    ModelRequest,
    ModelResponse,
)
from daedalus.orchestrator.artifact_record import ArtifactRecord
from daedalus.orchestrator.artifact_type import ArtifactType
from daedalus.orchestrator.run_lifecycle import utc_now
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

DEFAULT_RSR_SOURCE_EXTRACT_PATH = Path("artifacts/readysetrentables/rsr_source_extract.json")
DEFAULT_REVIEW_INSIGHT_INPUT_PATH = Path(
    "artifacts/readysetrentables/review_insight_extraction_input.json"
)
DEFAULT_REVIEW_INSIGHTS_PATH = Path("artifacts/readysetrentables/review_insights.json")
DEFAULT_RSR_REVIEW_INSIGHTS_OUTPUT_DIR = Path("artifacts/readysetrentables")


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

    if args.command == "record-review-insights-artifact":
        try:
            artifact_record = _record_review_insights_artifact(
                run_id=args.run_id,
                artifact_path=args.path,
            )
        except (FileNotFoundError, ValueError, WorkflowPersistenceError) as exc:
            parser.error(str(exc))

        print(
            "Recorded review insights artifact "
            f"run_id={artifact_record.run_id} "
            f"artifact_type={artifact_record.artifact_type.value} "
            f"artifact_path={artifact_record.artifact_path}"
        )
        return 0

    if args.command == "record-rsr-source-extract-artifact":
        try:
            artifact_record = _record_rsr_source_extract_artifact(
                run_id=args.run_id,
                artifact_path=args.path,
            )
        except (FileNotFoundError, ValueError, WorkflowPersistenceError) as exc:
            parser.error(str(exc))

        print(
            "Recorded RSR source extract artifact "
            f"run_id={artifact_record.run_id} "
            f"artifact_type={artifact_record.artifact_type.value} "
            f"artifact_path={artifact_record.artifact_path}"
        )
        return 0

    if args.command == "run-rsr-review-insights-pipeline":
        try:
            pipeline_result = _run_rsr_review_insights_pipeline(
                run_id=args.run_id,
                market_name=args.market_name,
                max_reviews=args.max_reviews,
                model_name=args.model,
                output_dir=args.output_dir,
                ollama_timeout_seconds=args.ollama_timeout_seconds,
                progress=print,
            )
        except (
            FileNotFoundError,
            ValueError,
            ValidationError,
            OllamaModelClientError,
            WorkflowPersistenceError,
        ) as exc:
            parser.error(str(exc))

        print(_format_rsr_review_insights_pipeline_summary(pipeline_result))
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

    if args.command == "extract-rsr-source-data":
        try:
            request = RsrSourceExtractionRequest(
                market_name=args.market_name,
                neighborhood_name=args.neighborhood_name,
                property_type=args.property_type,
                max_reviews=args.max_reviews,
            )
            rsr_source_settings = load_rsr_source_postgres_settings()
        except ValueError as exc:
            parser.error(str(exc))

        connection = None
        try:
            connection = connect_rsr_source_postgres(rsr_source_settings)
            rsr_source_repository = RsrSourceReadOnlyRepository(connection)
            source_extract_result = rsr_source_repository.extract_source_data(request=request)
            source_extract_path = write_rsr_source_extract_json(
                result=source_extract_result,
                output_path=args.output_json,
            )
        except Exception:
            parser.error("Failed to extract RSR source data.")
        finally:
            if connection is not None:
                close = getattr(connection, "close", None)
                if callable(close):
                    close()

        # Success output stays aggregate-only because real source artifacts can
        # contain private review text and should remain local/untracked.
        summary_parts = [
            "Wrote RSR source extract",
            f"output={source_extract_path}",
            f"market_name={request.market_name}",
        ]
        if request.neighborhood_name is not None:
            summary_parts.append(f"neighborhood_name={request.neighborhood_name}")
        if request.property_type is not None:
            summary_parts.append(f"property_type={request.property_type}")
        summary_parts.extend(
            [
                f"review_count={len(source_extract_result.reviews)}",
                f"listing_count={len(source_extract_result.listings)}",
                "neighborhood_present="
                f"{str(source_extract_result.neighborhood is not None).lower()}",
            ]
        )
        print(" ".join(summary_parts))
        return 0

    if args.command == "build-review-insight-input":
        try:
            source_extract_result = _load_rsr_source_extract_json(args.source_extract)
            review_insight_input = build_review_insight_extraction_input_from_source_extract(
                source_extract=source_extract_result,
                run_id=args.run_id,
                source_artifact_path=args.source_artifact_path,
                max_representative_reviews=args.max_representative_reviews,
            )
            review_insight_input_path = _write_review_insight_input_json(
                review_insight_input=review_insight_input,
                output_path=args.output_json,
            )
        except (FileNotFoundError, ValueError) as exc:
            parser.error(str(exc))

        # The generated input artifact may contain representative review text;
        # print counts and filters, not artifact contents.
        summary_parts = [
            "Wrote review insight extraction input",
            f"output={review_insight_input_path}",
        ]
        if review_insight_input.market_name is not None:
            summary_parts.append(f"market_name={review_insight_input.market_name}")
        if review_insight_input.neighborhood_name is not None:
            summary_parts.append(f"neighborhood_name={review_insight_input.neighborhood_name}")
        if review_insight_input.property_type is not None:
            summary_parts.append(f"property_type={review_insight_input.property_type}")
        summary_parts.extend(
            [
                f"review_count={review_insight_input.review_count}",
                f"representative_review_count={len(review_insight_input.representative_reviews)}",
            ]
        )
        if review_insight_input.average_rating is not None:
            summary_parts.append(f"average_rating={review_insight_input.average_rating}")
        summary_parts.append(f"rating_category_count={len(review_insight_input.rating_categories)}")
        print(" ".join(summary_parts))
        return 0

    if args.command == "extract-review-insights-ollama":
        try:
            if args.record_model_invocation and args.run_id is None:
                parser.error("--record-model-invocation requires --run-id")
            review_insight_input = _load_review_insight_input_json(args.input_json)
            ollama_settings = _ollama_settings_for_review_insights(
                model_name=args.model,
                base_url=args.ollama_base_url,
                timeout_seconds=args.timeout_seconds,
            )
        except (FileNotFoundError, ValueError, ValidationError) as exc:
            parser.error(str(exc))

        try:
            model_client = OllamaModelClient(settings=ollama_settings)
            review_insight_agent = ReviewInsightExtractionAgent(
                model_client=model_client,
                model_name=args.model,
                prompt_name="readysetrentables_review_insight_extraction",
                prompt_version="v0",
            )
            review_insight_result = review_insight_agent.run(input_data=review_insight_input)
            review_insights_path = write_review_insights_json(
                result=review_insight_result,
                output_path=args.output_json,
            )
            if args.record_model_invocation:
                _record_review_insight_model_invocation(
                    run_id=args.run_id,
                    result=review_insight_result,
                    input_artifact_path=args.input_json,
                    output_artifact_path=review_insights_path,
                )
        except (ValueError, OllamaModelClientError) as exc:
            parser.error(_safe_review_insights_ollama_failure_message(exc))
        except WorkflowPersistenceError as exc:
            parser.error(str(exc))
        except Exception:
            parser.error("Failed to extract review insights with local Ollama.")

        summary_parts = [
            "Wrote Ollama review insights",
            f"output={review_insights_path}",
            f"provider={review_insight_result.provider.value}",
            f"model_name={review_insight_result.model_name}",
            f"prompt_name={review_insight_result.prompt_name}",
            f"prompt_version={review_insight_result.prompt_version}",
            f"theme_count={len(review_insight_result.themes)}",
            f"strengths_count={len(review_insight_result.strengths)}",
            f"risks_count={len(review_insight_result.risks)}",
            f"guest_expectations_count={len(review_insight_result.guest_expectations)}",
        ]
        if review_insight_result.input_tokens is not None:
            summary_parts.append(f"input_tokens={review_insight_result.input_tokens}")
        if review_insight_result.output_tokens is not None:
            summary_parts.append(f"output_tokens={review_insight_result.output_tokens}")
        if review_insight_result.total_tokens is not None:
            summary_parts.append(f"total_tokens={review_insight_result.total_tokens}")
        if review_insight_result.estimated_cost_usd is not None:
            summary_parts.append(f"estimated_cost_usd={review_insight_result.estimated_cost_usd}")
        print(" ".join(summary_parts))
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

    if args.command == "evaluate-review-insights":
        review_insights_output_json = args.output_json
        review_insights_output_md = args.output_md
        if review_insights_output_json is None and review_insights_output_md is None:
            review_insights_output_json = _default_evaluation_json_path(args.review_insights)

        review_insights_report = evaluate_review_insights_json(
            insights_path=args.review_insights,
            run_id=args.run_id,
        )
        review_insights_written_paths: list[Path] = []
        if review_insights_output_json is not None:
            review_insights_written_paths.append(
                write_evaluation_report_json(
                    report=review_insights_report,
                    output_path=review_insights_output_json,
                )
            )
        if review_insights_output_md is not None:
            review_insights_written_paths.append(
                write_evaluation_report_markdown(
                    report=review_insights_report,
                    output_path=review_insights_output_md,
                )
            )

        print(
            "Wrote review insights evaluation "
            f"target_name={review_insights_report.target_name} "
            f"passed={review_insights_report.passed} "
            f"failed_count={review_insights_report.failed_count} "
            f"warning_count={review_insights_report.warning_count} "
            f"error_count={review_insights_report.error_count} "
            f"outputs={','.join(str(path) for path in review_insights_written_paths)}"
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

    record_review_insights_artifact = subparsers.add_parser(
        "record-review-insights-artifact",
        help="Record a review_insights.json artifact for a persisted workflow run.",
    )
    record_review_insights_artifact.add_argument(
        "--run-id",
        required=True,
        type=_uuid_arg,
        help="Workflow run UUID to attach the review insights artifact to.",
    )
    record_review_insights_artifact.add_argument(
        "--path",
        required=True,
        type=Path,
        help="Path to an existing review_insights.json artifact.",
    )

    record_rsr_source_extract_artifact = subparsers.add_parser(
        "record-rsr-source-extract-artifact",
        help="Record an RSR source extract JSON artifact for a persisted workflow run.",
    )
    record_rsr_source_extract_artifact.add_argument(
        "--run-id",
        required=True,
        type=_uuid_arg,
        help="Workflow run UUID to attach the RSR source extract artifact to.",
    )
    record_rsr_source_extract_artifact.add_argument(
        "--path",
        required=True,
        type=Path,
        help="Path to an existing rsr_source_extract.json artifact.",
    )

    run_rsr_review_insights_pipeline = subparsers.add_parser(
        "run-rsr-review-insights-pipeline",
        help="Run the manual ReadySetRentables review insights demo path.",
    )
    run_rsr_review_insights_pipeline.add_argument(
        "--run-id",
        required=True,
        type=_uuid_arg,
        help="Existing workflow run UUID to attach artifacts and model invocation to.",
    )
    run_rsr_review_insights_pipeline.add_argument(
        "--market-name",
        required=True,
        help="RSR market name to extract.",
    )
    run_rsr_review_insights_pipeline.add_argument(
        "--max-reviews",
        default=10,
        type=_positive_int_arg,
        help="Maximum number of source reviews to extract and pass to review insights.",
    )
    run_rsr_review_insights_pipeline.add_argument(
        "--model",
        required=True,
        help="Local Ollama model name to use for review insight extraction.",
    )
    run_rsr_review_insights_pipeline.add_argument(
        "--output-dir",
        default=DEFAULT_RSR_REVIEW_INSIGHTS_OUTPUT_DIR,
        type=Path,
        help="Directory where pipeline artifacts should be written.",
    )
    run_rsr_review_insights_pipeline.add_argument(
        "--ollama-timeout-seconds",
        default=None,
        type=_positive_int_arg,
        help="Optional positive integer timeout in seconds for local Ollama requests.",
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

    extract_rsr_source_data = subparsers.add_parser(
        "extract-rsr-source-data",
        help="Manually extract sanitized ReadySetRentables source data from the RSR source DB.",
    )
    extract_rsr_source_data.add_argument(
        "--market-name",
        required=True,
        help="RSR market name to extract.",
    )
    extract_rsr_source_data.add_argument(
        "--neighborhood-name",
        default=None,
        help="Optional RSR neighborhood name filter.",
    )
    extract_rsr_source_data.add_argument(
        "--property-type",
        default=None,
        help="Optional RSR property type filter.",
    )
    extract_rsr_source_data.add_argument(
        "--max-reviews",
        default=None,
        type=_positive_int_arg,
        help="Optional maximum number of reviews to extract.",
    )
    extract_rsr_source_data.add_argument(
        "--output-json",
        default=DEFAULT_RSR_SOURCE_EXTRACT_PATH,
        type=Path,
        help="Path where rsr_source_extract.json should be written.",
    )

    build_review_insight_input = subparsers.add_parser(
        "build-review-insight-input",
        help="Build ReviewInsightExtractionInput JSON from an rsr_source_extract.json artifact.",
    )
    build_review_insight_input.add_argument(
        "--source-extract",
        required=True,
        type=Path,
        help="Path to an existing rsr_source_extract.json artifact.",
    )
    build_review_insight_input.add_argument(
        "--run-id",
        default=None,
        type=_uuid_arg,
        help="Optional workflow run UUID for the review insight input.",
    )
    build_review_insight_input.add_argument(
        "--source-artifact-path",
        default=None,
        type=Path,
        help="Optional artifact path to preserve in the review insight input.",
    )
    build_review_insight_input.add_argument(
        "--max-representative-reviews",
        default=25,
        type=_non_negative_int_arg,
        help="Maximum number of representative review texts to include.",
    )
    build_review_insight_input.add_argument(
        "--output-json",
        default=DEFAULT_REVIEW_INSIGHT_INPUT_PATH,
        type=Path,
        help="Path where review_insight_extraction_input.json should be written.",
    )

    extract_review_insights_ollama = subparsers.add_parser(
        "extract-review-insights-ollama",
        help="Manually extract review insights with explicit local Ollama.",
    )
    extract_review_insights_ollama.add_argument(
        "--input-json",
        required=True,
        type=Path,
        help="Path to a review_insight_extraction_input.json artifact.",
    )
    extract_review_insights_ollama.add_argument(
        "--model",
        required=True,
        help="Local Ollama model name to use for review insight extraction.",
    )
    extract_review_insights_ollama.add_argument(
        "--output-json",
        default=DEFAULT_REVIEW_INSIGHTS_PATH,
        type=Path,
        help="Path where review_insights.json should be written.",
    )
    extract_review_insights_ollama.add_argument(
        "--ollama-base-url",
        default=None,
        help="Optional local Ollama base URL. Defaults to Ollama settings/env behavior.",
    )
    extract_review_insights_ollama.add_argument(
        "--timeout-seconds",
        default=None,
        type=_positive_float_arg,
        help="Optional timeout in seconds for the local Ollama request.",
    )
    extract_review_insights_ollama.add_argument(
        "--ollama-timeout-seconds",
        default=None,
        dest="timeout_seconds",
        type=_positive_int_arg,
        help="Optional positive integer timeout in seconds for local Ollama requests.",
    )
    extract_review_insights_ollama.add_argument(
        "--run-id",
        default=None,
        type=_uuid_arg,
        help="Workflow run UUID to attach persisted model invocation metadata to.",
    )
    extract_review_insights_ollama.add_argument(
        "--record-model-invocation",
        action="store_true",
        help="Persist safe Ollama model invocation metadata after writing review_insights.json.",
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

    evaluate_review_insights = subparsers.add_parser(
        "evaluate-review-insights",
        help="Evaluate a review_insights.json artifact with deterministic local checks.",
    )
    evaluate_review_insights.add_argument(
        "--review-insights",
        required=True,
        type=Path,
        help="Path to a review_insights.json artifact.",
    )
    evaluate_review_insights.add_argument(
        "--run-id",
        default=None,
        type=_uuid_arg,
        help="Optional workflow run UUID to associate with the evaluation report.",
    )
    evaluate_review_insights.add_argument(
        "--output-json",
        default=None,
        type=Path,
        help="Optional path for the JSON evaluation report artifact.",
    )
    evaluate_review_insights.add_argument(
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


def _record_review_insights_artifact(
    *,
    run_id: UUID,
    artifact_path: Path,
) -> ArtifactRecord:
    if not artifact_path.is_file():
        msg = f"Review insights artifact path does not exist: {artifact_path}"
        raise FileNotFoundError(msg)

    settings = load_postgres_settings()
    connection = connect_postgres(settings)
    try:
        artifact_record = ArtifactRecord.create(
            run_id=run_id,
            artifact_type=ArtifactType.REVIEW_INSIGHTS,
            artifact_path=artifact_path,
        )
        ArtifactRepository(connection).save(artifact_record)
        connection.commit()
    except Exception as exc:
        connection.rollback()
        msg = "Failed to record review insights artifact"
        raise WorkflowPersistenceError(msg) from exc
    finally:
        connection.close()

    return artifact_record


def _record_review_insight_model_invocation(
    *,
    run_id: UUID,
    result: ReviewInsightExtractionResult,
    input_artifact_path: Path,
    output_artifact_path: Path,
) -> None:
    started_at_utc = utc_now()
    completed_at_utc = started_at_utc
    request = ModelRequest(
        run_id=run_id,
        agent_name="review_insight_extraction_agent",
        provider=result.provider,
        model_name=result.model_name,
        prompt_name=result.prompt_name,
        prompt_version=result.prompt_version,
        input_artifact_path=input_artifact_path,
        output_artifact_path=output_artifact_path,
    )
    response = ModelResponse(
        invocation_id=uuid4(),
        status=ModelResponseStatus.COMPLETED,
        provider=result.provider,
        model_name=result.model_name,
        input_tokens=result.input_tokens,
        output_tokens=result.output_tokens,
        total_tokens=result.total_tokens,
        estimated_cost_usd=result.estimated_cost_usd,
        output_artifact_path=output_artifact_path,
    )

    settings = load_postgres_settings()
    connection = connect_postgres(settings)
    try:
        recorder = ModelInvocationRecorder(ModelInvocationRepository(connection))
        recorder.record_success(
            request=request,
            response=response,
            started_at_utc=started_at_utc,
            completed_at_utc=completed_at_utc,
        )
        connection.commit()
    except Exception as exc:
        connection.rollback()
        msg = "Failed to record review insight model invocation"
        raise WorkflowPersistenceError(msg) from exc
    finally:
        connection.close()


def _record_rsr_source_extract_artifact(
    *,
    run_id: UUID,
    artifact_path: Path,
) -> ArtifactRecord:
    if not artifact_path.is_file():
        msg = f"RSR source extract artifact path does not exist: {artifact_path}"
        raise FileNotFoundError(msg)

    settings = load_postgres_settings()
    connection = connect_postgres(settings)
    try:
        artifact_record = ArtifactRecord.create(
            run_id=run_id,
            artifact_type=ArtifactType.RSR_SOURCE_EXTRACT,
            artifact_path=artifact_path,
        )
        ArtifactRepository(connection).save(artifact_record)
        connection.commit()
    except Exception as exc:
        connection.rollback()
        msg = "Failed to record RSR source extract artifact"
        raise WorkflowPersistenceError(msg) from exc
    finally:
        connection.close()

    return artifact_record


@dataclass(frozen=True)
class RsrReviewInsightsPipelineResult:
    run_id: UUID
    market_name: str
    max_reviews: int
    model_name: str
    output_dir: Path
    source_extract_path: Path
    review_insight_input_path: Path
    review_insights_path: Path
    evaluation_json_path: Path
    evaluation_md_path: Path
    review_count: int
    listing_count: int
    representative_review_count: int
    theme_count: int
    strengths_count: int
    risks_count: int
    guest_expectations_count: int
    ollama_timeout_seconds: int | None
    input_tokens: int | None
    output_tokens: int | None
    total_tokens: int | None
    estimated_cost_usd: Decimal | None
    evaluation_passed: bool
    evaluation_failed_count: int
    evaluation_warning_count: int
    evaluation_error_count: int


def _run_rsr_review_insights_pipeline(
    *,
    run_id: UUID,
    market_name: str,
    max_reviews: int,
    model_name: str,
    output_dir: Path,
    ollama_timeout_seconds: int | None,
    progress: Callable[[str], None] | None = None,
) -> RsrReviewInsightsPipelineResult:
    output_dir.mkdir(parents=True, exist_ok=True)
    source_extract_path = output_dir / "rsr_source_extract.json"
    review_insight_input_path = output_dir / "review_insight_extraction_input.json"
    review_insights_path = output_dir / "review_insights.json"
    evaluation_json_path = output_dir / "review_insights.evaluation.json"
    evaluation_md_path = output_dir / "review_insights.evaluation.md"
    _emit_progress(
        progress,
        f"Prepared RSR review insights pipeline run_id={run_id} output_dir={output_dir}",
    )

    request = RsrSourceExtractionRequest(
        market_name=market_name,
        max_reviews=max_reviews,
    )
    rsr_source_settings = load_rsr_source_postgres_settings()
    source_connection = None
    try:
        source_connection = connect_rsr_source_postgres(rsr_source_settings)
        rsr_source_repository = RsrSourceReadOnlyRepository(source_connection)
        source_extract_result = rsr_source_repository.extract_source_data(request=request)
        write_rsr_source_extract_json(
            result=source_extract_result,
            output_path=source_extract_path,
        )
    except Exception as exc:
        msg = "Failed to extract RSR source data."
        raise ValueError(msg) from exc
    finally:
        if source_connection is not None:
            close = getattr(source_connection, "close", None)
            if callable(close):
                close()
    _emit_progress(
        progress,
        "Wrote RSR source extract "
        f"output={source_extract_path} "
        f"market_name={market_name} "
        f"max_reviews={max_reviews} "
        f"review_count={len(source_extract_result.reviews)} "
        f"listing_count={len(source_extract_result.listings)}",
    )

    review_insight_input = build_review_insight_extraction_input_from_source_extract(
        source_extract=source_extract_result,
        run_id=run_id,
        source_artifact_path=source_extract_path,
        max_representative_reviews=max_reviews,
    )
    _write_review_insight_input_json(
        review_insight_input=review_insight_input,
        output_path=review_insight_input_path,
    )
    _emit_progress(
        progress,
        "Wrote review insight extraction input "
        f"output={review_insight_input_path} "
        f"representative_review_count={len(review_insight_input.representative_reviews)}",
    )

    try:
        model_client = OllamaModelClient(
            settings=_ollama_settings_for_review_insights(
                model_name=model_name,
                base_url=None,
                timeout_seconds=ollama_timeout_seconds,
            )
        )
        review_insight_agent = ReviewInsightExtractionAgent(
            model_client=model_client,
            model_name=model_name,
            prompt_name="readysetrentables_review_insight_extraction",
            prompt_version="v0",
        )
        review_insight_result = review_insight_agent.run(input_data=review_insight_input)
        write_review_insights_json(
            result=review_insight_result,
            output_path=review_insights_path,
        )
    except (ValueError, OllamaModelClientError) as exc:
        raise ValueError(_safe_review_insights_ollama_failure_message(exc)) from exc
    except Exception as exc:
        msg = "Failed to extract review insights with local Ollama."
        raise ValueError(msg) from exc
    insight_progress_parts = [
        "Wrote Ollama review insights",
        f"output={review_insights_path}",
        f"model_name={model_name}",
        f"theme_count={len(review_insight_result.themes)}",
        f"strengths_count={len(review_insight_result.strengths)}",
        f"risks_count={len(review_insight_result.risks)}",
        f"guest_expectations_count={len(review_insight_result.guest_expectations)}",
    ]
    _append_usage_parts(
        input_tokens=review_insight_result.input_tokens,
        output_tokens=review_insight_result.output_tokens,
        total_tokens=review_insight_result.total_tokens,
        estimated_cost_usd=review_insight_result.estimated_cost_usd,
        summary_parts=insight_progress_parts,
    )
    _emit_progress(progress, " ".join(insight_progress_parts))

    evaluation_report = evaluate_review_insights_json(
        insights_path=review_insights_path,
        run_id=run_id,
    )
    write_evaluation_report_json(
        report=evaluation_report,
        output_path=evaluation_json_path,
    )
    write_evaluation_report_markdown(
        report=evaluation_report,
        output_path=evaluation_md_path,
    )
    _emit_progress(
        progress,
        "Wrote review insights evaluation "
        f"output_json={evaluation_json_path} "
        f"output_md={evaluation_md_path} "
        f"passed={evaluation_report.passed} "
        f"failed_count={evaluation_report.failed_count} "
        f"warning_count={evaluation_report.warning_count} "
        f"error_count={evaluation_report.error_count}",
    )

    _record_review_insights_artifact(
        run_id=run_id,
        artifact_path=review_insights_path,
    )
    _record_evaluation_report_artifact(
        run_id=run_id,
        artifact_path=evaluation_json_path,
    )
    _record_review_insight_model_invocation(
        run_id=run_id,
        result=review_insight_result,
        input_artifact_path=review_insight_input_path,
        output_artifact_path=review_insights_path,
    )
    _emit_progress(
        progress,
        "Recorded pipeline metadata "
        f"run_id={run_id} "
        "artifacts=review_insights,evaluation_report "
        "model_invocation=ollama",
    )

    return RsrReviewInsightsPipelineResult(
        run_id=run_id,
        market_name=market_name,
        max_reviews=max_reviews,
        model_name=model_name,
        output_dir=output_dir,
        source_extract_path=source_extract_path,
        review_insight_input_path=review_insight_input_path,
        review_insights_path=review_insights_path,
        evaluation_json_path=evaluation_json_path,
        evaluation_md_path=evaluation_md_path,
        review_count=len(source_extract_result.reviews),
        listing_count=len(source_extract_result.listings),
        representative_review_count=len(review_insight_input.representative_reviews),
        theme_count=len(review_insight_result.themes),
        strengths_count=len(review_insight_result.strengths),
        risks_count=len(review_insight_result.risks),
        guest_expectations_count=len(review_insight_result.guest_expectations),
        ollama_timeout_seconds=ollama_timeout_seconds,
        input_tokens=review_insight_result.input_tokens,
        output_tokens=review_insight_result.output_tokens,
        total_tokens=review_insight_result.total_tokens,
        estimated_cost_usd=review_insight_result.estimated_cost_usd,
        evaluation_passed=evaluation_report.passed,
        evaluation_failed_count=evaluation_report.failed_count,
        evaluation_warning_count=evaluation_report.warning_count,
        evaluation_error_count=evaluation_report.error_count,
    )


def _emit_progress(progress: Callable[[str], None] | None, message: str) -> None:
    if progress is not None:
        progress(message)


def _format_rsr_review_insights_pipeline_summary(
    result: RsrReviewInsightsPipelineResult,
) -> str:
    summary_parts = [
        "RSR review insights pipeline complete",
        f"run_id={result.run_id}",
        f"model={result.model_name}",
        f"output_dir={result.output_dir}",
        f"source_extract={result.source_extract_path}",
        f"review_insight_input={result.review_insight_input_path}",
        f"review_insights={result.review_insights_path}",
        f"evaluation_json={result.evaluation_json_path}",
        f"evaluation_md={result.evaluation_md_path}",
        f"review_count={result.review_count}",
        f"representative_review_count={result.representative_review_count}",
        f"theme_count={result.theme_count}",
        f"passed={result.evaluation_passed}",
        f"failed_count={result.evaluation_failed_count}",
        f"warning_count={result.evaluation_warning_count}",
        f"error_count={result.evaluation_error_count}",
        "artifacts_recorded=review_insights,evaluation_report",
        "model_invocation_recorded=yes",
    ]
    if result.ollama_timeout_seconds is not None:
        summary_parts.append(f"ollama_timeout_seconds={result.ollama_timeout_seconds}")
    _append_usage_summary_parts(result, summary_parts)
    return " ".join(summary_parts)


def _append_usage_summary_parts(
    result: RsrReviewInsightsPipelineResult,
    summary_parts: list[str],
) -> None:
    _append_usage_parts(
        input_tokens=result.input_tokens,
        output_tokens=result.output_tokens,
        total_tokens=result.total_tokens,
        estimated_cost_usd=result.estimated_cost_usd,
        summary_parts=summary_parts,
    )


def _append_usage_parts(
    *,
    input_tokens: int | None,
    output_tokens: int | None,
    total_tokens: int | None,
    estimated_cost_usd: Decimal | None,
    summary_parts: list[str],
) -> None:
    if input_tokens is not None:
        summary_parts.append(f"input_tokens={input_tokens}")
    if output_tokens is not None:
        summary_parts.append(f"output_tokens={output_tokens}")
    if total_tokens is not None:
        summary_parts.append(f"total_tokens={total_tokens}")
    if estimated_cost_usd is not None:
        summary_parts.append(f"estimated_cost_usd={estimated_cost_usd}")


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


def _load_rsr_source_extract_json(source_extract_path: Path) -> RsrSourceExtractionResult:
    if not source_extract_path.is_file():
        msg = f"RSR source extract artifact path does not exist: {source_extract_path}"
        raise FileNotFoundError(msg)

    try:
        parsed = json.loads(source_extract_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        msg = "RSR source extract artifact is not valid JSON."
        raise ValueError(msg) from exc

    try:
        return RsrSourceExtractionResult.model_validate(parsed)
    except ValidationError as exc:
        msg = "RSR source extract artifact does not match the expected schema."
        raise ValueError(msg) from exc


def _write_review_insight_input_json(
    *,
    review_insight_input: ReviewInsightExtractionInput,
    output_path: Path,
) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.loads(review_insight_input.model_dump_json())
    output_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return output_path


def _load_review_insight_input_json(input_path: Path) -> ReviewInsightExtractionInput:
    if not input_path.is_file():
        msg = f"Review insight extraction input path does not exist: {input_path}"
        raise FileNotFoundError(msg)

    try:
        parsed = json.loads(input_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        msg = "Review insight extraction input is not valid JSON."
        raise ValueError(msg) from exc

    try:
        return ReviewInsightExtractionInput.model_validate(parsed)
    except ValidationError as exc:
        msg = "Review insight extraction input does not match the expected schema."
        raise ValueError(msg) from exc


def _ollama_settings_for_review_insights(
    *,
    model_name: str,
    base_url: str | None,
    timeout_seconds: float | None,
) -> OllamaModelClientSettings:
    settings = OllamaModelClientSettings.from_env()
    values = settings.model_dump()
    values.update(
        {
            "enabled": True,
            "model_name": model_name,
        }
    )
    update: dict[str, object] = {}
    if base_url is not None:
        update["base_url"] = base_url
    if timeout_seconds is not None:
        update["request_timeout_seconds"] = timeout_seconds
    values.update(update)
    return OllamaModelClientSettings.model_validate(values)


def _safe_review_insights_ollama_failure_message(exc: Exception) -> str:
    reason = _safe_review_insights_ollama_failure_reason(exc)
    return f"Failed to extract review insights with local Ollama: {reason}"


def _safe_review_insights_ollama_failure_reason(exc: Exception) -> str:
    # Map parser/provider failures to fixed public messages so raw model output
    # and source-derived review text never leak through argparse errors.
    message = str(exc)
    if message == MODEL_OUTPUT_EMPTY_MESSAGE:
        return "model output was empty."
    if message == MODEL_OUTPUT_NO_JSON_OBJECT_MESSAGE:
        return "model output did not contain a valid JSON object."
    if message == MODEL_OUTPUT_INVALID_JSON_MESSAGE:
        return "model output JSON could not be parsed."
    if message == MODEL_OUTPUT_SCHEMA_MESSAGE:
        return "model output did not match the expected review insight JSON schema."
    if isinstance(exc, OllamaModelClientError):
        if message == OLLAMA_REQUEST_TIMEOUT_MESSAGE:
            return "Ollama request timed out."
        return "local Ollama request failed."
    return "model output could not be converted to review insights."


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


def _positive_int_arg(value: str) -> int:
    try:
        parsed_value = int(value)
    except ValueError as exc:
        msg = f"Invalid integer: {value}"
        raise argparse.ArgumentTypeError(msg) from exc

    if parsed_value <= 0:
        msg = f"Value must be positive: {value}"
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
