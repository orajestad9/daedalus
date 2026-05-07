-- Initial workflow persistence schema for Daedalus.
-- Migrations are committed source artifacts; never place secrets here.

CREATE TABLE IF NOT EXISTS workflow_runs (
    run_id UUID PRIMARY KEY,
    workflow_name TEXT NOT NULL,
    domain TEXT NOT NULL,
    status TEXT NOT NULL,
    started_at_utc TIMESTAMPTZ NOT NULL,
    completed_at_utc TIMESTAMPTZ NOT NULL,
    source_input_path TEXT NOT NULL,
    output_artifact_path TEXT NOT NULL,
    metadata_artifact_path TEXT NOT NULL,
    summary_artifact_path TEXT NOT NULL,
    run_record_artifact_path TEXT NOT NULL,
    duration_ms INTEGER NOT NULL,
    review_count INTEGER NOT NULL,
    approval_required BOOLEAN NOT NULL,
    approved BOOLEAN NOT NULL,
    created_at_utc TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS workflow_artifacts (
    artifact_id UUID PRIMARY KEY,
    run_id UUID NOT NULL REFERENCES workflow_runs(run_id) ON DELETE CASCADE,
    artifact_type TEXT NOT NULL,
    artifact_path TEXT NOT NULL,
    created_at_utc TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_workflow_runs_created_at_utc_desc
    ON workflow_runs (created_at_utc DESC);

CREATE INDEX IF NOT EXISTS idx_workflow_runs_workflow_name
    ON workflow_runs (workflow_name);

CREATE INDEX IF NOT EXISTS idx_workflow_runs_domain
    ON workflow_runs (domain);

CREATE INDEX IF NOT EXISTS idx_workflow_runs_status
    ON workflow_runs (status);

CREATE INDEX IF NOT EXISTS idx_workflow_artifacts_run_id
    ON workflow_artifacts (run_id);

CREATE INDEX IF NOT EXISTS idx_workflow_artifacts_artifact_type
    ON workflow_artifacts (artifact_type);
