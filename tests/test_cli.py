import json
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any, cast
from uuid import UUID, uuid4

import pytest

from daedalus.cli import main
from daedalus.config import PostgresSettings
from daedalus.domains.readysetrentables_reviews.artifacts import write_review_batch_json
from daedalus.domains.readysetrentables_reviews.ingestion import load_airbnb_reviews_csv
from daedalus.domains.readysetrentables_reviews.review_insight_models import (
    ReviewInsightExtractionInput,
    ReviewInsightExtractionResult,
    ReviewInsightTheme,
)
from daedalus.domains.readysetrentables_reviews.source_db_settings import (
    RsrSourcePostgresSettings,
)
from daedalus.domains.readysetrentables_reviews.source_extraction_models import (
    RsrSourceExtractionRequest,
    RsrSourceExtractionResult,
    RsrSourceListingContext,
    RsrSourceNeighborhoodContext,
    RsrSourceReviewRecord,
)
from daedalus.domains.readysetrentables_reviews.workflow import (
    ReviewNormalizationWorkflowResult,
)
from daedalus.memory.workflow_persistence import (
    WorkflowPersistenceError,
    WorkflowRunDetails,
    WorkflowRunNotFoundError,
)
from daedalus.model_clients.invocation_record import (
    ModelInvocationRecord,
    ModelInvocationStatus,
)
from daedalus.model_clients.ollama import (
    OLLAMA_REQUEST_TIMEOUT_MESSAGE,
    OllamaModelClientError,
)
from daedalus.model_clients.ollama_settings import OllamaModelClientSettings
from daedalus.model_clients.types import (
    ModelInvocationStatus as ModelResponseStatus,
    ModelProvider,
    ModelResponse,
)
from daedalus.orchestrator.artifact_record import ArtifactRecord
from daedalus.orchestrator.artifact_type import ArtifactType
from daedalus.orchestrator.run_record import WorkflowRunRecord
from daedalus.orchestrator.status import WorkflowStatus
from daedalus.orchestrator.step_record import WorkflowStepRecord
from daedalus.shared.workflow_manifest import WorkflowExecutionEngine


SAMPLE_CSV_PATH = Path("sample_data/readysetrentables_reviews/airbnb_reviews_sample.csv")
SAMPLE_MANIFEST_PATH = Path("workflows/readysetrentables_review_normalization.yaml")


def test_cli_help_includes_record_review_insights_artifact(
    capsys: pytest.CaptureFixture[str],
) -> None:
    with pytest.raises(SystemExit) as exc_info:
        main(["--help"])

    output = capsys.readouterr().out
    assert exc_info.value.code == 0
    assert "record-review-insights-artifact" in output


def test_normalize_reviews_command_succeeds_with_sample_csv(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    output_path = tmp_path / "normalized_reviews.json"

    exit_code = main(
        [
            "normalize-reviews",
            "--input",
            str(SAMPLE_CSV_PATH),
            "--output",
            str(output_path),
        ]
    )

    assert exit_code == 0
    assert output_path.is_file()
    assert (tmp_path / "normalized_reviews.metadata.json").is_file()
    assert (tmp_path / "normalized_reviews.summary.md").is_file()
    assert (tmp_path / "normalized_reviews.run.json").is_file()

    output = capsys.readouterr().out
    assert "metadata=" in output
    assert "summary=" in output
    assert "run_record=" in output
    assert "run_id=" in output


def test_run_review_graph_command_succeeds_with_sample_csv(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    output_path = tmp_path / "normalized_reviews.json"

    exit_code = main(
        [
            "run-review-graph",
            "--input",
            str(SAMPLE_CSV_PATH),
            "--output",
            str(output_path),
        ]
    )

    assert exit_code == 0
    assert output_path.is_file()
    assert (tmp_path / "normalized_reviews.metadata.json").is_file()
    assert (tmp_path / "normalized_reviews.summary.md").is_file()
    assert (tmp_path / "normalized_reviews.run.json").is_file()
    assert (tmp_path / "review_theme_summary.md").is_file()

    output = capsys.readouterr().out
    assert "Ran review graph" in output
    assert "run_id=" in output
    assert "review_count=8" in output
    assert f"output={output_path}" in output
    assert f"metadata={tmp_path / 'normalized_reviews.metadata.json'}" in output
    assert f"summary={tmp_path / 'normalized_reviews.summary.md'}" in output
    assert f"run_record={tmp_path / 'normalized_reviews.run.json'}" in output
    assert "steps=8" in output


def test_run_workflow_command_succeeds_with_sample_manifest(
    capsys: pytest.CaptureFixture[str],
) -> None:
    exit_code = main(
        [
            "run-workflow",
            "--manifest",
            str(SAMPLE_MANIFEST_PATH),
        ]
    )

    output_path = Path("artifacts/readysetrentables/normalized_reviews.json")
    metadata_path = Path("artifacts/readysetrentables/normalized_reviews.metadata.json")
    summary_path = Path("artifacts/readysetrentables/normalized_reviews.summary.md")
    run_record_path = Path("artifacts/readysetrentables/normalized_reviews.run.json")

    assert exit_code == 0
    assert output_path.is_file()
    assert metadata_path.is_file()
    assert summary_path.is_file()
    assert run_record_path.is_file()

    output = capsys.readouterr().out
    assert "run_id=" in output
    assert "review_count=8" in output
    assert f"output={output_path}" in output
    assert f"metadata={metadata_path}" in output
    assert f"summary={summary_path}" in output
    assert f"run_record={run_record_path}" in output


def test_run_workflow_command_without_execution_engine_override_uses_manifest(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[WorkflowExecutionEngine | None] = []

    def fake_run_workflow(
        _: Path,
        *,
        approved: bool,
        execution_engine_override: WorkflowExecutionEngine | None,
    ) -> ReviewNormalizationWorkflowResult:
        assert approved is False
        calls.append(execution_engine_override)
        return _review_normalization_result(Path("artifacts/test/normalized_reviews.json"))

    monkeypatch.setattr("daedalus.cli.run_workflow_from_manifest_path", fake_run_workflow)

    exit_code = main(
        [
            "run-workflow",
            "--manifest",
            str(SAMPLE_MANIFEST_PATH),
        ]
    )

    assert exit_code == 0
    assert calls == [None]


def test_run_workflow_command_passes_execution_engine_override(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[WorkflowExecutionEngine | None] = []

    def fake_run_workflow(
        _: Path,
        *,
        approved: bool,
        execution_engine_override: WorkflowExecutionEngine | None,
    ) -> ReviewNormalizationWorkflowResult:
        assert approved is False
        calls.append(execution_engine_override)
        return _review_normalization_result(Path("artifacts/test/normalized_reviews.json"))

    monkeypatch.setattr("daedalus.cli.run_workflow_from_manifest_path", fake_run_workflow)

    exit_code = main(
        [
            "run-workflow",
            "--manifest",
            str(SAMPLE_MANIFEST_PATH),
            "--execution-engine",
            "langgraph",
        ]
    )

    assert exit_code == 0
    assert calls == [WorkflowExecutionEngine.LANGGRAPH]


def test_run_workflow_command_invalid_execution_engine_fails_cleanly() -> None:
    with pytest.raises(SystemExit) as exc_info:
        main(
            [
                "run-workflow",
                "--manifest",
                str(SAMPLE_MANIFEST_PATH),
                "--execution-engine",
                "unsupported",
            ]
        )

    assert exc_info.value.code == 2


def test_run_workflow_command_rejects_unsupported_manifest(tmp_path: Path) -> None:
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

    with pytest.raises(SystemExit) as exc_info:
        main(
            [
                "run-workflow",
                "--manifest",
                str(manifest_path),
            ]
        )

    assert exc_info.value.code == 2


def test_run_workflow_command_requires_approval_when_manifest_requires_it(
    tmp_path: Path,
) -> None:
    manifest_path = _write_readysetrentables_manifest(
        tmp_path,
        requires_human_approval=True,
    )

    with pytest.raises(SystemExit) as exc_info:
        main(
            [
                "run-workflow",
                "--manifest",
                str(manifest_path),
            ]
        )

    assert exc_info.value.code == 2


def test_run_workflow_command_succeeds_when_approval_supplied(
    tmp_path: Path,
) -> None:
    manifest_path = _write_readysetrentables_manifest(
        tmp_path,
        requires_human_approval=True,
    )

    exit_code = main(
        [
            "run-workflow",
            "--manifest",
            str(manifest_path),
            "--approve",
        ]
    )

    assert exit_code == 0
    assert (tmp_path / "normalized_reviews.json").is_file()
    assert (tmp_path / "normalized_reviews.metadata.json").is_file()
    assert (tmp_path / "normalized_reviews.summary.md").is_file()
    assert (tmp_path / "normalized_reviews.run.json").is_file()


def test_run_workflow_command_without_persist_does_not_call_persistence(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manifest_path = _write_readysetrentables_manifest(
        tmp_path,
        requires_human_approval=False,
    )

    def fail_if_called(_: ReviewNormalizationWorkflowResult) -> int:
        msg = "Persistence should not run without --persist"
        raise AssertionError(msg)

    monkeypatch.setattr(
        "daedalus.cli.persist_review_normalization_workflow_result",
        fail_if_called,
    )

    exit_code = main(
        [
            "run-workflow",
            "--manifest",
            str(manifest_path),
        ]
    )

    assert exit_code == 0


def test_run_workflow_command_with_persist_calls_persistence_flow(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    manifest_path = _write_readysetrentables_manifest(
        tmp_path,
        requires_human_approval=False,
    )
    persisted_results: list[ReviewNormalizationWorkflowResult] = []

    def fake_persist(result: ReviewNormalizationWorkflowResult) -> int:
        persisted_results.append(result)
        return 4

    monkeypatch.setattr(
        "daedalus.cli.persist_review_normalization_workflow_result",
        fake_persist,
    )

    exit_code = main(
        [
            "run-workflow",
            "--manifest",
            str(manifest_path),
            "--persist",
        ]
    )

    output = capsys.readouterr().out
    assert exit_code == 0
    assert len(persisted_results) == 1
    assert persisted_results[0].run_record_json_path == tmp_path / "normalized_reviews.run.json"
    assert "Persisted workflow run" in output
    assert "with 4 artifact record(s)." in output


def test_run_workflow_command_with_persist_failure_fails_cleanly(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manifest_path = _write_readysetrentables_manifest(
        tmp_path,
        requires_human_approval=False,
    )

    def fail_persist(_: ReviewNormalizationWorkflowResult) -> int:
        msg = "Failed to persist workflow run"
        raise WorkflowPersistenceError(msg)

    monkeypatch.setattr(
        "daedalus.cli.persist_review_normalization_workflow_result",
        fail_persist,
    )

    with pytest.raises(SystemExit) as exc_info:
        main(
            [
                "run-workflow",
                "--manifest",
                str(manifest_path),
                "--persist",
            ]
        )

    assert exc_info.value.code == 2


def test_migrate_db_command_succeeds_with_mocked_migration_runner(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    settings = PostgresSettings(
        host="placeholder-host",
        port=5433,
        database="placeholder-db",
        user="placeholder-user",
        password="placeholder-password",
    )
    applied_migrations = [Path("sql/migrations/001_create_workflow_tables.sql")]

    monkeypatch.setattr("daedalus.cli.load_postgres_settings", lambda: settings)
    monkeypatch.setattr("daedalus.cli.apply_migrations", lambda _: applied_migrations)

    exit_code = main(["migrate-db"])

    assert exit_code == 0
    assert "Applied 1 migration files" in capsys.readouterr().out


def test_record_fake_model_invocation_command_succeeds_with_mocked_postgres(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    connection = FakeModelInvocationConnection()
    settings = PostgresSettings(
        host="placeholder-host",
        port=5433,
        database="placeholder-db",
        user="placeholder-user",
        password="placeholder-password",
    )
    monkeypatch.setattr("daedalus.cli.load_postgres_settings", lambda: settings)
    monkeypatch.setattr("daedalus.cli.connect_postgres", lambda _: connection)

    exit_code = main(["record-fake-model-invocation", "--run-id", str(uuid4())])

    output = capsys.readouterr().out
    assert exit_code == 0
    assert "Recorded fake model invocation" in output
    assert "provider=fake" in output
    assert "model_name=fake-model" in output
    assert "total_tokens=" in output
    assert "estimated_cost_usd=" in output
    assert connection.committed is True
    assert connection.rolled_back is False
    assert connection.closed is True
    assert any("insert into model_invocations" in sql.lower() for sql in connection.executed_sql)


def test_record_fake_model_invocation_invalid_run_id_fails_cleanly() -> None:
    with pytest.raises(SystemExit) as exc_info:
        main(["record-fake-model-invocation", "--run-id", "not-a-uuid"])

    assert exc_info.value.code == 2


def test_record_fake_model_invocation_output_omits_raw_input_and_response(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    connection = FakeModelInvocationConnection()
    settings = PostgresSettings(
        host="placeholder-host",
        port=5433,
        database="placeholder-db",
        user="placeholder-user",
        password="placeholder-password",
    )
    monkeypatch.setattr("daedalus.cli.load_postgres_settings", lambda: settings)
    monkeypatch.setattr("daedalus.cli.connect_postgres", lambda _: connection)

    exit_code = main(["record-fake-model-invocation", "--run-id", str(uuid4())])

    output = capsys.readouterr().out
    assert exit_code == 0
    assert "Synthetic local fake model check text." not in output
    assert "fake local summary" not in output


def test_record_review_theme_summary_artifact_command_succeeds_with_mocked_postgres(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    connection = FakeModelInvocationConnection()
    settings = PostgresSettings(
        host="placeholder-host",
        port=5433,
        database="placeholder-db",
        user="placeholder-user",
        password="placeholder-password",
    )
    run_id = uuid4()
    artifact_path = tmp_path / "review_theme_summary.md"
    artifact_body = "Do not print this review theme summary body."
    artifact_path.write_text(artifact_body, encoding="utf-8")

    monkeypatch.setattr("daedalus.cli.load_postgres_settings", lambda: settings)
    monkeypatch.setattr("daedalus.cli.connect_postgres", lambda _: connection)

    exit_code = main(
        [
            "record-review-theme-summary-artifact",
            "--run-id",
            str(run_id),
            "--path",
            str(artifact_path),
        ]
    )

    output = capsys.readouterr().out
    assert exit_code == 0
    assert "Recorded review theme summary artifact" in output
    assert str(run_id) in output
    assert "artifact_type=review_theme_summary" in output
    assert f"artifact_path={artifact_path}" in output
    assert artifact_body not in output
    assert connection.committed is True
    assert connection.rolled_back is False
    assert connection.closed is True
    assert any("insert into workflow_artifacts" in sql.lower() for sql in connection.executed_sql)
    assert connection.executed_params[0][1] == run_id
    assert connection.executed_params[0][2] == ArtifactType.REVIEW_THEME_SUMMARY.value
    assert connection.executed_params[0][3] == str(artifact_path)


def test_record_review_theme_summary_artifact_missing_path_fails_cleanly(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fail_connect(_: object) -> object:
        raise AssertionError("Postgres should not be opened for a missing artifact path")

    monkeypatch.setattr("daedalus.cli.connect_postgres", fail_connect)

    with pytest.raises(SystemExit) as exc_info:
        main(
            [
                "record-review-theme-summary-artifact",
                "--run-id",
                str(uuid4()),
                "--path",
                str(tmp_path / "missing_review_theme_summary.md"),
            ]
        )

    assert exc_info.value.code == 2


def test_record_review_theme_summary_artifact_invalid_run_id_fails_cleanly(
    tmp_path: Path,
) -> None:
    artifact_path = tmp_path / "review_theme_summary.md"
    artifact_path.write_text("safe artifact body", encoding="utf-8")

    with pytest.raises(SystemExit) as exc_info:
        main(
            [
                "record-review-theme-summary-artifact",
                "--run-id",
                "not-a-uuid",
                "--path",
                str(artifact_path),
            ]
        )

    assert exc_info.value.code == 2


def test_record_evaluation_report_artifact_command_succeeds_with_mocked_postgres(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    connection = FakeModelInvocationConnection()
    settings = PostgresSettings(
        host="placeholder-host",
        port=5433,
        database="placeholder-db",
        user="placeholder-user",
        password="placeholder-password",
    )
    run_id = uuid4()
    artifact_path = tmp_path / "review_theme_summary.evaluation.json"
    artifact_body = "Do not print this evaluation report body."
    artifact_path.write_text(artifact_body, encoding="utf-8")

    monkeypatch.setattr("daedalus.cli.load_postgres_settings", lambda: settings)
    monkeypatch.setattr("daedalus.cli.connect_postgres", lambda _: connection)

    exit_code = main(
        [
            "record-evaluation-report-artifact",
            "--run-id",
            str(run_id),
            "--path",
            str(artifact_path),
        ]
    )

    output = capsys.readouterr().out
    assert exit_code == 0
    assert "Recorded evaluation report artifact" in output
    assert str(run_id) in output
    assert "artifact_type=evaluation_report" in output
    assert f"artifact_path={artifact_path}" in output
    assert artifact_body not in output
    assert connection.committed is True
    assert connection.rolled_back is False
    assert connection.closed is True
    assert any("insert into workflow_artifacts" in sql.lower() for sql in connection.executed_sql)
    assert connection.executed_params[0][1] == run_id
    assert connection.executed_params[0][2] == ArtifactType.EVALUATION_REPORT.value
    assert connection.executed_params[0][3] == str(artifact_path)


def test_record_evaluation_report_artifact_missing_path_fails_cleanly(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fail_connect(_: object) -> object:
        raise AssertionError("Postgres should not be opened for a missing artifact path")

    monkeypatch.setattr("daedalus.cli.connect_postgres", fail_connect)

    with pytest.raises(SystemExit) as exc_info:
        main(
            [
                "record-evaluation-report-artifact",
                "--run-id",
                str(uuid4()),
                "--path",
                str(tmp_path / "missing_evaluation_report.json"),
            ]
        )

    assert exc_info.value.code == 2


def test_record_evaluation_report_artifact_invalid_run_id_fails_cleanly(
    tmp_path: Path,
) -> None:
    artifact_path = tmp_path / "review_theme_summary.evaluation.json"
    artifact_path.write_text("safe evaluation report body", encoding="utf-8")

    with pytest.raises(SystemExit) as exc_info:
        main(
            [
                "record-evaluation-report-artifact",
                "--run-id",
                "not-a-uuid",
                "--path",
                str(artifact_path),
            ]
        )

    assert exc_info.value.code == 2


def test_record_evaluation_report_artifact_rolls_back_on_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    connection = FailingArtifactConnection()
    settings = PostgresSettings(
        host="placeholder-host",
        port=5433,
        database="placeholder-db",
        user="placeholder-user",
        password="placeholder-password",
    )
    artifact_path = tmp_path / "review_theme_summary.evaluation.json"
    artifact_body = "Do not print this failed evaluation report body."
    artifact_path.write_text(artifact_body, encoding="utf-8")

    monkeypatch.setattr("daedalus.cli.load_postgres_settings", lambda: settings)
    monkeypatch.setattr("daedalus.cli.connect_postgres", lambda _: connection)

    with pytest.raises(SystemExit) as exc_info:
        main(
            [
                "record-evaluation-report-artifact",
                "--run-id",
                str(uuid4()),
                "--path",
                str(artifact_path),
            ]
        )

    captured = capsys.readouterr()
    combined_output = captured.out + captured.err
    assert exc_info.value.code == 2
    assert connection.committed is False
    assert connection.rolled_back is True
    assert connection.closed is True
    assert artifact_body not in combined_output


# ---------------------------------------------------------------------------
# record-evaluation-comparison-report-artifact
# ---------------------------------------------------------------------------


def test_record_evaluation_comparison_report_artifact_command_succeeds_with_mocked_postgres(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    connection = FakeModelInvocationConnection()
    settings = PostgresSettings(
        host="placeholder-host",
        port=5433,
        database="placeholder-db",
        user="placeholder-user",
        password="placeholder-password",
    )
    run_id = uuid4()
    artifact_path = tmp_path / "review_theme_summary.comparison.json"
    artifact_body = "Do not print this comparison report body."
    artifact_path.write_text(artifact_body, encoding="utf-8")

    monkeypatch.setattr("daedalus.cli.load_postgres_settings", lambda: settings)
    monkeypatch.setattr("daedalus.cli.connect_postgres", lambda _: connection)

    exit_code = main(
        [
            "record-evaluation-comparison-report-artifact",
            "--run-id",
            str(run_id),
            "--path",
            str(artifact_path),
        ]
    )

    output = capsys.readouterr().out
    assert exit_code == 0
    assert "Recorded evaluation comparison report artifact" in output
    assert str(run_id) in output
    assert "artifact_type=evaluation_comparison_report" in output
    assert f"artifact_path={artifact_path}" in output
    assert artifact_body not in output
    assert connection.committed is True
    assert connection.rolled_back is False
    assert connection.closed is True
    assert any("insert into workflow_artifacts" in sql.lower() for sql in connection.executed_sql)
    assert connection.executed_params[0][1] == run_id
    assert connection.executed_params[0][2] == ArtifactType.EVALUATION_COMPARISON_REPORT.value
    assert connection.executed_params[0][3] == str(artifact_path)


def test_record_evaluation_comparison_report_artifact_output_includes_run_id(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    connection = FakeModelInvocationConnection()
    settings = PostgresSettings(
        host="placeholder-host",
        port=5433,
        database="placeholder-db",
        user="placeholder-user",
        password="placeholder-password",
    )
    run_id = uuid4()
    artifact_path = tmp_path / "review_theme_summary.comparison.json"
    artifact_path.write_text("{}", encoding="utf-8")

    monkeypatch.setattr("daedalus.cli.load_postgres_settings", lambda: settings)
    monkeypatch.setattr("daedalus.cli.connect_postgres", lambda _: connection)

    main(
        [
            "record-evaluation-comparison-report-artifact",
            "--run-id",
            str(run_id),
            "--path",
            str(artifact_path),
        ]
    )

    output = capsys.readouterr().out
    assert str(run_id) in output


def test_record_evaluation_comparison_report_artifact_output_includes_artifact_type(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    connection = FakeModelInvocationConnection()
    settings = PostgresSettings(
        host="placeholder-host",
        port=5433,
        database="placeholder-db",
        user="placeholder-user",
        password="placeholder-password",
    )
    artifact_path = tmp_path / "review_theme_summary.comparison.json"
    artifact_path.write_text("{}", encoding="utf-8")

    monkeypatch.setattr("daedalus.cli.load_postgres_settings", lambda: settings)
    monkeypatch.setattr("daedalus.cli.connect_postgres", lambda _: connection)

    main(
        [
            "record-evaluation-comparison-report-artifact",
            "--run-id",
            str(uuid4()),
            "--path",
            str(artifact_path),
        ]
    )

    output = capsys.readouterr().out
    assert "artifact_type=evaluation_comparison_report" in output


def test_record_evaluation_comparison_report_artifact_output_includes_artifact_path(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    connection = FakeModelInvocationConnection()
    settings = PostgresSettings(
        host="placeholder-host",
        port=5433,
        database="placeholder-db",
        user="placeholder-user",
        password="placeholder-password",
    )
    artifact_path = tmp_path / "review_theme_summary.comparison.json"
    artifact_path.write_text("{}", encoding="utf-8")

    monkeypatch.setattr("daedalus.cli.load_postgres_settings", lambda: settings)
    monkeypatch.setattr("daedalus.cli.connect_postgres", lambda _: connection)

    main(
        [
            "record-evaluation-comparison-report-artifact",
            "--run-id",
            str(uuid4()),
            "--path",
            str(artifact_path),
        ]
    )

    output = capsys.readouterr().out
    assert str(artifact_path) in output


def test_record_evaluation_comparison_report_artifact_repository_receives_correct_type(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    connection = FakeModelInvocationConnection()
    settings = PostgresSettings(
        host="placeholder-host",
        port=5433,
        database="placeholder-db",
        user="placeholder-user",
        password="placeholder-password",
    )
    run_id = uuid4()
    artifact_path = tmp_path / "review_theme_summary.comparison.json"
    artifact_path.write_text("{}", encoding="utf-8")

    monkeypatch.setattr("daedalus.cli.load_postgres_settings", lambda: settings)
    monkeypatch.setattr("daedalus.cli.connect_postgres", lambda _: connection)

    main(
        [
            "record-evaluation-comparison-report-artifact",
            "--run-id",
            str(run_id),
            "--path",
            str(artifact_path),
        ]
    )

    assert connection.executed_params[0][2] == ArtifactType.EVALUATION_COMPARISON_REPORT.value


def test_record_evaluation_comparison_report_artifact_does_not_print_file_contents(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    connection = FakeModelInvocationConnection()
    settings = PostgresSettings(
        host="placeholder-host",
        port=5433,
        database="placeholder-db",
        user="placeholder-user",
        password="placeholder-password",
    )
    artifact_path = tmp_path / "review_theme_summary.comparison.json"
    artifact_body = "Sensitive comparison report body that must not appear in stdout."
    artifact_path.write_text(artifact_body, encoding="utf-8")

    monkeypatch.setattr("daedalus.cli.load_postgres_settings", lambda: settings)
    monkeypatch.setattr("daedalus.cli.connect_postgres", lambda _: connection)

    main(
        [
            "record-evaluation-comparison-report-artifact",
            "--run-id",
            str(uuid4()),
            "--path",
            str(artifact_path),
        ]
    )

    output = capsys.readouterr().out
    assert artifact_body not in output


def test_record_evaluation_comparison_report_artifact_commits_on_success(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    connection = FakeModelInvocationConnection()
    settings = PostgresSettings(
        host="placeholder-host",
        port=5433,
        database="placeholder-db",
        user="placeholder-user",
        password="placeholder-password",
    )
    artifact_path = tmp_path / "review_theme_summary.comparison.json"
    artifact_path.write_text("{}", encoding="utf-8")

    monkeypatch.setattr("daedalus.cli.load_postgres_settings", lambda: settings)
    monkeypatch.setattr("daedalus.cli.connect_postgres", lambda _: connection)

    main(
        [
            "record-evaluation-comparison-report-artifact",
            "--run-id",
            str(uuid4()),
            "--path",
            str(artifact_path),
        ]
    )

    assert connection.committed is True
    assert connection.rolled_back is False
    assert connection.closed is True


def test_record_evaluation_comparison_report_artifact_missing_path_fails_cleanly(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fail_connect(_: object) -> object:
        raise AssertionError("Postgres should not be opened for a missing artifact path")

    monkeypatch.setattr("daedalus.cli.connect_postgres", fail_connect)

    with pytest.raises(SystemExit) as exc_info:
        main(
            [
                "record-evaluation-comparison-report-artifact",
                "--run-id",
                str(uuid4()),
                "--path",
                str(tmp_path / "missing_comparison_report.json"),
            ]
        )

    assert exc_info.value.code == 2


def test_record_evaluation_comparison_report_artifact_invalid_run_id_fails_cleanly(
    tmp_path: Path,
) -> None:
    artifact_path = tmp_path / "review_theme_summary.comparison.json"
    artifact_path.write_text("{}", encoding="utf-8")

    with pytest.raises(SystemExit) as exc_info:
        main(
            [
                "record-evaluation-comparison-report-artifact",
                "--run-id",
                "not-a-uuid",
                "--path",
                str(artifact_path),
            ]
        )

    assert exc_info.value.code == 2


def test_record_evaluation_comparison_report_artifact_rolls_back_on_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    connection = FailingArtifactConnection()
    settings = PostgresSettings(
        host="placeholder-host",
        port=5433,
        database="placeholder-db",
        user="placeholder-user",
        password="placeholder-password",
    )
    artifact_path = tmp_path / "review_theme_summary.comparison.json"
    artifact_body = "Do not print this failed comparison report body."
    artifact_path.write_text(artifact_body, encoding="utf-8")

    monkeypatch.setattr("daedalus.cli.load_postgres_settings", lambda: settings)
    monkeypatch.setattr("daedalus.cli.connect_postgres", lambda _: connection)

    with pytest.raises(SystemExit) as exc_info:
        main(
            [
                "record-evaluation-comparison-report-artifact",
                "--run-id",
                str(uuid4()),
                "--path",
                str(artifact_path),
            ]
        )

    captured = capsys.readouterr()
    combined_output = captured.out + captured.err
    assert exc_info.value.code == 2
    assert connection.committed is False
    assert connection.rolled_back is True
    assert connection.closed is True
    assert artifact_body not in combined_output


# ---------------------------------------------------------------------------
# record-review-insights-artifact
# ---------------------------------------------------------------------------


def test_record_review_insights_artifact_command_succeeds_with_mocked_postgres(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    connection = FakeModelInvocationConnection()
    settings = PostgresSettings(
        host="placeholder-host",
        port=5433,
        database="placeholder-db",
        user="placeholder-user",
        password="placeholder-password",
    )
    run_id = uuid4()
    artifact_path = tmp_path / "review_insights.json"
    artifact_body = "Sensitive synthetic review insight body must not be printed."
    artifact_path.write_text(artifact_body, encoding="utf-8")

    monkeypatch.setattr("daedalus.cli.load_postgres_settings", lambda: settings)
    monkeypatch.setattr("daedalus.cli.connect_postgres", lambda _: connection)

    exit_code = main(
        [
            "record-review-insights-artifact",
            "--run-id",
            str(run_id),
            "--path",
            str(artifact_path),
        ]
    )

    output = capsys.readouterr().out
    assert exit_code == 0
    assert "Recorded review insights artifact" in output
    assert str(run_id) in output
    assert "artifact_type=review_insights" in output
    assert f"artifact_path={artifact_path}" in output
    assert artifact_body not in output
    assert connection.committed is True
    assert connection.rolled_back is False
    assert connection.closed is True
    assert any("insert into workflow_artifacts" in sql.lower() for sql in connection.executed_sql)
    assert connection.executed_params[0][1] == run_id
    assert connection.executed_params[0][2] == ArtifactType.REVIEW_INSIGHTS.value
    assert connection.executed_params[0][3] == str(artifact_path)


def test_record_review_insights_artifact_missing_path_fails_cleanly(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fail_connect(_: object) -> object:
        raise AssertionError("Postgres should not be opened for a missing artifact path")

    monkeypatch.setattr("daedalus.cli.connect_postgres", fail_connect)

    with pytest.raises(SystemExit) as exc_info:
        main(
            [
                "record-review-insights-artifact",
                "--run-id",
                str(uuid4()),
                "--path",
                str(tmp_path / "missing_review_insights.json"),
            ]
        )

    assert exc_info.value.code == 2


def test_record_review_insights_artifact_invalid_run_id_fails_cleanly(
    tmp_path: Path,
) -> None:
    artifact_path = tmp_path / "review_insights.json"
    artifact_path.write_text("safe synthetic artifact body", encoding="utf-8")

    with pytest.raises(SystemExit) as exc_info:
        main(
            [
                "record-review-insights-artifact",
                "--run-id",
                "not-a-uuid",
                "--path",
                str(artifact_path),
            ]
        )

    assert exc_info.value.code == 2


def test_record_review_insights_artifact_rolls_back_without_printing_contents(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    connection = FailingArtifactConnection()
    settings = PostgresSettings(
        host="placeholder-host",
        port=5433,
        database="placeholder-db",
        user="placeholder-user",
        password="placeholder-password",
    )
    artifact_path = tmp_path / "review_insights.json"
    artifact_body = "Sensitive failed review insight body must not be printed."
    artifact_path.write_text(artifact_body, encoding="utf-8")

    monkeypatch.setattr("daedalus.cli.load_postgres_settings", lambda: settings)
    monkeypatch.setattr("daedalus.cli.connect_postgres", lambda _: connection)

    with pytest.raises(SystemExit) as exc_info:
        main(
            [
                "record-review-insights-artifact",
                "--run-id",
                str(uuid4()),
                "--path",
                str(artifact_path),
            ]
        )

    captured = capsys.readouterr()
    combined_output = captured.out + captured.err
    assert exc_info.value.code == 2
    assert connection.committed is False
    assert connection.rolled_back is True
    assert connection.closed is True
    assert artifact_body not in combined_output


def test_record_rsr_source_extract_artifact_command_succeeds_with_mocked_postgres(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    connection = FakeModelInvocationConnection()
    settings = PostgresSettings(
        host="placeholder-host",
        port=5433,
        database="placeholder-db",
        user="placeholder-user",
        password="placeholder-password",
    )
    run_id = uuid4()
    artifact_path = tmp_path / "rsr_source_extract.json"
    artifact_body = "Synthetic review: source extract body must not be printed."
    artifact_path.write_text(artifact_body, encoding="utf-8")

    monkeypatch.setattr("daedalus.cli.load_postgres_settings", lambda: settings)
    monkeypatch.setattr("daedalus.cli.connect_postgres", lambda _: connection)

    exit_code = main(
        [
            "record-rsr-source-extract-artifact",
            "--run-id",
            str(run_id),
            "--path",
            str(artifact_path),
        ]
    )

    output = capsys.readouterr().out
    assert exit_code == 0
    assert "Recorded RSR source extract artifact" in output
    assert str(run_id) in output
    assert "artifact_type=rsr_source_extract" in output
    assert f"artifact_path={artifact_path}" in output
    assert artifact_body not in output
    assert "Synthetic review:" not in output
    assert connection.committed is True
    assert connection.rolled_back is False
    assert connection.closed is True
    assert any("insert into workflow_artifacts" in sql.lower() for sql in connection.executed_sql)
    assert connection.executed_params[0][1] == run_id
    assert connection.executed_params[0][2] == ArtifactType.RSR_SOURCE_EXTRACT.value
    assert connection.executed_params[0][3] == str(artifact_path)


def test_record_rsr_source_extract_artifact_missing_path_fails_cleanly(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fail_connect(_: object) -> object:
        msg = "Metadata Postgres should not be opened for a missing artifact path"
        raise AssertionError(msg)

    monkeypatch.setattr("daedalus.cli.connect_postgres", fail_connect)

    with pytest.raises(SystemExit) as exc_info:
        main(
            [
                "record-rsr-source-extract-artifact",
                "--run-id",
                str(uuid4()),
                "--path",
                str(tmp_path / "missing_rsr_source_extract.json"),
            ]
        )

    assert exc_info.value.code == 2


def test_record_rsr_source_extract_artifact_invalid_run_id_fails_cleanly(
    tmp_path: Path,
) -> None:
    artifact_path = tmp_path / "rsr_source_extract.json"
    artifact_path.write_text("safe source extract artifact body", encoding="utf-8")

    with pytest.raises(SystemExit) as exc_info:
        main(
            [
                "record-rsr-source-extract-artifact",
                "--run-id",
                "not-a-uuid",
                "--path",
                str(artifact_path),
            ]
        )

    assert exc_info.value.code == 2


def test_record_rsr_source_extract_artifact_rolls_back_on_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    connection = FailingArtifactConnection()
    settings = PostgresSettings(
        host="placeholder-host",
        port=5433,
        database="placeholder-db",
        user="placeholder-user",
        password="placeholder-password",
    )
    artifact_path = tmp_path / "rsr_source_extract.json"
    artifact_body = "Synthetic review: failed source extract body must not be printed."
    artifact_path.write_text(artifact_body, encoding="utf-8")

    monkeypatch.setattr("daedalus.cli.load_postgres_settings", lambda: settings)
    monkeypatch.setattr("daedalus.cli.connect_postgres", lambda _: connection)

    with pytest.raises(SystemExit) as exc_info:
        main(
            [
                "record-rsr-source-extract-artifact",
                "--run-id",
                str(uuid4()),
                "--path",
                str(artifact_path),
            ]
        )

    captured = capsys.readouterr()
    combined_output = captured.out + captured.err
    assert exc_info.value.code == 2
    assert connection.committed is False
    assert connection.rolled_back is True
    assert connection.closed is True
    assert artifact_body not in combined_output
    assert "Synthetic review:" not in combined_output


def test_record_rsr_source_extract_artifact_uses_metadata_db_not_rsr_source_settings(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    connection = FakeModelInvocationConnection()
    settings = PostgresSettings(
        host="placeholder-host",
        port=5433,
        database="placeholder-db",
        user="placeholder-user",
        password="placeholder-password",
    )
    artifact_path = tmp_path / "rsr_source_extract.json"
    artifact_path.write_text("safe source extract artifact body", encoding="utf-8")

    def fail_rsr_source_settings() -> object:
        msg = "RSR_SOURCE_POSTGRES settings should not be loaded"
        raise AssertionError(msg)

    monkeypatch.setattr("daedalus.cli.load_postgres_settings", lambda: settings)
    monkeypatch.setattr("daedalus.cli.connect_postgres", lambda _: connection)
    monkeypatch.setattr("daedalus.cli.load_rsr_source_postgres_settings", fail_rsr_source_settings)

    exit_code = main(
        [
            "record-rsr-source-extract-artifact",
            "--run-id",
            str(uuid4()),
            "--path",
            str(artifact_path),
        ]
    )

    assert exit_code == 0
    assert connection.committed is True


def test_summarize_review_themes_fake_command_succeeds(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    input_path = _write_normalized_reviews_json(tmp_path)
    output_path = tmp_path / "review_theme_summary.md"
    run_id = uuid4()

    exit_code = main(
        [
            "summarize-review-themes-fake",
            "--input",
            str(input_path),
            "--output",
            str(output_path),
            "--run-id",
            str(run_id),
        ]
    )

    output = capsys.readouterr().out
    assert exit_code == 0
    assert output_path.is_file()
    assert str(run_id) in output
    assert f"output={output_path}" in output
    assert "provider=fake" in output
    assert "model_name=fake-model" in output
    assert "total_tokens=" in output
    assert "estimated_cost_usd=" in output


def test_summarize_review_themes_fake_command_generates_run_id(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    input_path = _write_normalized_reviews_json(tmp_path)
    output_path = tmp_path / "review_theme_summary.md"

    exit_code = main(
        [
            "summarize-review-themes-fake",
            "--input",
            str(input_path),
            "--output",
            str(output_path),
        ]
    )

    output = capsys.readouterr().out
    assert exit_code == 0
    assert "run_id=" in output
    assert output_path.is_file()


def test_summarize_review_themes_fake_command_output_omits_raw_text(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    input_path = _write_normalized_reviews_json(tmp_path)
    output_path = tmp_path / "review_theme_summary.md"

    exit_code = main(
        [
            "summarize-review-themes-fake",
            "--input",
            str(input_path),
            "--output",
            str(output_path),
        ]
    )

    output = capsys.readouterr().out
    assert exit_code == 0
    assert "ReadySetRentables Review Theme Summary" not in output
    assert "fake model response" not in output
    assert "Bright apartment with a spotless kitchen" not in output


def test_summarize_review_themes_fake_command_invalid_representative_review_limit_fails_cleanly(
    tmp_path: Path,
) -> None:
    input_path = _write_normalized_reviews_json(tmp_path)
    output_path = tmp_path / "review_theme_summary.md"

    with pytest.raises(SystemExit) as exc_info:
        main(
            [
                "summarize-review-themes-fake",
                "--input",
                str(input_path),
                "--output",
                str(output_path),
                "--max-representative-reviews",
                "-1",
            ]
        )

    assert exc_info.value.code == 2


def test_evaluate_review_theme_summary_succeeds_for_valid_summary_artifact(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    run_id = uuid4()
    summary_path = _write_review_theme_summary_markdown_artifact(tmp_path, run_id=run_id)
    output_json_path = tmp_path / "evaluation.json"

    exit_code = main(
        [
            "evaluate-review-theme-summary",
            "--summary",
            str(summary_path),
            "--run-id",
            str(run_id),
            "--output-json",
            str(output_json_path),
        ]
    )

    output = capsys.readouterr().out
    assert exit_code == 0
    assert output_json_path.is_file()
    assert "target_name=review_theme_summary.md" in output
    assert "passed=True" in output


def test_evaluate_review_theme_summary_default_json_output_path_is_created(
    tmp_path: Path,
) -> None:
    summary_path = _write_review_theme_summary_markdown_artifact(tmp_path)

    exit_code = main(
        [
            "evaluate-review-theme-summary",
            "--summary",
            str(summary_path),
        ]
    )

    assert exit_code == 0
    assert (tmp_path / "review_theme_summary.evaluation.json").is_file()


def test_evaluate_review_theme_summary_output_json_writes_report(tmp_path: Path) -> None:
    summary_path = _write_review_theme_summary_markdown_artifact(tmp_path)
    output_json_path = tmp_path / "custom_evaluation.json"

    exit_code = main(
        [
            "evaluate-review-theme-summary",
            "--summary",
            str(summary_path),
            "--output-json",
            str(output_json_path),
        ]
    )

    data = _read_json(output_json_path)
    assert exit_code == 0
    assert data["target_type"] == "review_theme_summary"
    assert data["evaluator_name"] == "readysetrentables_review_theme_summary_basic"


def test_evaluate_review_theme_summary_output_md_writes_report(tmp_path: Path) -> None:
    summary_path = _write_review_theme_summary_markdown_artifact(tmp_path)
    output_md_path = tmp_path / "custom_evaluation.md"

    exit_code = main(
        [
            "evaluate-review-theme-summary",
            "--summary",
            str(summary_path),
            "--output-md",
            str(output_md_path),
        ]
    )

    markdown = output_md_path.read_text(encoding="utf-8")
    assert exit_code == 0
    assert "Evaluation Report" in markdown
    assert "Target name: `review_theme_summary.md`" in markdown


def test_evaluate_review_theme_summary_writes_json_and_markdown_together(
    tmp_path: Path,
) -> None:
    summary_path = _write_review_theme_summary_markdown_artifact(tmp_path)
    output_json_path = tmp_path / "evaluation.json"
    output_md_path = tmp_path / "evaluation.md"

    exit_code = main(
        [
            "evaluate-review-theme-summary",
            "--summary",
            str(summary_path),
            "--output-json",
            str(output_json_path),
            "--output-md",
            str(output_md_path),
        ]
    )

    assert exit_code == 0
    assert output_json_path.is_file()
    assert output_md_path.is_file()


def test_evaluate_review_theme_summary_run_id_is_preserved_in_report(
    tmp_path: Path,
) -> None:
    run_id = uuid4()
    summary_path = _write_review_theme_summary_markdown_artifact(tmp_path, run_id=run_id)
    output_json_path = tmp_path / "evaluation.json"

    exit_code = main(
        [
            "evaluate-review-theme-summary",
            "--summary",
            str(summary_path),
            "--run-id",
            str(run_id),
            "--output-json",
            str(output_json_path),
        ]
    )

    data = _read_json(output_json_path)
    assert exit_code == 0
    assert data["run_id"] == str(run_id)


def test_evaluate_review_theme_summary_command_output_includes_counts(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    summary_path = _write_review_theme_summary_markdown_artifact(tmp_path)

    exit_code = main(
        [
            "evaluate-review-theme-summary",
            "--summary",
            str(summary_path),
        ]
    )

    output = capsys.readouterr().out
    assert exit_code == 0
    assert "target_name=review_theme_summary.md" in output
    assert "passed=True" in output
    assert "failed_count=0" in output
    assert "warning_count=0" in output
    assert "error_count=0" in output


def test_evaluate_review_theme_summary_missing_summary_still_writes_failed_report(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    summary_path = tmp_path / "missing_review_theme_summary.md"
    output_json_path = tmp_path / "evaluation.json"

    exit_code = main(
        [
            "evaluate-review-theme-summary",
            "--summary",
            str(summary_path),
            "--output-json",
            str(output_json_path),
        ]
    )

    output = capsys.readouterr().out
    data = _read_json(output_json_path)
    assert exit_code == 0
    assert output_json_path.is_file()
    assert "passed=False" in output
    assert any(
        check["check_name"] == "artifact_exists" and check["status"] == "failed"
        for check in data["checks"]
    )


def test_evaluate_review_theme_summary_invalid_run_id_fails_cleanly(
    tmp_path: Path,
) -> None:
    summary_path = _write_review_theme_summary_markdown_artifact(tmp_path)

    with pytest.raises(SystemExit) as exc_info:
        main(
            [
                "evaluate-review-theme-summary",
                "--summary",
                str(summary_path),
                "--run-id",
                "not-a-uuid",
            ]
        )

    assert exc_info.value.code == 2


def test_evaluate_review_theme_summary_command_does_not_print_artifact_contents(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    summary_path = _write_review_theme_summary_markdown_artifact(tmp_path)

    exit_code = main(
        [
            "evaluate-review-theme-summary",
            "--summary",
            str(summary_path),
        ]
    )

    output = capsys.readouterr().out
    assert exit_code == 0
    assert "Artifact body that must stay out of stdout." not in output
    assert "ReadySetRentables Review Theme Summary" not in output
    assert "readysetrentables/review_theme_summary" not in output


def test_extract_rsr_source_data_succeeds_with_mocked_source_db(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    output_path = tmp_path / "rsr_source_extract.json"
    state = _install_rsr_source_cli_fakes(monkeypatch)

    exit_code = main(
        [
            "extract-rsr-source-data",
            "--market-name",
            "Synthetic Market",
            "--output-json",
            str(output_path),
        ]
    )

    output = capsys.readouterr().out
    data = _read_json(output_path)
    assert exit_code == 0
    assert output_path.is_file()
    assert data["request"]["market_name"] == "Synthetic Market"
    assert state.loaded_settings_count == 1
    assert state.connected_settings == [state.settings]
    assert state.requests[0].market_name == "Synthetic Market"
    assert state.connection.closed is True
    assert f"output={output_path}" in output
    assert "review_count=2" in output
    assert "listing_count=1" in output
    assert "neighborhood_present=true" in output
    assert "Raw private review text" not in output
    assert "top-secret-password" not in output


def test_extract_rsr_source_data_default_output_path_is_created(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(tmp_path)
    _install_rsr_source_cli_fakes(monkeypatch)

    exit_code = main(["extract-rsr-source-data", "--market-name", "Synthetic Market"])

    output_path = Path("artifacts/readysetrentables/rsr_source_extract.json")
    assert exit_code == 0
    assert output_path.is_file()


def test_extract_rsr_source_data_output_json_writes_custom_path(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    output_path = tmp_path / "custom" / "extract.json"
    _install_rsr_source_cli_fakes(monkeypatch)

    exit_code = main(
        [
            "extract-rsr-source-data",
            "--market-name",
            "Synthetic Market",
            "--output-json",
            str(output_path),
        ]
    )

    data = _read_json(output_path)
    assert exit_code == 0
    assert data["source_name"] == "readysetrentables"
    assert data["reviews"][0]["review_id"] == "review-1"


def test_extract_rsr_source_data_market_name_is_required(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fail_if_called() -> object:
        msg = "RSR source settings should not load without --market-name"
        raise AssertionError(msg)

    monkeypatch.setattr("daedalus.cli.load_rsr_source_postgres_settings", fail_if_called)

    with pytest.raises(SystemExit) as exc_info:
        main(["extract-rsr-source-data"])

    assert exc_info.value.code == 2


def test_extract_rsr_source_data_passes_optional_request_fields(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    state = _install_rsr_source_cli_fakes(monkeypatch)

    exit_code = main(
        [
            "extract-rsr-source-data",
            "--market-name",
            "Synthetic Market",
            "--neighborhood-name",
            "Synthetic Neighborhood",
            "--property-type",
            "Entire home",
            "--max-reviews",
            "25",
            "--output-json",
            str(tmp_path / "rsr_source_extract.json"),
        ]
    )

    request = state.requests[0]
    assert exit_code == 0
    assert request.neighborhood_name == "Synthetic Neighborhood"
    assert request.property_type == "Entire home"
    assert request.max_reviews == 25


def test_extract_rsr_source_data_invalid_max_reviews_fails_cleanly(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fail_if_called() -> object:
        msg = "RSR source settings should not load for invalid --max-reviews"
        raise AssertionError(msg)

    monkeypatch.setattr("daedalus.cli.load_rsr_source_postgres_settings", fail_if_called)

    with pytest.raises(SystemExit) as exc_info:
        main(
            [
                "extract-rsr-source-data",
                "--market-name",
                "Synthetic Market",
                "--max-reviews",
                "0",
            ]
        )

    assert exc_info.value.code == 2


def test_extract_rsr_source_data_missing_settings_fails_cleanly(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    def fail_load_settings() -> object:
        msg = "Required environment variable RSR_SOURCE_POSTGRES_HOST is missing or empty"
        raise ValueError(msg)

    def fail_connect(_: object) -> object:
        msg = "RSR source DB should not connect when settings are missing"
        raise AssertionError(msg)

    monkeypatch.setattr("daedalus.cli.load_rsr_source_postgres_settings", fail_load_settings)
    monkeypatch.setattr("daedalus.cli.connect_rsr_source_postgres", fail_connect)

    with pytest.raises(SystemExit) as exc_info:
        main(["extract-rsr-source-data", "--market-name", "Synthetic Market"])

    captured = capsys.readouterr()
    combined_output = captured.out + captured.err
    assert exc_info.value.code == 2
    assert "RSR_SOURCE_POSTGRES_HOST" in combined_output
    assert "top-secret-password" not in combined_output


def test_extract_rsr_source_data_repository_failure_fails_cleanly_and_closes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    state = _install_rsr_source_cli_fakes(
        monkeypatch,
        repository_error=RuntimeError("repo failed: top-secret-password Raw private review text"),
    )

    with pytest.raises(SystemExit) as exc_info:
        main(
            [
                "extract-rsr-source-data",
                "--market-name",
                "Synthetic Market",
                "--output-json",
                str(tmp_path / "rsr_source_extract.json"),
            ]
        )

    captured = capsys.readouterr()
    combined_output = captured.out + captured.err
    assert exc_info.value.code == 2
    assert state.connection.closed is True
    assert "Failed to extract RSR source data." in combined_output
    assert "Raw private review text" not in combined_output
    assert "top-secret-password" not in combined_output


def test_extract_rsr_source_data_connection_failure_fails_cleanly_without_secrets(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    settings = _rsr_source_postgres_settings()

    def fail_connect(_: object) -> object:
        msg = "postgresql://source-user:top-secret-password@private-host/source-db"
        raise RuntimeError(msg)

    monkeypatch.setattr("daedalus.cli.load_rsr_source_postgres_settings", lambda: settings)
    monkeypatch.setattr("daedalus.cli.connect_rsr_source_postgres", fail_connect)

    with pytest.raises(SystemExit) as exc_info:
        main(["extract-rsr-source-data", "--market-name", "Synthetic Market"])

    captured = capsys.readouterr()
    combined_output = captured.out + captured.err
    assert exc_info.value.code == 2
    assert "Failed to extract RSR source data." in combined_output
    assert "top-secret-password" not in combined_output
    assert "postgresql://" not in combined_output


def test_extract_rsr_source_data_does_not_use_metadata_postgres_settings(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _install_rsr_source_cli_fakes(monkeypatch)

    def fail_metadata_settings() -> object:
        msg = "Daedalus metadata POSTGRES settings should not be loaded"
        raise AssertionError(msg)

    monkeypatch.setattr("daedalus.cli.load_postgres_settings", fail_metadata_settings)

    exit_code = main(
        [
            "extract-rsr-source-data",
            "--market-name",
            "Synthetic Market",
            "--output-json",
            str(tmp_path / "rsr_source_extract.json"),
        ]
    )

    assert exit_code == 0


def test_evaluate_rsr_source_extract_succeeds_for_valid_artifact(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    run_id = uuid4()
    source_extract_path = _write_rsr_source_extract_artifact(tmp_path)
    output_json_path = tmp_path / "evaluation.json"

    exit_code = main(
        [
            "evaluate-rsr-source-extract",
            "--source-extract",
            str(source_extract_path),
            "--run-id",
            str(run_id),
            "--output-json",
            str(output_json_path),
        ]
    )

    output = capsys.readouterr().out
    assert exit_code == 0
    assert output_json_path.is_file()
    assert "target_name=rsr_source_extract.json" in output


def test_evaluate_rsr_source_extract_default_json_output_path_is_created(
    tmp_path: Path,
) -> None:
    source_extract_path = _write_rsr_source_extract_artifact(tmp_path)

    exit_code = main(
        [
            "evaluate-rsr-source-extract",
            "--source-extract",
            str(source_extract_path),
        ]
    )

    assert exit_code == 0
    assert (tmp_path / "rsr_source_extract.evaluation.json").is_file()


def test_evaluate_rsr_source_extract_output_json_writes_report(tmp_path: Path) -> None:
    source_extract_path = _write_rsr_source_extract_artifact(tmp_path)
    output_json_path = tmp_path / "custom_evaluation.json"

    exit_code = main(
        [
            "evaluate-rsr-source-extract",
            "--source-extract",
            str(source_extract_path),
            "--output-json",
            str(output_json_path),
        ]
    )

    data = _read_json(output_json_path)
    assert exit_code == 0
    assert data["target_type"] == "rsr_source_extract"
    assert data["evaluator_name"] == "readysetrentables_source_extract_basic"


def test_evaluate_rsr_source_extract_output_md_writes_report(tmp_path: Path) -> None:
    source_extract_path = _write_rsr_source_extract_artifact(tmp_path)
    output_md_path = tmp_path / "custom_evaluation.md"

    exit_code = main(
        [
            "evaluate-rsr-source-extract",
            "--source-extract",
            str(source_extract_path),
            "--output-md",
            str(output_md_path),
        ]
    )

    markdown = output_md_path.read_text(encoding="utf-8")
    assert exit_code == 0
    assert "Evaluation Report" in markdown
    assert "Target name: `rsr_source_extract.json`" in markdown


def test_evaluate_rsr_source_extract_writes_json_and_markdown_together(
    tmp_path: Path,
) -> None:
    source_extract_path = _write_rsr_source_extract_artifact(tmp_path)
    output_json_path = tmp_path / "evaluation.json"
    output_md_path = tmp_path / "evaluation.md"

    exit_code = main(
        [
            "evaluate-rsr-source-extract",
            "--source-extract",
            str(source_extract_path),
            "--output-json",
            str(output_json_path),
            "--output-md",
            str(output_md_path),
        ]
    )

    assert exit_code == 0
    assert output_json_path.is_file()
    assert output_md_path.is_file()


def test_evaluate_rsr_source_extract_run_id_is_preserved_in_report(
    tmp_path: Path,
) -> None:
    run_id = uuid4()
    source_extract_path = _write_rsr_source_extract_artifact(tmp_path)
    output_json_path = tmp_path / "evaluation.json"

    exit_code = main(
        [
            "evaluate-rsr-source-extract",
            "--source-extract",
            str(source_extract_path),
            "--run-id",
            str(run_id),
            "--output-json",
            str(output_json_path),
        ]
    )

    data = _read_json(output_json_path)
    assert exit_code == 0
    assert data["run_id"] == str(run_id)


def test_evaluate_rsr_source_extract_command_output_includes_counts(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    source_extract_path = _write_rsr_source_extract_artifact(tmp_path)

    exit_code = main(
        [
            "evaluate-rsr-source-extract",
            "--source-extract",
            str(source_extract_path),
        ]
    )

    output = capsys.readouterr().out
    assert exit_code == 0
    assert "target_name=rsr_source_extract.json" in output
    assert "passed=True" in output
    assert "failed_count=" in output
    assert "warning_count=" in output
    assert "error_count=" in output


def test_evaluate_rsr_source_extract_missing_artifact_still_writes_failed_report(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    source_extract_path = tmp_path / "missing_rsr_source_extract.json"
    output_json_path = tmp_path / "evaluation.json"

    exit_code = main(
        [
            "evaluate-rsr-source-extract",
            "--source-extract",
            str(source_extract_path),
            "--output-json",
            str(output_json_path),
        ]
    )

    output = capsys.readouterr().out
    data = _read_json(output_json_path)
    assert exit_code == 0
    assert output_json_path.is_file()
    assert "passed=False" in output
    assert any(
        check["check_name"] == "artifact_exists" and check["status"] == "failed"
        for check in data["checks"]
    )


def test_evaluate_rsr_source_extract_invalid_run_id_fails_cleanly(
    tmp_path: Path,
) -> None:
    source_extract_path = _write_rsr_source_extract_artifact(tmp_path)

    with pytest.raises(SystemExit) as exc_info:
        main(
            [
                "evaluate-rsr-source-extract",
                "--source-extract",
                str(source_extract_path),
                "--run-id",
                "not-a-uuid",
            ]
        )

    assert exc_info.value.code == 2


def test_evaluate_rsr_source_extract_command_does_not_print_artifact_contents(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    source_extract_path = _write_rsr_source_extract_artifact(tmp_path)

    exit_code = main(
        [
            "evaluate-rsr-source-extract",
            "--source-extract",
            str(source_extract_path),
        ]
    )

    output = capsys.readouterr().out
    assert exit_code == 0
    assert "Synthetic review:" not in output
    assert "Synthetic Studio Listing" not in output
    assert "Sample Neighborhood" not in output


def test_build_review_insight_input_succeeds_for_valid_source_extract_artifact(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    source_extract_path = _write_rsr_source_extract_artifact(tmp_path)
    output_json_path = tmp_path / "review_insight_extraction_input.json"

    exit_code = main(
        [
            "build-review-insight-input",
            "--source-extract",
            str(source_extract_path),
            "--output-json",
            str(output_json_path),
        ]
    )

    output = capsys.readouterr().out
    data = _read_json(output_json_path)
    model = ReviewInsightExtractionInput.model_validate(data)
    assert exit_code == 0
    assert output_json_path.is_file()
    assert model.review_count == 3
    assert len(model.representative_reviews) == 3
    assert f"output={output_json_path}" in output
    assert "review_count=3" in output
    assert "representative_review_count=3" in output
    assert "rating_category_count=0" in output


def test_build_review_insight_input_default_output_path_is_created(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(tmp_path)
    source_extract_path = _write_rsr_source_extract_artifact(tmp_path)

    exit_code = main(
        [
            "build-review-insight-input",
            "--source-extract",
            str(source_extract_path),
        ]
    )

    output_path = Path("artifacts/readysetrentables/review_insight_extraction_input.json")
    assert exit_code == 0
    assert output_path.is_file()


def test_build_review_insight_input_output_json_writes_custom_path(tmp_path: Path) -> None:
    source_extract_path = _write_rsr_source_extract_artifact(tmp_path)
    output_json_path = tmp_path / "custom" / "input.json"

    exit_code = main(
        [
            "build-review-insight-input",
            "--source-extract",
            str(source_extract_path),
            "--output-json",
            str(output_json_path),
        ]
    )

    assert exit_code == 0
    assert output_json_path.is_file()
    ReviewInsightExtractionInput.model_validate(_read_json(output_json_path))


def test_build_review_insight_input_run_id_is_preserved_in_output_json(
    tmp_path: Path,
) -> None:
    source_extract_path = _write_rsr_source_extract_artifact(tmp_path)
    output_json_path = tmp_path / "input.json"
    run_id = uuid4()

    exit_code = main(
        [
            "build-review-insight-input",
            "--source-extract",
            str(source_extract_path),
            "--run-id",
            str(run_id),
            "--output-json",
            str(output_json_path),
        ]
    )

    data = _read_json(output_json_path)
    assert exit_code == 0
    assert data["run_id"] == str(run_id)


def test_build_review_insight_input_source_artifact_path_is_preserved(
    tmp_path: Path,
) -> None:
    source_extract_path = _write_rsr_source_extract_artifact(tmp_path)
    output_json_path = tmp_path / "input.json"
    source_artifact_path = Path("artifacts/readysetrentables/rsr_source_extract.json")

    exit_code = main(
        [
            "build-review-insight-input",
            "--source-extract",
            str(source_extract_path),
            "--source-artifact-path",
            str(source_artifact_path),
            "--output-json",
            str(output_json_path),
        ]
    )

    data = _read_json(output_json_path)
    assert exit_code == 0
    assert Path(data["source_artifact_path"]) == source_artifact_path


def test_build_review_insight_input_max_representative_reviews_limits_reviews(
    tmp_path: Path,
) -> None:
    source_extract_path = _write_rsr_source_extract_artifact(tmp_path)
    output_json_path = tmp_path / "input.json"

    exit_code = main(
        [
            "build-review-insight-input",
            "--source-extract",
            str(source_extract_path),
            "--max-representative-reviews",
            "2",
            "--output-json",
            str(output_json_path),
        ]
    )

    data = _read_json(output_json_path)
    assert exit_code == 0
    assert len(data["representative_reviews"]) == 2


def test_build_review_insight_input_allows_zero_representative_reviews(
    tmp_path: Path,
) -> None:
    source_extract_path = _write_rsr_source_extract_artifact(tmp_path)
    output_json_path = tmp_path / "input.json"

    exit_code = main(
        [
            "build-review-insight-input",
            "--source-extract",
            str(source_extract_path),
            "--max-representative-reviews",
            "0",
            "--output-json",
            str(output_json_path),
        ]
    )

    data = _read_json(output_json_path)
    assert exit_code == 0
    assert data["representative_reviews"] == []


def test_build_review_insight_input_negative_max_representative_reviews_fails_cleanly(
    tmp_path: Path,
) -> None:
    source_extract_path = _write_rsr_source_extract_artifact(tmp_path)

    with pytest.raises(SystemExit) as exc_info:
        main(
            [
                "build-review-insight-input",
                "--source-extract",
                str(source_extract_path),
                "--max-representative-reviews",
                "-1",
            ]
        )

    assert exc_info.value.code == 2


def test_build_review_insight_input_missing_source_extract_fails_cleanly(
    tmp_path: Path,
) -> None:
    with pytest.raises(SystemExit) as exc_info:
        main(
            [
                "build-review-insight-input",
                "--source-extract",
                str(tmp_path / "missing_rsr_source_extract.json"),
            ]
        )

    assert exc_info.value.code == 2


def test_build_review_insight_input_invalid_json_fails_cleanly_without_contents(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    source_extract_path = tmp_path / "rsr_source_extract.json"
    source_extract_path.write_text("{Synthetic review: not valid json", encoding="utf-8")

    with pytest.raises(SystemExit) as exc_info:
        main(["build-review-insight-input", "--source-extract", str(source_extract_path)])

    captured = capsys.readouterr()
    combined_output = captured.out + captured.err
    assert exc_info.value.code == 2
    assert "not valid JSON" in combined_output
    assert "Synthetic review:" not in combined_output


def test_build_review_insight_input_schema_invalid_json_fails_cleanly_without_contents(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    source_extract_path = tmp_path / "rsr_source_extract.json"
    source_extract_path.write_text(
        json.dumps({"review_text": "Synthetic review: hidden body"}),
        encoding="utf-8",
    )

    with pytest.raises(SystemExit) as exc_info:
        main(["build-review-insight-input", "--source-extract", str(source_extract_path)])

    captured = capsys.readouterr()
    combined_output = captured.out + captured.err
    assert exc_info.value.code == 2
    assert "expected schema" in combined_output
    assert "Synthetic review:" not in combined_output


def test_build_review_insight_input_invalid_run_id_fails_cleanly(
    tmp_path: Path,
) -> None:
    source_extract_path = _write_rsr_source_extract_artifact(tmp_path)

    with pytest.raises(SystemExit) as exc_info:
        main(
            [
                "build-review-insight-input",
                "--source-extract",
                str(source_extract_path),
                "--run-id",
                "not-a-uuid",
            ]
        )

    assert exc_info.value.code == 2


def test_build_review_insight_input_command_output_includes_safe_summary_counts(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    source_extract_path = _write_rsr_source_extract_artifact(tmp_path)
    output_json_path = tmp_path / "input.json"

    exit_code = main(
        [
            "build-review-insight-input",
            "--source-extract",
            str(source_extract_path),
            "--output-json",
            str(output_json_path),
        ]
    )

    output = capsys.readouterr().out
    assert exit_code == 0
    assert f"output={output_json_path}" in output
    assert "review_count=3" in output
    assert "representative_review_count=3" in output
    assert "rating_category_count=0" in output


def test_build_review_insight_input_command_does_not_print_review_text(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    source_extract_path = _write_rsr_source_extract_artifact(tmp_path)

    exit_code = main(["build-review-insight-input", "--source-extract", str(source_extract_path)])

    output = capsys.readouterr().out
    assert exit_code == 0
    assert "Synthetic review:" not in output
    assert "Synthetic Studio Listing" not in output


def test_build_review_insight_input_does_not_connect_to_db(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source_extract_path = _write_rsr_source_extract_artifact(tmp_path)

    def fail_if_called(*_: object, **__: object) -> object:
        msg = "Database connections should not be opened"
        raise AssertionError(msg)

    monkeypatch.setattr("daedalus.cli.connect_postgres", fail_if_called)
    monkeypatch.setattr("daedalus.cli.connect_rsr_source_postgres", fail_if_called)

    exit_code = main(["build-review-insight-input", "--source-extract", str(source_extract_path)])

    assert exit_code == 0


def test_build_review_insight_input_does_not_call_model_providers(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source_extract_path = _write_rsr_source_extract_artifact(tmp_path)

    def fail_if_called(*_: object, **__: object) -> object:
        msg = "Model providers should not be created"
        raise AssertionError(msg)

    monkeypatch.setattr("daedalus.cli.OllamaModelClient", fail_if_called)

    exit_code = main(["build-review-insight-input", "--source-extract", str(source_extract_path)])

    assert exit_code == 0


def test_extract_review_insights_ollama_succeeds_with_mocked_agent_path(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    input_path = _write_review_insight_input_artifact(tmp_path)
    output_path = tmp_path / "review_insights.json"
    state = _install_review_insights_ollama_cli_fakes(monkeypatch)

    exit_code = main(
        [
            "extract-review-insights-ollama",
            "--input-json",
            str(input_path),
            "--model",
            "llama3.1",
            "--output-json",
            str(output_path),
        ]
    )

    output = capsys.readouterr().out
    assert exit_code == 0
    assert output_path.is_file()
    assert len(state.clients) == 1
    assert len(state.agents) == 1
    assert len(state.inputs) == 1
    assert "Wrote Ollama review insights" in output


def test_extract_review_insights_ollama_requires_input_json() -> None:
    with pytest.raises(SystemExit) as exc_info:
        main(["extract-review-insights-ollama", "--model", "llama3.1"])

    assert exc_info.value.code == 2


def test_extract_review_insights_ollama_requires_model(
    tmp_path: Path,
) -> None:
    input_path = _write_review_insight_input_artifact(tmp_path)

    with pytest.raises(SystemExit) as exc_info:
        main(["extract-review-insights-ollama", "--input-json", str(input_path)])

    assert exc_info.value.code == 2


def test_extract_review_insights_ollama_default_output_path_is_created(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(tmp_path)
    input_path = _write_review_insight_input_artifact(tmp_path)
    _install_review_insights_ollama_cli_fakes(monkeypatch)

    exit_code = main(
        [
            "extract-review-insights-ollama",
            "--input-json",
            str(input_path),
            "--model",
            "llama3.1",
        ]
    )

    output_path = Path("artifacts/readysetrentables/review_insights.json")
    assert exit_code == 0
    assert output_path.is_file()


def test_extract_review_insights_ollama_output_json_writes_custom_path(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    input_path = _write_review_insight_input_artifact(tmp_path)
    output_path = tmp_path / "custom" / "review_insights.json"
    _install_review_insights_ollama_cli_fakes(monkeypatch)

    exit_code = main(
        [
            "extract-review-insights-ollama",
            "--input-json",
            str(input_path),
            "--model",
            "llama3.1",
            "--output-json",
            str(output_path),
        ]
    )

    assert exit_code == 0
    assert output_path.is_file()


def test_extract_review_insights_ollama_parses_review_insight_input(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    input_path = _write_review_insight_input_artifact(tmp_path)
    state = _install_review_insights_ollama_cli_fakes(monkeypatch)

    exit_code = main(
        [
            "extract-review-insights-ollama",
            "--input-json",
            str(input_path),
            "--model",
            "llama3.1",
        ]
    )

    assert exit_code == 0
    assert state.inputs[0].review_count == 2
    assert state.inputs[0].market_name == "Synthetic Market"


def test_extract_review_insights_ollama_passes_model_name_to_agent(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    input_path = _write_review_insight_input_artifact(tmp_path)
    state = _install_review_insights_ollama_cli_fakes(monkeypatch)

    exit_code = main(
        [
            "extract-review-insights-ollama",
            "--input-json",
            str(input_path),
            "--model",
            "llama3.1",
        ]
    )

    assert exit_code == 0
    assert state.agents[0].model_name == "llama3.1"
    assert state.clients[0].settings.model_name == "llama3.1"


def test_extract_review_insights_ollama_writes_valid_result_json(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    input_path = _write_review_insight_input_artifact(tmp_path)
    output_path = tmp_path / "review_insights.json"
    _install_review_insights_ollama_cli_fakes(monkeypatch)

    exit_code = main(
        [
            "extract-review-insights-ollama",
            "--input-json",
            str(input_path),
            "--model",
            "llama3.1",
            "--output-json",
            str(output_path),
        ]
    )

    result = ReviewInsightExtractionResult.model_validate(_read_json(output_path))
    assert exit_code == 0
    assert result.provider == ModelProvider.OLLAMA
    assert result.model_name == "llama3.1"
    assert result.themes[0].name == "arrival clarity"


def test_extract_review_insights_ollama_output_includes_safe_summary(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    input_path = _write_review_insight_input_artifact(tmp_path)
    output_path = tmp_path / "review_insights.json"
    _install_review_insights_ollama_cli_fakes(monkeypatch)

    exit_code = main(
        [
            "extract-review-insights-ollama",
            "--input-json",
            str(input_path),
            "--model",
            "llama3.1",
            "--output-json",
            str(output_path),
        ]
    )

    output = capsys.readouterr().out
    assert exit_code == 0
    assert f"output={output_path}" in output
    assert "provider=ollama" in output
    assert "model_name=llama3.1" in output
    assert "prompt_name=readysetrentables_review_insight_extraction" in output
    assert "prompt_version=v0" in output
    assert "theme_count=1" in output
    assert "strengths_count=1" in output
    assert "risks_count=1" in output
    assert "guest_expectations_count=1" in output
    assert "input_tokens=11" in output
    assert "output_tokens=7" in output
    assert "total_tokens=18" in output
    assert "estimated_cost_usd=0" in output


def test_extract_review_insights_ollama_missing_input_file_fails_cleanly(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    missing_path = tmp_path / "missing.json"

    with pytest.raises(SystemExit) as exc_info:
        main(
            [
                "extract-review-insights-ollama",
                "--input-json",
                str(missing_path),
                "--model",
                "llama3.1",
            ]
        )

    captured = capsys.readouterr()
    combined_output = captured.out + captured.err
    assert exc_info.value.code == 2
    assert "does not exist" in combined_output


def test_extract_review_insights_ollama_invalid_json_fails_cleanly(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    input_path = tmp_path / "review_insight_extraction_input.json"
    input_path.write_text("{Synthetic review: not valid json", encoding="utf-8")

    with pytest.raises(SystemExit) as exc_info:
        main(
            [
                "extract-review-insights-ollama",
                "--input-json",
                str(input_path),
                "--model",
                "llama3.1",
            ]
        )

    captured = capsys.readouterr()
    combined_output = captured.out + captured.err
    assert exc_info.value.code == 2
    assert "not valid JSON" in combined_output
    assert "Synthetic review:" not in combined_output


def test_extract_review_insights_ollama_schema_invalid_input_fails_cleanly(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    input_path = tmp_path / "review_insight_extraction_input.json"
    input_path.write_text(
        json.dumps({"representative_reviews": ["Synthetic review: hidden body"]}),
        encoding="utf-8",
    )

    with pytest.raises(SystemExit) as exc_info:
        main(
            [
                "extract-review-insights-ollama",
                "--input-json",
                str(input_path),
                "--model",
                "llama3.1",
            ]
        )

    captured = capsys.readouterr()
    combined_output = captured.out + captured.err
    assert exc_info.value.code == 2
    assert "expected schema" in combined_output
    assert "Synthetic review:" not in combined_output


def test_extract_review_insights_ollama_agent_failure_fails_cleanly(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    input_path = _write_review_insight_input_artifact(tmp_path)
    _install_review_insights_ollama_cli_fakes(
        monkeypatch,
        agent_error=ValueError(
            "Model output JSON did not match ReviewInsightExtractionResult schema."
        ),
    )

    with pytest.raises(SystemExit) as exc_info:
        main(
            [
                "extract-review-insights-ollama",
                "--input-json",
                str(input_path),
                "--model",
                "llama3.1",
            ]
        )

    captured = capsys.readouterr()
    combined_output = captured.out + captured.err
    assert exc_info.value.code == 2
    assert "Failed to extract review insights with local Ollama:" in combined_output
    assert "model output did not match the expected review insight JSON schema." in combined_output
    assert "ReviewInsightExtractionResult" not in combined_output
    assert "Synthetic review: hidden representative review." not in combined_output


def test_extract_review_insights_ollama_unknown_agent_failure_hides_raw_output(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    input_path = _write_review_insight_input_artifact(tmp_path)
    _install_review_insights_ollama_cli_fakes(
        monkeypatch,
        agent_error=ValueError("Raw model output should not leak."),
    )

    with pytest.raises(SystemExit) as exc_info:
        main(
            [
                "extract-review-insights-ollama",
                "--input-json",
                str(input_path),
                "--model",
                "llama3.1",
            ]
        )

    captured = capsys.readouterr()
    combined_output = captured.out + captured.err
    assert exc_info.value.code == 2
    assert "model output could not be converted to review insights." in combined_output
    assert "Raw model output should not leak." not in combined_output
    assert "Synthetic review: hidden representative review." not in combined_output


def test_extract_review_insights_ollama_timeout_reports_safe_category(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    input_path = _write_review_insight_input_artifact(tmp_path)
    _install_review_insights_ollama_cli_fakes(
        monkeypatch,
        agent_error=OllamaModelClientError(OLLAMA_REQUEST_TIMEOUT_MESSAGE),
    )

    with pytest.raises(SystemExit) as exc_info:
        main(
            [
                "extract-review-insights-ollama",
                "--input-json",
                str(input_path),
                "--model",
                "llama3.1",
            ]
        )

    captured = capsys.readouterr()
    combined_output = captured.out + captured.err
    assert exc_info.value.code == 2
    assert "Failed to extract review insights with local Ollama:" in combined_output
    assert "Ollama request timed out." in combined_output


def test_extract_review_insights_ollama_generic_client_error_reports_safe_category(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    input_path = _write_review_insight_input_artifact(tmp_path)
    _install_review_insights_ollama_cli_fakes(
        monkeypatch,
        agent_error=OllamaModelClientError("Ollama generate request failed with HTTP status 500."),
    )

    with pytest.raises(SystemExit) as exc_info:
        main(
            [
                "extract-review-insights-ollama",
                "--input-json",
                str(input_path),
                "--model",
                "llama3.1",
            ]
        )

    captured = capsys.readouterr()
    combined_output = captured.out + captured.err
    assert exc_info.value.code == 2
    assert "local Ollama request failed." in combined_output
    assert "HTTP status 500" not in combined_output


def test_extract_review_insights_ollama_command_does_not_print_sensitive_text(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    input_path = _write_review_insight_input_artifact(tmp_path)
    _install_review_insights_ollama_cli_fakes(monkeypatch)

    exit_code = main(
        [
            "extract-review-insights-ollama",
            "--input-json",
            str(input_path),
            "--model",
            "llama3.1",
        ]
    )

    output = capsys.readouterr().out
    assert exit_code == 0
    assert "Synthetic review: hidden representative review." not in output
    assert "Raw model output" not in output
    assert "Compact review insight input" not in output


def test_extract_review_insights_ollama_does_not_connect_to_db(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    input_path = _write_review_insight_input_artifact(tmp_path)
    _install_review_insights_ollama_cli_fakes(monkeypatch)

    def fail_if_called(*_: object, **__: object) -> object:
        raise AssertionError("Database connections should not be opened")

    monkeypatch.setattr("daedalus.cli.connect_postgres", fail_if_called)
    monkeypatch.setattr("daedalus.cli.connect_rsr_source_postgres", fail_if_called)

    exit_code = main(
        [
            "extract-review-insights-ollama",
            "--input-json",
            str(input_path),
            "--model",
            "llama3.1",
        ]
    )

    assert exit_code == 0


def test_extract_review_insights_ollama_does_not_call_claude_or_anthropic(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    input_path = _write_review_insight_input_artifact(tmp_path)
    _install_review_insights_ollama_cli_fakes(monkeypatch)

    exit_code = main(
        [
            "extract-review-insights-ollama",
            "--input-json",
            str(input_path),
            "--model",
            "llama3.1",
        ]
    )

    assert exit_code == 0


def test_extract_review_insights_ollama_tests_do_not_call_real_ollama(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    input_path = _write_review_insight_input_artifact(tmp_path)
    state = _install_review_insights_ollama_cli_fakes(monkeypatch)

    exit_code = main(
        [
            "extract-review-insights-ollama",
            "--input-json",
            str(input_path),
            "--model",
            "llama3.1",
        ]
    )

    assert exit_code == 0
    assert len(state.clients) == 1
    assert state.clients[0].settings.enabled is True


def test_compare_review_theme_summaries_succeeds_for_valid_artifacts(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    baseline, candidate = _write_two_summaries(tmp_path)
    output_json_path = tmp_path / "comparison.json"

    exit_code = main(
        [
            "compare-review-theme-summaries",
            "--baseline",
            str(baseline),
            "--candidate",
            str(candidate),
            "--output-json",
            str(output_json_path),
        ]
    )

    output = capsys.readouterr().out
    assert exit_code == 0
    assert output_json_path.is_file()
    assert "passed=" in output


def test_compare_review_theme_summaries_default_json_output_path_is_created(
    tmp_path: Path,
) -> None:
    baseline, candidate = _write_two_summaries(tmp_path)

    exit_code = main(
        [
            "compare-review-theme-summaries",
            "--baseline",
            str(baseline),
            "--candidate",
            str(candidate),
        ]
    )

    assert exit_code == 0
    assert (tmp_path / "candidate" / "review_theme_summary.comparison.json").is_file()


def test_compare_review_theme_summaries_output_json_writes_report(tmp_path: Path) -> None:
    baseline, candidate = _write_two_summaries(tmp_path)
    output_json_path = tmp_path / "out.json"

    exit_code = main(
        [
            "compare-review-theme-summaries",
            "--baseline",
            str(baseline),
            "--candidate",
            str(candidate),
            "--output-json",
            str(output_json_path),
        ]
    )

    data = _read_json(output_json_path)
    assert exit_code == 0
    assert data["target_type"] == "review_theme_summary"
    assert data["comparator_name"] == "readysetrentables_review_theme_summary_basic_comparison"


def test_compare_review_theme_summaries_output_md_writes_report(tmp_path: Path) -> None:
    baseline, candidate = _write_two_summaries(tmp_path)
    output_md_path = tmp_path / "out.md"

    exit_code = main(
        [
            "compare-review-theme-summaries",
            "--baseline",
            str(baseline),
            "--candidate",
            str(candidate),
            "--output-md",
            str(output_md_path),
        ]
    )

    markdown = output_md_path.read_text(encoding="utf-8")
    assert exit_code == 0
    assert "Evaluation Comparison Report" in markdown
    assert "Target name: `review_theme_summary`" in markdown


def test_compare_review_theme_summaries_writes_json_and_md_together(
    tmp_path: Path,
) -> None:
    baseline, candidate = _write_two_summaries(tmp_path)
    output_json_path = tmp_path / "out.json"
    output_md_path = tmp_path / "out.md"

    exit_code = main(
        [
            "compare-review-theme-summaries",
            "--baseline",
            str(baseline),
            "--candidate",
            str(candidate),
            "--output-json",
            str(output_json_path),
            "--output-md",
            str(output_md_path),
        ]
    )

    assert exit_code == 0
    assert output_json_path.is_file()
    assert output_md_path.is_file()


def test_compare_review_theme_summaries_baseline_report_id_is_preserved(
    tmp_path: Path,
) -> None:
    baseline, candidate = _write_two_summaries(tmp_path)
    baseline_report_id = uuid4()
    output_json_path = tmp_path / "out.json"

    exit_code = main(
        [
            "compare-review-theme-summaries",
            "--baseline",
            str(baseline),
            "--candidate",
            str(candidate),
            "--baseline-report-id",
            str(baseline_report_id),
            "--output-json",
            str(output_json_path),
        ]
    )

    data = _read_json(output_json_path)
    assert exit_code == 0
    assert data["baseline_report_id"] == str(baseline_report_id)


def test_compare_review_theme_summaries_candidate_report_id_is_preserved(
    tmp_path: Path,
) -> None:
    baseline, candidate = _write_two_summaries(tmp_path)
    candidate_report_id = uuid4()
    output_json_path = tmp_path / "out.json"

    exit_code = main(
        [
            "compare-review-theme-summaries",
            "--baseline",
            str(baseline),
            "--candidate",
            str(candidate),
            "--candidate-report-id",
            str(candidate_report_id),
            "--output-json",
            str(output_json_path),
        ]
    )

    data = _read_json(output_json_path)
    assert exit_code == 0
    assert data["candidate_report_id"] == str(candidate_report_id)


def test_compare_review_theme_summaries_output_includes_target_name(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    baseline, candidate = _write_two_summaries(tmp_path)

    exit_code = main(
        [
            "compare-review-theme-summaries",
            "--baseline",
            str(baseline),
            "--candidate",
            str(candidate),
        ]
    )

    output = capsys.readouterr().out
    assert exit_code == 0
    assert "target_name=review_theme_summary" in output


def test_compare_review_theme_summaries_output_includes_passed(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    baseline, candidate = _write_two_summaries(tmp_path)

    exit_code = main(
        [
            "compare-review-theme-summaries",
            "--baseline",
            str(baseline),
            "--candidate",
            str(candidate),
        ]
    )

    output = capsys.readouterr().out
    assert exit_code == 0
    assert "passed=" in output


def test_compare_review_theme_summaries_output_includes_counts(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    baseline, candidate = _write_two_summaries(tmp_path)

    exit_code = main(
        [
            "compare-review-theme-summaries",
            "--baseline",
            str(baseline),
            "--candidate",
            str(candidate),
        ]
    )

    output = capsys.readouterr().out
    assert exit_code == 0
    assert "different_count=" in output
    assert "improved_count=" in output
    assert "regressed_count=" in output
    assert "inconclusive_count=" in output


def test_compare_review_theme_summaries_missing_baseline_still_writes_report(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    baseline = tmp_path / "missing_baseline" / "review_theme_summary.md"
    candidate_dir = tmp_path / "candidate"
    candidate_dir.mkdir(parents=True, exist_ok=True)
    candidate = _write_review_theme_summary_markdown_artifact(candidate_dir)
    output_json_path = tmp_path / "out.json"

    exit_code = main(
        [
            "compare-review-theme-summaries",
            "--baseline",
            str(baseline),
            "--candidate",
            str(candidate),
            "--output-json",
            str(output_json_path),
        ]
    )

    data = _read_json(output_json_path)
    assert exit_code == 0
    assert output_json_path.is_file()
    assert any(
        c["comparison_name"] == "baseline_artifact_exists" and c["status"] != "match"
        for c in data["comparisons"]
    )


def test_compare_review_theme_summaries_missing_candidate_still_writes_report(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    baseline_dir = tmp_path / "baseline"
    baseline_dir.mkdir(parents=True, exist_ok=True)
    baseline = _write_review_theme_summary_markdown_artifact(baseline_dir)
    candidate = tmp_path / "missing_candidate" / "review_theme_summary.md"
    output_json_path = tmp_path / "out.json"

    exit_code = main(
        [
            "compare-review-theme-summaries",
            "--baseline",
            str(baseline),
            "--candidate",
            str(candidate),
            "--output-json",
            str(output_json_path),
        ]
    )

    data = _read_json(output_json_path)
    assert exit_code == 0
    assert output_json_path.is_file()
    assert any(
        c["comparison_name"] == "candidate_artifact_exists" and c["status"] != "match"
        for c in data["comparisons"]
    )


def test_compare_review_theme_summaries_invalid_baseline_report_id_fails_cleanly(
    tmp_path: Path,
) -> None:
    baseline, candidate = _write_two_summaries(tmp_path)

    with pytest.raises(SystemExit) as exc_info:
        main(
            [
                "compare-review-theme-summaries",
                "--baseline",
                str(baseline),
                "--candidate",
                str(candidate),
                "--baseline-report-id",
                "not-a-uuid",
            ]
        )

    assert exc_info.value.code == 2


def test_compare_review_theme_summaries_invalid_candidate_report_id_fails_cleanly(
    tmp_path: Path,
) -> None:
    baseline, candidate = _write_two_summaries(tmp_path)

    with pytest.raises(SystemExit) as exc_info:
        main(
            [
                "compare-review-theme-summaries",
                "--baseline",
                str(baseline),
                "--candidate",
                str(candidate),
                "--candidate-report-id",
                "not-a-uuid",
            ]
        )

    assert exc_info.value.code == 2


def test_compare_review_theme_summaries_does_not_print_baseline_contents(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    baseline, candidate = _write_two_summaries(tmp_path)

    exit_code = main(
        [
            "compare-review-theme-summaries",
            "--baseline",
            str(baseline),
            "--candidate",
            str(candidate),
        ]
    )

    output = capsys.readouterr().out
    assert exit_code == 0
    assert "Artifact body that must stay out of stdout." not in output
    assert "ReadySetRentables Review Theme Summary" not in output


def test_compare_review_theme_summaries_does_not_print_candidate_contents(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    baseline_dir = tmp_path / "baseline"
    baseline_dir.mkdir(parents=True, exist_ok=True)
    baseline = _write_review_theme_summary_markdown_artifact(baseline_dir)
    candidate_body = "Candidate body that must stay out of stdout."
    candidate = tmp_path / "candidate" / "review_theme_summary.md"
    candidate.parent.mkdir(parents=True, exist_ok=True)
    candidate.write_text(
        "\n".join(
            [
                "# ReadySetRentables Review Theme Summary",
                "",
                "- Run ID: `00000000-0000-0000-0000-000000000001`",
                "- Prompt: `readysetrentables/review_theme_summary`",
                "- Prompt version: `v0`",
                "- Model provider: `ollama`",
                "- Model name: `llama3.1`",
                "",
                "## Summary",
                "",
                candidate_body,
                "",
                "## Token And Cost Metadata",
                "",
                "- Input tokens: 100",
                "- Output tokens: 200",
                "- Total tokens: 300",
                "- Estimated cost USD: 0",
                "",
            ]
        ),
        encoding="utf-8",
    )

    exit_code = main(
        [
            "compare-review-theme-summaries",
            "--baseline",
            str(baseline),
            "--candidate",
            str(candidate),
        ]
    )

    output = capsys.readouterr().out
    assert exit_code == 0
    assert candidate_body not in output


def test_summarize_review_themes_ollama_command_succeeds_with_mocked_client(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    SuccessfulOllamaClient.created_clients.clear()
    input_path = _write_normalized_reviews_json(tmp_path)
    output_path = tmp_path / "review_theme_summary.md"
    run_id = uuid4()
    monkeypatch.setattr("daedalus.cli.OllamaModelClient", SuccessfulOllamaClient)

    exit_code = main(
        [
            "summarize-review-themes-ollama",
            "--input",
            str(input_path),
            "--output",
            str(output_path),
            "--model",
            "llama3.1",
            "--run-id",
            str(run_id),
        ]
    )

    output = capsys.readouterr().out
    assert exit_code == 0
    assert output_path.is_file()
    assert str(run_id) in output
    assert f"output={output_path}" in output
    assert "provider=ollama" in output
    assert "model_name=llama3.1" in output
    assert "total_tokens=7" in output
    assert "estimated_cost_usd=0" in output
    assert "artifact_persisted=no" in output
    assert "invocation_persisted=no" in output


def test_summarize_review_themes_ollama_without_persistence_does_not_connect_to_postgres(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    input_path = _write_normalized_reviews_json(tmp_path)
    output_path = tmp_path / "review_theme_summary.md"
    monkeypatch.setattr("daedalus.cli.OllamaModelClient", SuccessfulOllamaClient)

    def fail_if_called(_: object) -> object:
        raise AssertionError("Postgres should not be opened without persistence flags")

    monkeypatch.setattr("daedalus.cli.connect_postgres", fail_if_called)

    exit_code = main(
        [
            "summarize-review-themes-ollama",
            "--input",
            str(input_path),
            "--output",
            str(output_path),
            "--model",
            "llama3.1",
        ]
    )

    assert exit_code == 0


def test_summarize_review_themes_ollama_persist_invocation_requires_run_id(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    input_path = _write_normalized_reviews_json(tmp_path)
    output_path = tmp_path / "review_theme_summary.md"

    def fail_if_called(_: object) -> object:
        raise AssertionError("Postgres should not be opened without --run-id")

    monkeypatch.setattr("daedalus.cli.connect_postgres", fail_if_called)

    with pytest.raises(SystemExit) as exc_info:
        main(
            [
                "summarize-review-themes-ollama",
                "--input",
                str(input_path),
                "--output",
                str(output_path),
                "--model",
                "llama3.1",
                "--persist-invocation",
            ]
        )

    assert exc_info.value.code == 2


def test_summarize_review_themes_ollama_persist_artifact_requires_run_id(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    input_path = _write_normalized_reviews_json(tmp_path)
    output_path = tmp_path / "review_theme_summary.md"

    def fail_if_called(_: object) -> object:
        raise AssertionError("Postgres should not be opened without --run-id")

    monkeypatch.setattr("daedalus.cli.connect_postgres", fail_if_called)

    with pytest.raises(SystemExit) as exc_info:
        main(
            [
                "summarize-review-themes-ollama",
                "--input",
                str(input_path),
                "--output",
                str(output_path),
                "--model",
                "llama3.1",
                "--persist-artifact",
            ]
        )

    assert exc_info.value.code == 2


def test_summarize_review_themes_ollama_persist_invocation_records_model_invocation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    connection = FakeModelInvocationConnection()
    settings = PostgresSettings(
        host="placeholder-host",
        port=5433,
        database="placeholder-db",
        user="placeholder-user",
        password="placeholder-password",
    )
    run_id = uuid4()
    input_path = _write_normalized_reviews_json(tmp_path)
    output_path = tmp_path / "review_theme_summary.md"

    monkeypatch.setattr("daedalus.cli.OllamaModelClient", SuccessfulOllamaClient)
    monkeypatch.setattr("daedalus.cli.load_postgres_settings", lambda: settings)
    monkeypatch.setattr("daedalus.cli.connect_postgres", lambda _: connection)

    exit_code = main(
        [
            "summarize-review-themes-ollama",
            "--input",
            str(input_path),
            "--output",
            str(output_path),
            "--model",
            "llama3.1",
            "--run-id",
            str(run_id),
            "--persist-invocation",
        ]
    )

    output = capsys.readouterr().out
    assert exit_code == 0
    assert output_path.is_file()
    assert "provider=ollama" in output
    assert "model_name=llama3.1" in output
    assert "total_tokens=7" in output
    assert "estimated_cost_usd=0" in output
    assert "artifact_persisted=no" in output
    assert "invocation_persisted=yes" in output
    assert "Raw local model output should not be printed." not in output
    assert "Bright apartment with a spotless kitchen" not in output
    assert any("insert into model_invocations" in sql.lower() for sql in connection.executed_sql)
    assert not any(
        "insert into workflow_artifacts" in sql.lower() for sql in connection.executed_sql
    )
    assert connection.executed_params[0][1] == run_id
    assert connection.executed_params[0][4] == ModelProvider.OLLAMA.value
    assert connection.executed_params[0][5] == "llama3.1"
    assert connection.executed_params[0][6] == "readysetrentables/review_theme_summary"
    assert connection.executed_params[0][7] == "v0"
    assert connection.executed_params[0][8] == 4
    assert connection.executed_params[0][9] == 3
    assert connection.executed_params[0][10] == 7
    assert connection.executed_params[0][12] == ModelInvocationStatus.SUCCEEDED.value
    assert connection.committed is True
    assert connection.rolled_back is False
    assert connection.closed is True


def test_summarize_review_themes_ollama_persist_artifact_records_review_theme_summary(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    connection = FakeModelInvocationConnection()
    settings = PostgresSettings(
        host="placeholder-host",
        port=5433,
        database="placeholder-db",
        user="placeholder-user",
        password="placeholder-password",
    )
    run_id = uuid4()
    input_path = _write_normalized_reviews_json(tmp_path)
    output_path = tmp_path / "review_theme_summary.md"

    monkeypatch.setattr("daedalus.cli.OllamaModelClient", SuccessfulOllamaClient)
    monkeypatch.setattr("daedalus.cli.load_postgres_settings", lambda: settings)
    monkeypatch.setattr("daedalus.cli.connect_postgres", lambda _: connection)

    exit_code = main(
        [
            "summarize-review-themes-ollama",
            "--input",
            str(input_path),
            "--output",
            str(output_path),
            "--model",
            "llama3.1",
            "--run-id",
            str(run_id),
            "--persist-artifact",
        ]
    )

    output = capsys.readouterr().out
    assert exit_code == 0
    assert output_path.is_file()
    assert "artifact_persisted=yes" in output
    assert "invocation_persisted=no" in output
    assert "Raw local model output should not be printed." not in output
    assert "Bright apartment with a spotless kitchen" not in output
    assert "ReadySetRentables Review Theme Summary" not in output
    assert any("insert into workflow_artifacts" in sql.lower() for sql in connection.executed_sql)
    assert not any(
        "insert into model_invocations" in sql.lower() for sql in connection.executed_sql
    )
    assert connection.executed_params[0][1] == run_id
    assert connection.executed_params[0][2] == ArtifactType.REVIEW_THEME_SUMMARY.value
    assert connection.executed_params[0][3] == str(output_path)
    assert connection.committed is True
    assert connection.rolled_back is False
    assert connection.closed is True


def test_summarize_review_themes_ollama_persist_artifact_and_invocation_records_both(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    connection = FakeModelInvocationConnection()
    settings = PostgresSettings(
        host="placeholder-host",
        port=5433,
        database="placeholder-db",
        user="placeholder-user",
        password="placeholder-password",
    )
    run_id = uuid4()
    input_path = _write_normalized_reviews_json(tmp_path)
    output_path = tmp_path / "review_theme_summary.md"

    monkeypatch.setattr("daedalus.cli.OllamaModelClient", SuccessfulOllamaClient)
    monkeypatch.setattr("daedalus.cli.load_postgres_settings", lambda: settings)
    monkeypatch.setattr("daedalus.cli.connect_postgres", lambda _: connection)

    exit_code = main(
        [
            "summarize-review-themes-ollama",
            "--input",
            str(input_path),
            "--output",
            str(output_path),
            "--model",
            "llama3.1",
            "--run-id",
            str(run_id),
            "--persist-artifact",
            "--persist-invocation",
        ]
    )

    output = capsys.readouterr().out
    assert exit_code == 0
    assert "artifact_persisted=yes" in output
    assert "invocation_persisted=yes" in output
    assert any("insert into model_invocations" in sql.lower() for sql in connection.executed_sql)
    assert any("insert into workflow_artifacts" in sql.lower() for sql in connection.executed_sql)
    assert connection.committed is True
    assert connection.rolled_back is False
    assert connection.closed is True


def test_summarize_review_themes_ollama_persist_invocation_rolls_back_on_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    connection = FakeModelInvocationConnection()
    settings = PostgresSettings(
        host="placeholder-host",
        port=5433,
        database="placeholder-db",
        user="placeholder-user",
        password="placeholder-password",
    )
    input_path = _write_normalized_reviews_json(tmp_path)
    output_path = tmp_path / "review_theme_summary.md"

    monkeypatch.setattr("daedalus.cli.OllamaModelClient", FailingOllamaClient)
    monkeypatch.setattr("daedalus.cli.load_postgres_settings", lambda: settings)
    monkeypatch.setattr("daedalus.cli.connect_postgres", lambda _: connection)

    with pytest.raises(SystemExit) as exc_info:
        main(
            [
                "summarize-review-themes-ollama",
                "--input",
                str(input_path),
                "--output",
                str(output_path),
                "--model",
                "llama3.1",
                "--run-id",
                str(uuid4()),
                "--persist-invocation",
            ]
        )

    captured = capsys.readouterr()
    combined_output = captured.out + captured.err
    assert exc_info.value.code == 2
    assert connection.committed is False
    assert connection.rolled_back is True
    assert connection.closed is True
    assert "Bright apartment with a spotless kitchen" not in combined_output
    assert "Prompt template:" not in combined_output


def test_summarize_review_themes_ollama_persist_artifact_rolls_back_on_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    connection = FailingArtifactConnection()
    settings = PostgresSettings(
        host="placeholder-host",
        port=5433,
        database="placeholder-db",
        user="placeholder-user",
        password="placeholder-password",
    )
    input_path = _write_normalized_reviews_json(tmp_path)
    output_path = tmp_path / "review_theme_summary.md"

    monkeypatch.setattr("daedalus.cli.OllamaModelClient", SuccessfulOllamaClient)
    monkeypatch.setattr("daedalus.cli.load_postgres_settings", lambda: settings)
    monkeypatch.setattr("daedalus.cli.connect_postgres", lambda _: connection)

    with pytest.raises(SystemExit) as exc_info:
        main(
            [
                "summarize-review-themes-ollama",
                "--input",
                str(input_path),
                "--output",
                str(output_path),
                "--model",
                "llama3.1",
                "--run-id",
                str(uuid4()),
                "--persist-artifact",
            ]
        )

    captured = capsys.readouterr()
    combined_output = captured.out + captured.err
    assert exc_info.value.code == 2
    assert connection.committed is False
    assert connection.rolled_back is True
    assert connection.closed is True
    assert "Raw local model output should not be printed." not in combined_output
    assert "ReadySetRentables Review Theme Summary" not in combined_output


def test_summarize_review_themes_ollama_command_output_omits_raw_text(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    input_path = _write_normalized_reviews_json(tmp_path)
    output_path = tmp_path / "review_theme_summary.md"
    monkeypatch.setattr("daedalus.cli.OllamaModelClient", SuccessfulOllamaClient)

    exit_code = main(
        [
            "summarize-review-themes-ollama",
            "--input",
            str(input_path),
            "--output",
            str(output_path),
            "--model",
            "llama3.1",
        ]
    )

    output = capsys.readouterr().out
    assert exit_code == 0
    assert "ReadySetRentables Review Theme Summary" not in output
    assert "Raw local model output should not be printed." not in output
    assert "Bright apartment with a spotless kitchen" not in output
    assert "Prompt template:" not in output


def test_summarize_review_themes_ollama_handles_model_client_error_cleanly(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    input_path = _write_normalized_reviews_json(tmp_path)
    output_path = tmp_path / "review_theme_summary.md"
    monkeypatch.setattr("daedalus.cli.OllamaModelClient", FailingOllamaClient)

    with pytest.raises(SystemExit) as exc_info:
        main(
            [
                "summarize-review-themes-ollama",
                "--input",
                str(input_path),
                "--output",
                str(output_path),
                "--model",
                "llama3.1",
            ]
        )

    captured = capsys.readouterr()
    combined_output = captured.out + captured.err
    assert exc_info.value.code == 2
    assert "local Ollama smoke check failed safely" in combined_output
    assert "Bright apartment with a spotless kitchen" not in combined_output
    assert "Prompt template:" not in combined_output


def test_summarize_review_themes_ollama_invalid_representative_review_limit_fails_cleanly(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    input_path = _write_normalized_reviews_json(tmp_path)
    output_path = tmp_path / "review_theme_summary.md"

    def fail_if_called(*_: object, **__: object) -> object:
        raise AssertionError("OllamaModelClient should not be created for invalid limits")

    monkeypatch.setattr("daedalus.cli.OllamaModelClient", fail_if_called)

    with pytest.raises(SystemExit) as exc_info:
        main(
            [
                "summarize-review-themes-ollama",
                "--input",
                str(input_path),
                "--output",
                str(output_path),
                "--model",
                "llama3.1",
                "--max-representative-reviews",
                "-1",
            ]
        )

    assert exc_info.value.code == 2


def test_ollama_smoke_check_succeeds_with_mocked_client(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr("daedalus.cli.OllamaModelClient", SuccessfulOllamaClient)

    exit_code = main(
        [
            "ollama-smoke-check",
            "--model",
            "llama3.1",
            "--prompt",
            "Raw smoke check prompt should not be printed.",
        ]
    )

    output = capsys.readouterr().out
    assert exit_code == 0
    assert "Ollama smoke check succeeded" in output
    assert "provider=ollama" in output
    assert "model_name=llama3.1" in output
    assert "input_tokens=4" in output
    assert "output_tokens=3" in output
    assert "total_tokens=7" in output
    assert "estimated_cost_usd=0" in output
    assert "Raw smoke check prompt should not be printed." not in output
    assert "Raw local model output should not be printed." not in output


def test_ollama_smoke_check_passes_configuration_to_mocked_client(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    SuccessfulOllamaClient.created_clients.clear()
    monkeypatch.setattr("daedalus.cli.OllamaModelClient", SuccessfulOllamaClient)

    exit_code = main(
        [
            "ollama-smoke-check",
            "--model",
            "llama3.1",
            "--base-url",
            "http://localhost:11434",
            "--timeout-seconds",
            "2.5",
        ]
    )

    assert exit_code == 0
    client = SuccessfulOllamaClient.created_clients[0]
    assert client.settings.enabled is True
    assert client.settings.base_url == "http://localhost:11434"
    assert client.settings.model_name == "llama3.1"
    assert client.settings.request_timeout_seconds == 2.5


def test_ollama_smoke_check_handles_model_client_error_cleanly(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr("daedalus.cli.OllamaModelClient", FailingOllamaClient)

    with pytest.raises(SystemExit) as exc_info:
        main(
            [
                "ollama-smoke-check",
                "--model",
                "llama3.1",
                "--prompt",
                "Raw smoke check prompt should not be printed.",
            ]
        )

    captured = capsys.readouterr()
    combined_output = captured.out + captured.err
    assert exc_info.value.code == 2
    assert "local Ollama smoke check failed safely" in combined_output
    assert "Raw smoke check prompt should not be printed." not in combined_output


def test_show_run_command_succeeds_with_mocked_persistence(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    run_id = uuid4()
    details = _workflow_run_details(run_id)

    monkeypatch.setattr("daedalus.cli.load_workflow_run_details", lambda _: details)

    exit_code = main(["show-run", "--run-id", str(run_id)])

    output = capsys.readouterr().out
    assert exit_code == 0
    assert str(run_id) in output
    assert "workflow_name: readysetrentables_review_normalization" in output
    assert "status: completed" in output
    assert "duration_ms: 60000" in output
    assert "output_artifact_path: normalized_reviews.json" in output
    assert "- normalized_reviews: normalized_reviews.json" in output
    assert "- workflow_summary: normalized_reviews.summary.md" in output
    assert "steps:" in output
    assert "- load_reviews: status=completed duration_ms=50" in output
    assert "- write_artifact: status=failed duration_ms=75 error_message=write failed" in output
    assert "Model Invocations:" in output
    assert "provider=fake" in output
    assert "model_name=fake-local-model" in output
    assert "prompt_name=summarize_reviews" in output
    assert "status=succeeded" in output


def test_show_run_command_displays_review_insights_artifact(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    run_id = uuid4()
    details = _workflow_run_details(
        run_id,
        artifact_records=[
            ArtifactRecord.create(
                run_id=run_id,
                artifact_type=ArtifactType.REVIEW_INSIGHTS,
                artifact_path=Path("artifacts/readysetrentables/review_insights.json"),
            )
        ],
    )

    monkeypatch.setattr("daedalus.cli.load_workflow_run_details", lambda _: details)

    exit_code = main(["show-run", "--run-id", str(run_id)])

    output = capsys.readouterr().out
    assert exit_code == 0
    assert "- review_insights: artifacts/readysetrentables/review_insights.json" in output


def test_show_run_command_handles_no_steps_cleanly(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    run_id = uuid4()
    details = _workflow_run_details(run_id, step_records=[])

    monkeypatch.setattr("daedalus.cli.load_workflow_run_details", lambda _: details)

    exit_code = main(["show-run", "--run-id", str(run_id)])

    output = capsys.readouterr().out
    assert exit_code == 0
    assert "- normalized_reviews: normalized_reviews.json" in output
    assert "steps:" in output
    assert "No workflow steps recorded." in output


def test_show_run_command_handles_no_model_invocations_cleanly(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    run_id = uuid4()
    details = _workflow_run_details(run_id, model_invocation_records=[])

    monkeypatch.setattr("daedalus.cli.load_workflow_run_details", lambda _: details)

    exit_code = main(["show-run", "--run-id", str(run_id)])

    output = capsys.readouterr().out
    assert exit_code == 0
    assert "Model Invocations:" in output
    assert "No model invocations recorded." in output


def test_show_run_command_missing_run_fails_cleanly(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    run_id = uuid4()

    def fail_load(_: object) -> WorkflowRunDetails:
        msg = f"Workflow run not found: run_id={run_id}"
        raise WorkflowRunNotFoundError(msg)

    monkeypatch.setattr("daedalus.cli.load_workflow_run_details", fail_load)

    with pytest.raises(SystemExit) as exc_info:
        main(["show-run", "--run-id", str(run_id)])

    assert exc_info.value.code == 2


def test_show_run_command_invalid_uuid_fails_cleanly() -> None:
    with pytest.raises(SystemExit) as exc_info:
        main(["show-run", "--run-id", "not-a-uuid"])

    assert exc_info.value.code == 2


def test_list_runs_command_succeeds_with_mocked_persistence(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    first_run_id = uuid4()
    second_run_id = uuid4()
    listed_calls: list[tuple[int, str | None, str | None]] = []

    def fake_list(
        *,
        limit: int,
        domain: str | None,
        status: str | None,
    ) -> list[WorkflowRunRecord]:
        listed_calls.append((limit, domain, status))
        return [
            _workflow_run_details(first_run_id).run_record,
            _workflow_run_details(second_run_id).run_record,
        ]

    monkeypatch.setattr("daedalus.cli.load_recent_workflow_runs", fake_list)

    exit_code = main(
        [
            "list-runs",
            "--limit",
            "5",
            "--domain",
            "readysetrentables_reviews",
            "--status",
            "completed",
        ]
    )

    output = capsys.readouterr().out
    assert exit_code == 0
    assert listed_calls == [(5, "readysetrentables_reviews", "completed")]
    assert str(first_run_id) in output
    assert str(second_run_id) in output
    assert "workflow_name=readysetrentables_review_normalization" in output
    assert "status=completed" in output
    assert "duration_ms=60000" in output


def test_list_runs_command_prints_message_when_no_runs_exist(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr("daedalus.cli.load_recent_workflow_runs", lambda **_: [])

    exit_code = main(["list-runs"])

    assert exit_code == 0
    assert "No workflow runs found." in capsys.readouterr().out


def test_list_runs_command_invalid_limit_fails_cleanly(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fail_if_called(**_: object) -> list[WorkflowRunRecord]:
        msg = "DB should not be called for invalid limits"
        raise AssertionError(msg)

    monkeypatch.setattr("daedalus.cli.load_recent_workflow_runs", fail_if_called)

    with pytest.raises(SystemExit) as exc_info:
        main(["list-runs", "--limit", "0"])

    assert exc_info.value.code == 2


def _write_readysetrentables_manifest(
    tmp_path: Path,
    *,
    requires_human_approval: bool,
) -> Path:
    manifest_path = tmp_path / "readysetrentables.yaml"
    manifest_path.write_text(
        "\n".join(
            [
                "workflow_name: readysetrentables_review_normalization",
                "domain: readysetrentables_reviews",
                "description: Approval gate test workflow.",
                f"input_csv_path: {SAMPLE_CSV_PATH}",
                f"output_json_path: {tmp_path / 'normalized_reviews.json'}",
                f"requires_human_approval: {str(requires_human_approval).lower()}",
            ]
        ),
        encoding="utf-8",
    )
    return manifest_path


def _review_normalization_result(output_json_path: Path) -> ReviewNormalizationWorkflowResult:
    run_id = uuid4()
    return ReviewNormalizationWorkflowResult(
        source_csv_path=SAMPLE_CSV_PATH,
        output_json_path=output_json_path,
        metadata_json_path=output_json_path.with_name(f"{output_json_path.stem}.metadata.json"),
        summary_markdown_path=output_json_path.with_name(f"{output_json_path.stem}.summary.md"),
        run_record_json_path=output_json_path.with_name(f"{output_json_path.stem}.run.json"),
        review_count=8,
        run_id=run_id,
        approval_required=False,
        approved=False,
        steps=[WorkflowStepRecord.start(run_id=run_id, step_name="load_reviews").complete()],
    )


def _write_normalized_reviews_json(tmp_path: Path) -> Path:
    batch = load_airbnb_reviews_csv(SAMPLE_CSV_PATH)
    output_path = tmp_path / "normalized_reviews.json"
    return write_review_batch_json(batch, output_path)


def _write_two_summaries(tmp_path: Path) -> tuple[Path, Path]:
    baseline_dir = tmp_path / "baseline"
    baseline_dir.mkdir(parents=True, exist_ok=True)
    candidate_dir = tmp_path / "candidate"
    candidate_dir.mkdir(parents=True, exist_ok=True)
    baseline = _write_review_theme_summary_markdown_artifact(baseline_dir)
    candidate = _write_review_theme_summary_markdown_artifact(candidate_dir)
    return baseline, candidate


def _write_review_theme_summary_markdown_artifact(
    tmp_path: Path,
    *,
    run_id: UUID | None = None,
) -> Path:
    summary_run_id = run_id or uuid4()
    output_path = tmp_path / "review_theme_summary.md"
    output_path.write_text(
        "\n".join(
            [
                "# ReadySetRentables Review Theme Summary",
                "",
                f"- Run ID: `{summary_run_id}`",
                "- Prompt: `readysetrentables/review_theme_summary`",
                "- Prompt version: `v0`",
                "- Model provider: `fake`",
                "- Model name: `fake-model`",
                "",
                "## Summary",
                "",
                "Artifact body that must stay out of stdout.",
                "",
                "## Token And Cost Metadata",
                "",
                "- Input tokens: 10",
                "- Output tokens: 20",
                "- Total tokens: 30",
                "- Estimated cost USD: 0",
                "",
            ]
        ),
        encoding="utf-8",
    )
    return output_path


def _read_json(path: Path) -> dict[str, Any]:
    return cast(dict[str, Any], json.loads(path.read_text(encoding="utf-8")))


def _write_rsr_source_extract_artifact(tmp_path: Path) -> Path:
    from daedalus.domains.readysetrentables_reviews.source_extraction_artifacts import (
        write_rsr_source_extract_json,
    )
    from daedalus.domains.readysetrentables_reviews.source_extraction_fixtures import (
        build_sample_rsr_source_extraction_result,
    )

    output_path = tmp_path / "rsr_source_extract.json"
    write_rsr_source_extract_json(
        result=build_sample_rsr_source_extraction_result(),
        output_path=output_path,
    )
    return output_path


def _write_review_insight_input_artifact(tmp_path: Path) -> Path:
    output_path = tmp_path / "review_insight_extraction_input.json"
    input_data = ReviewInsightExtractionInput(
        run_id=uuid4(),
        review_count=2,
        market_name="Synthetic Market",
        neighborhood_name="Synthetic Neighborhood",
        property_type="Synthetic Apartment",
        average_rating=4.7,
        rating_categories={"synthetic_location": 4.9},
        representative_reviews=["Synthetic review: hidden representative review."],
    )
    payload = json.loads(input_data.model_dump_json())
    output_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return output_path


def _install_review_insights_ollama_cli_fakes(
    monkeypatch: pytest.MonkeyPatch,
    *,
    agent_error: Exception | None = None,
) -> "FakeReviewInsightsOllamaCliState":
    state = FakeReviewInsightsOllamaCliState(agent_error=agent_error)

    class FakeOllamaClient:
        def __init__(self, *, settings: OllamaModelClientSettings) -> None:
            self.settings = settings
            state.clients.append(self)

    class FakeReviewInsightAgent:
        def __init__(
            self,
            *,
            model_client: object,
            model_name: str,
            prompt_name: str = "readysetrentables_review_insight_extraction",
            prompt_version: str = "v0",
        ) -> None:
            self.model_client = model_client
            self.model_name = model_name
            self.prompt_name = prompt_name
            self.prompt_version = prompt_version
            state.agents.append(self)

        def run(
            self,
            *,
            input_data: ReviewInsightExtractionInput,
        ) -> ReviewInsightExtractionResult:
            state.inputs.append(input_data)
            if state.agent_error is not None:
                raise state.agent_error
            return _review_insight_extraction_result(
                run_id=input_data.run_id,
                model_name=self.model_name,
                prompt_name=self.prompt_name,
                prompt_version=self.prompt_version,
            )

    monkeypatch.setattr("daedalus.cli.OllamaModelClient", FakeOllamaClient)
    monkeypatch.setattr("daedalus.cli.ReviewInsightExtractionAgent", FakeReviewInsightAgent)
    return state


def _review_insight_extraction_result(
    *,
    run_id: UUID,
    model_name: str = "llama3.1",
    prompt_name: str = "readysetrentables_review_insight_extraction",
    prompt_version: str = "v0",
) -> ReviewInsightExtractionResult:
    return ReviewInsightExtractionResult(
        run_id=run_id,
        provider=ModelProvider.OLLAMA,
        model_name=model_name,
        prompt_name=prompt_name,
        prompt_version=prompt_version,
        themes=[
            ReviewInsightTheme(
                name="arrival clarity",
                sentiment="positive",
                evidence_count=2,
                summary="Synthetic guests value clear arrival details.",
            )
        ],
        strengths=["Clear synthetic arrival details"],
        risks=["Occasional synthetic street noise"],
        guest_expectations=["Send arrival details before check-in"],
        raw_insight_summary="Raw model output should not be printed.",
        input_tokens=11,
        output_tokens=7,
        total_tokens=18,
        estimated_cost_usd=Decimal("0"),
    )


def _install_rsr_source_cli_fakes(
    monkeypatch: pytest.MonkeyPatch,
    *,
    result: RsrSourceExtractionResult | None = None,
    repository_error: Exception | None = None,
) -> "FakeRsrSourceCliState":
    settings = _rsr_source_postgres_settings()
    state = FakeRsrSourceCliState(
        settings=settings,
        connection=FakeRsrSourceConnection(),
        result=result or _rsr_source_extraction_result(),
        repository_error=repository_error,
    )

    def fake_load_settings() -> RsrSourcePostgresSettings:
        state.loaded_settings_count += 1
        return settings

    def fake_connect(received_settings: RsrSourcePostgresSettings) -> FakeRsrSourceConnection:
        state.connected_settings.append(received_settings)
        return state.connection

    class FakeRepository:
        def __init__(self, connection: object) -> None:
            state.repository_connections.append(connection)

        def extract_source_data(
            self,
            *,
            request: RsrSourceExtractionRequest,
        ) -> RsrSourceExtractionResult:
            state.requests.append(request)
            if state.repository_error is not None:
                raise state.repository_error
            return state.result.model_copy(update={"request": request})

    monkeypatch.setattr("daedalus.cli.load_rsr_source_postgres_settings", fake_load_settings)
    monkeypatch.setattr("daedalus.cli.connect_rsr_source_postgres", fake_connect)
    monkeypatch.setattr("daedalus.cli.RsrSourceReadOnlyRepository", FakeRepository)
    return state


def _rsr_source_postgres_settings() -> RsrSourcePostgresSettings:
    return RsrSourcePostgresSettings(
        host="source-host",
        port=5432,
        database="source-db",
        user="source-user",
        password="top-secret-password",
    )


def _rsr_source_extraction_result(
    *,
    neighborhood_present: bool = True,
) -> RsrSourceExtractionResult:
    return RsrSourceExtractionResult(
        request=RsrSourceExtractionRequest(market_name="Synthetic Market"),
        extracted_at_utc=datetime(2026, 5, 18, 10, 0, tzinfo=UTC),
        reviews=[
            RsrSourceReviewRecord(
                review_id="review-1",
                listing_id="listing-1",
                rating=5.0,
                review_text="Raw private review text that must stay out of stdout.",
            ),
            RsrSourceReviewRecord(
                review_id="review-2",
                listing_id="listing-1",
                rating=4.0,
                review_text="Second raw private review text that must stay out of stdout.",
            ),
        ],
        listings=[
            RsrSourceListingContext(
                listing_id="listing-1",
                listing_name="Private listing name",
                property_type="Entire home",
            )
        ],
        neighborhood=(
            RsrSourceNeighborhoodContext(
                market_name="Synthetic Market",
                neighborhood_name="Synthetic Neighborhood",
            )
            if neighborhood_present
            else None
        ),
        metadata={"extraction_mode": "read_only"},
    )


def _workflow_run_details(
    run_id: UUID,
    artifact_records: list[ArtifactRecord] | None = None,
    step_records: list[WorkflowStepRecord] | None = None,
    model_invocation_records: list[ModelInvocationRecord] | None = None,
) -> WorkflowRunDetails:
    run_record = WorkflowRunRecord(
        run_id=run_id,
        workflow_name="readysetrentables_review_normalization",
        domain="readysetrentables_reviews",
        status=WorkflowStatus.COMPLETED,
        started_at_utc=datetime(2026, 5, 7, 10, 0, tzinfo=UTC),
        completed_at_utc=datetime(2026, 5, 7, 10, 1, tzinfo=UTC),
        source_input_path=Path("sample.csv"),
        output_artifact_path=Path("normalized_reviews.json"),
        metadata_artifact_path=Path("normalized_reviews.metadata.json"),
        summary_artifact_path=Path("normalized_reviews.summary.md"),
        run_record_artifact_path=Path("normalized_reviews.run.json"),
        duration_ms=60_000,
        review_count=8,
        approval_required=False,
        approved=False,
    )
    return WorkflowRunDetails(
        run_record=run_record,
        artifact_records=artifact_records
        if artifact_records is not None
        else [
            ArtifactRecord.create(
                run_id=run_record.run_id,
                artifact_type=ArtifactType.NORMALIZED_REVIEWS,
                artifact_path=Path("normalized_reviews.json"),
            ),
            ArtifactRecord.create(
                run_id=run_record.run_id,
                artifact_type=ArtifactType.WORKFLOW_SUMMARY,
                artifact_path=Path("normalized_reviews.summary.md"),
            ),
        ],
        step_records=step_records
        if step_records is not None
        else [
            _workflow_step_record(
                run_id=run_record.run_id,
                step_name="load_reviews",
                status=WorkflowStatus.COMPLETED,
                duration_ms=50,
            ),
            _workflow_step_record(
                run_id=run_record.run_id,
                step_name="write_artifact",
                status=WorkflowStatus.FAILED,
                duration_ms=75,
                error_message="write failed",
            ),
        ],
        model_invocation_records=model_invocation_records
        if model_invocation_records is not None
        else [_model_invocation_record(run_id=run_record.run_id)],
    )


class FakeModelInvocationConnection:
    def __init__(self) -> None:
        self.executed_sql: list[str] = []
        self.executed_params: list[tuple[object, ...]] = []
        self.committed = False
        self.rolled_back = False
        self.closed = False

    def execute(self, sql: str, params: tuple[object, ...]) -> None:
        self.executed_sql.append(sql)
        self.executed_params.append(params)

    def commit(self) -> None:
        self.committed = True

    def rollback(self) -> None:
        self.rolled_back = True

    def close(self) -> None:
        self.closed = True


class FakeRsrSourceConnection:
    def __init__(self) -> None:
        self.closed = False

    def close(self) -> None:
        self.closed = True


class FakeRsrSourceCliState:
    def __init__(
        self,
        *,
        settings: RsrSourcePostgresSettings,
        connection: FakeRsrSourceConnection,
        result: RsrSourceExtractionResult,
        repository_error: Exception | None,
    ) -> None:
        self.settings = settings
        self.connection = connection
        self.result = result
        self.repository_error = repository_error
        self.loaded_settings_count = 0
        self.connected_settings: list[RsrSourcePostgresSettings] = []
        self.repository_connections: list[object] = []
        self.requests: list[RsrSourceExtractionRequest] = []


class FailingArtifactConnection(FakeModelInvocationConnection):
    def execute(self, sql: str, params: tuple[object, ...]) -> None:
        super().execute(sql, params)
        if "insert into workflow_artifacts" in sql.lower():
            msg = "synthetic artifact insert failure"
            raise RuntimeError(msg)


class FakeReviewInsightsOllamaCliState:
    def __init__(self, *, agent_error: Exception | None) -> None:
        self.agent_error = agent_error
        self.clients: list[Any] = []
        self.agents: list[Any] = []
        self.inputs: list[ReviewInsightExtractionInput] = []


class SuccessfulOllamaClient:
    created_clients: list["SuccessfulOllamaClient"] = []

    def __init__(self, *, settings: OllamaModelClientSettings) -> None:
        self.settings = settings
        self.requests: list[object] = []
        self.created_clients.append(self)

    def complete(self, request: object) -> ModelResponse:
        self.requests.append(request)
        return ModelResponse(
            invocation_id=uuid4(),
            status=ModelResponseStatus.COMPLETED,
            provider=ModelProvider.OLLAMA,
            model_name="llama3.1",
            output_text="Raw local model output should not be printed.",
            input_tokens=4,
            output_tokens=3,
            total_tokens=7,
            estimated_cost_usd=Decimal("0"),
        )


class FailingOllamaClient:
    def __init__(self, *, settings: OllamaModelClientSettings) -> None:
        self.settings = settings

    def complete(self, request: object) -> ModelResponse:
        msg = "local Ollama smoke check failed safely"
        raise OllamaModelClientError(msg)


def _workflow_step_record(
    *,
    run_id: UUID,
    step_name: str,
    status: WorkflowStatus,
    duration_ms: int,
    error_message: str | None = None,
) -> WorkflowStepRecord:
    return WorkflowStepRecord(
        step_id=uuid4(),
        run_id=run_id,
        step_name=step_name,
        status=status,
        started_at_utc=datetime(2026, 5, 7, 10, 0, tzinfo=UTC),
        completed_at_utc=datetime(2026, 5, 7, 10, 1, tzinfo=UTC),
        duration_ms=duration_ms,
        error_message=error_message,
    )


def _model_invocation_record(run_id: UUID) -> ModelInvocationRecord:
    return ModelInvocationRecord(
        invocation_id=uuid4(),
        run_id=run_id,
        step_id=uuid4(),
        agent_name="review_summarizer",
        provider=ModelProvider.FAKE,
        model_name="fake-local-model",
        prompt_name="summarize_reviews",
        prompt_version="v1",
        input_tokens=10,
        output_tokens=5,
        total_tokens=15,
        estimated_cost_usd=Decimal("0.001"),
        status=ModelInvocationStatus.SUCCEEDED,
        started_at_utc=datetime(2026, 5, 7, 10, 0, tzinfo=UTC),
        completed_at_utc=datetime(2026, 5, 7, 10, 0, 1, tzinfo=UTC),
        duration_ms=1_000,
        input_artifact_path=Path("artifacts/input.json"),
        output_artifact_path=Path("artifacts/output.json"),
        error_message=None,
    )
