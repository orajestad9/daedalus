from pathlib import Path

from daedalus.memory.migrations import discover_migration_files


MIGRATION_PATH = Path("sql/migrations/001_create_workflow_tables.sql")


def test_initial_workflow_migration_exists() -> None:
    assert MIGRATION_PATH.is_file()


def test_initial_workflow_migration_creates_expected_tables() -> None:
    migration_sql = MIGRATION_PATH.read_text(encoding="utf-8").lower()

    assert "create table if not exists workflow_runs" in migration_sql
    assert "create table if not exists workflow_artifacts" in migration_sql
    assert "create table if not exists workflow_steps" in migration_sql


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
        "duration_ms integer not null",
        "review_count integer not null",
        "approval_required boolean not null",
        "approved boolean not null",
        "artifact_id uuid primary key",
        "artifact_type text not null",
        "artifact_path text not null",
        "step_id uuid primary key",
        "step_name text not null",
        "duration_ms integer null",
        "error_message text null",
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
        "on workflow_steps (run_id)",
        "on workflow_steps (status)",
        "on workflow_steps (step_name)",
        "on workflow_steps (created_at_utc desc)",
    ]

    for expected_index in expected_indexes:
        assert expected_index in migration_sql


def test_discover_migration_files_returns_only_sql_files(tmp_path: Path) -> None:
    sql_migration = tmp_path / "001_create_tables.sql"
    sql_migration.write_text("select 1;", encoding="utf-8")
    readme = tmp_path / "README.md"
    readme.write_text("Not a migration.", encoding="utf-8")

    assert discover_migration_files(tmp_path) == [sql_migration]


def test_discover_migration_files_sorts_by_filename(tmp_path: Path) -> None:
    second_migration = tmp_path / "002_second.sql"
    first_migration = tmp_path / "001_first.sql"
    second_migration.write_text("select 2;", encoding="utf-8")
    first_migration.write_text("select 1;", encoding="utf-8")

    assert discover_migration_files(tmp_path) == [first_migration, second_migration]
