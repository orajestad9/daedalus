from pathlib import Path


MIGRATION_PATH = Path("sql/migrations/001_create_workflow_tables.sql")


def test_initial_workflow_migration_exists() -> None:
    assert MIGRATION_PATH.is_file()


def test_initial_workflow_migration_creates_expected_tables() -> None:
    migration_sql = MIGRATION_PATH.read_text(encoding="utf-8").lower()

    assert "create table if not exists workflow_runs" in migration_sql
    assert "create table if not exists workflow_artifacts" in migration_sql


def test_initial_workflow_migration_contains_expected_columns() -> None:
    migration_sql = MIGRATION_PATH.read_text(encoding="utf-8").lower()

    expected_columns = [
        "run_id uuid primary key",
        "workflow_name text not null",
        "domain text not null",
        "status text not null",
        "started_at_utc timestamptz not null",
        "completed_at_utc timestamptz not null",
        "source_input_path text not null",
        "output_artifact_path text not null",
        "metadata_artifact_path text not null",
        "summary_artifact_path text not null",
        "run_record_artifact_path text not null",
        "review_count integer not null",
        "approval_required boolean not null",
        "approved boolean not null",
        "artifact_id uuid primary key",
        "artifact_type text not null",
        "artifact_path text not null",
    ]

    for expected_column in expected_columns:
        assert expected_column in migration_sql


def test_initial_workflow_migration_contains_expected_indexes() -> None:
    migration_sql = MIGRATION_PATH.read_text(encoding="utf-8").lower()

    expected_indexes = [
        "on workflow_runs (created_at_utc desc)",
        "on workflow_runs (workflow_name)",
        "on workflow_runs (domain)",
        "on workflow_runs (status)",
        "on workflow_artifacts (run_id)",
        "on workflow_artifacts (artifact_type)",
    ]

    for expected_index in expected_indexes:
        assert expected_index in migration_sql
