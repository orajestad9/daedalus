from datetime import UTC, datetime
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
from daedalus.orchestrator.artifact_record import ArtifactRecord
from daedalus.orchestrator.artifact_type import ArtifactType
from daedalus.orchestrator.run_record import WorkflowRunRecord
from daedalus.orchestrator.status import WorkflowStatus


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


def _workflow_run_details(run_id: UUID) -> WorkflowRunDetails:
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
    )
