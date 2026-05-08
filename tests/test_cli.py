from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from uuid import UUID, uuid4

import pytest

from daedalus.cli import main
from daedalus.config import PostgresSettings
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
from daedalus.model_clients.types import ModelProvider
from daedalus.orchestrator.artifact_record import ArtifactRecord
from daedalus.orchestrator.artifact_type import ArtifactType
from daedalus.orchestrator.run_record import WorkflowRunRecord
from daedalus.orchestrator.status import WorkflowStatus
from daedalus.orchestrator.step_record import WorkflowStepRecord
from daedalus.shared.workflow_manifest import WorkflowExecutionEngine


SAMPLE_CSV_PATH = Path("sample_data/readysetrentables_reviews/airbnb_reviews_sample.csv")
SAMPLE_MANIFEST_PATH = Path("workflows/readysetrentables_review_normalization.yaml")


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

    output = capsys.readouterr().out
    assert "Ran review graph" in output
    assert "run_id=" in output
    assert "review_count=8" in output
    assert f"output={output_path}" in output
    assert f"metadata={tmp_path / 'normalized_reviews.metadata.json'}" in output
    assert f"summary={tmp_path / 'normalized_reviews.summary.md'}" in output
    assert f"run_record={tmp_path / 'normalized_reviews.run.json'}" in output
    assert "steps=5" in output


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


def _workflow_run_details(
    run_id: UUID,
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
        artifact_records=[
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
