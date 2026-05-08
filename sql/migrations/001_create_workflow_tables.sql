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

CREATE TABLE IF NOT EXISTS workflow_steps (
    step_id UUID PRIMARY KEY,
    run_id UUID NOT NULL REFERENCES workflow_runs(run_id) ON DELETE CASCADE,
    step_name TEXT NOT NULL,
    status TEXT NOT NULL,
    started_at_utc TIMESTAMPTZ NOT NULL,
    completed_at_utc TIMESTAMPTZ NULL,
    duration_ms INTEGER NULL,
    error_message TEXT NULL,
    created_at_utc TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Model invocation records intentionally store metadata and artifact paths only.
-- Raw prompt text and raw response text do not belong in this table.
CREATE TABLE IF NOT EXISTS model_invocations (
    invocation_id UUID PRIMARY KEY,
    run_id UUID NOT NULL REFERENCES workflow_runs(run_id) ON DELETE CASCADE,
    step_id UUID NULL REFERENCES workflow_steps(step_id) ON DELETE SET NULL,
    agent_name TEXT NULL,
    provider TEXT NOT NULL,
    model_name TEXT NOT NULL,
    prompt_name TEXT NOT NULL,
    prompt_version TEXT NOT NULL,
    input_tokens INTEGER NULL,
    output_tokens INTEGER NULL,
    total_tokens INTEGER NULL,
    estimated_cost_usd NUMERIC NULL,
    status TEXT NOT NULL,
    started_at_utc TIMESTAMPTZ NOT NULL,
    completed_at_utc TIMESTAMPTZ NOT NULL,
    duration_ms INTEGER NOT NULL,
    input_artifact_path TEXT NULL,
    output_artifact_path TEXT NULL,
    error_message TEXT NULL,
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

CREATE INDEX IF NOT EXISTS idx_workflow_steps_run_id
    ON workflow_steps (run_id);

CREATE INDEX IF NOT EXISTS idx_workflow_steps_status
    ON workflow_steps (status);

CREATE INDEX IF NOT EXISTS idx_workflow_steps_step_name
    ON workflow_steps (step_name);

CREATE INDEX IF NOT EXISTS idx_workflow_steps_created_at_utc_desc
    ON workflow_steps (created_at_utc DESC);

CREATE INDEX IF NOT EXISTS idx_model_invocations_run_id
    ON model_invocations (run_id);

CREATE INDEX IF NOT EXISTS idx_model_invocations_step_id
    ON model_invocations (step_id);

CREATE INDEX IF NOT EXISTS idx_model_invocations_provider
    ON model_invocations (provider);

CREATE INDEX IF NOT EXISTS idx_model_invocations_model_name
    ON model_invocations (model_name);

CREATE INDEX IF NOT EXISTS idx_model_invocations_status
    ON model_invocations (status);

CREATE INDEX IF NOT EXISTS idx_model_invocations_created_at_utc_desc
    ON model_invocations (created_at_utc DESC);
