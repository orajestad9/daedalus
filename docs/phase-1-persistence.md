# Phase 1 Persistence

Phase 1 added optional local Postgres persistence for Daedalus workflow
execution records. The workflow still writes local artifacts first. Postgres
stores the run and artifact index so operators and future agents can inspect
completed workflow executions without opening every JSON or markdown file
manually. Phase 2 extends this persisted inspection path with workflow step
records; see [`docs/observability.md`](observability.md) for the current
run/step inspection model.

This phase remains local-first. It does not add production deployment,
Kubernetes, agents, model clients, LangGraph, or OpenTelemetry.

## What Persistence Stores

Phase 1 introduced two kinds of records:

- workflow run records, one row per completed workflow run
- workflow artifact records, one row per generated artifact associated with a
  run

Phase 2 adds workflow step records in `workflow_steps` for persisted run
inspection. This document remains the Phase 1 persistence baseline; the current
observability model is documented in [`docs/observability.md`](observability.md).

The first persisted workflow is the ReadySetRentables review normalization flow:

```sh
daedalus run-workflow --manifest workflows/readysetrentables_review_normalization.yaml --persist
```

Without `--persist`, workflow execution remains file-only and does not require
database settings or a Postgres connection.

## `workflow_runs`

The `workflow_runs` table records the workflow execution itself. It stores the
run ID, workflow name, domain, status, timestamps, source input path, artifact
paths, review count, and approval status.

This table is the local Postgres counterpart to the file-based
`normalized_reviews.run.json` artifact.

## `workflow_artifacts`

The `workflow_artifacts` table records generated artifact paths for a workflow
run. It stores an artifact ID, the run ID, artifact type, artifact path, and
creation timestamp.

Current artifact types include normalized review JSON, metadata JSON, summary
markdown, and workflow run record JSON.

## What Remains File-Based

The workflow still writes these local artifacts:

- `normalized_reviews.json`
- `normalized_reviews.metadata.json`
- `normalized_reviews.summary.md`
- `normalized_reviews.run.json`

Postgres records point to these files. Phase 1 does not move the full normalized
review payload, markdown summary body, or metadata JSON contents into database
tables.

## How `--persist` Works

`run-workflow --persist` runs the workflow normally, then explicitly loads local
Postgres settings from `.env`, opens a Postgres connection, and saves:

- one `WorkflowRunRecord`
- four `ArtifactRecord` rows for the generated artifacts

The persistence path commits after a successful save and rolls back on failure.
Secrets are not printed, logged, or embedded in connection strings.

## Inspecting Runs

List recent persisted runs:

```sh
daedalus list-runs
```

Limit and filter the list:

```sh
daedalus list-runs --limit 5 --domain readysetrentables_reviews --status completed
```

Inspect one run, its artifacts, and its workflow steps:

```sh
daedalus show-run --run-id <workflow-run-uuid>
```

These commands read from Postgres through repository classes. SQL remains in the
memory layer rather than the CLI.

## Local Commands

Create local settings from placeholders:

```sh
cp .env.example .env
```

Edit `.env` locally and replace placeholders. Never commit `.env`.
Keep the `POSTGRES_*` values used by the Python CLI aligned with the
`DAEDALUS_POSTGRES_*` values used by Docker Compose.

Start Postgres:

```sh
make db-up
```

Apply migrations:

```sh
make migrate-db
```

Run the persisted workflow:

```sh
daedalus run-workflow --manifest workflows/readysetrentables_review_normalization.yaml --persist
```

Stop Postgres:

```sh
make db-down
```

Run the local integration check:

```sh
make db-check
```

`make db-check` starts Postgres, applies migrations, runs the workflow with
`--persist`, captures the run ID, lists recent runs, inspects the persisted run
with `show-run`, verifies workflow steps are visible, cleans generated local
artifacts, and stops Postgres.

## Why `make check` Does Not Require Postgres

`make check` is the fast unit-quality gate. It runs pytest, ruff, ruff format
check, and mypy without Docker or Postgres.

Database-dependent verification lives behind `make db-check` so local
development, CI, and future coding-agent work do not require a running database
for every edit.

## Secrets Policy

Do not commit real secrets. Ever.

Do not commit or document real passwords, API keys, provider tokens,
password-bearing DSNs, private IPs, private hostnames, or machine-specific
connection details.

`.env.example` contains placeholders only. Real local values belong only in
ignored files such as `.env`.

CLI output, logs, tests, and docs must not expose password-bearing connection
strings or raw secret values.

## Token And Cost Governance

Model clients and agents are intentionally deferred, but token and cost
governance is already a design constraint. See
[`docs/token-cost-governance.md`](token-cost-governance.md) before adding model
invocation tables, prompt tracking, cloud-model calls, agents, or LangGraph
flows.

## Intentionally Deferred

- OpenTelemetry
- LangGraph
- agents
- model clients
- token/cost database tables
- Kubernetes
- UI/dashboard
- production deployment
- app Docker image builds
- live Postgres integration tests in `make check`
