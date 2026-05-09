# Observability

Daedalus observability is intentionally local-first today. Phase 2 records enough
run, step, artifact, and log context to inspect a completed workflow without
adding OpenTelemetry, agents, dashboards, or production infrastructure yet.
Phase 4 added model invocation metadata through fake/local model clients, and
Phase 5A now persists fake LangGraph summary invocation metadata when explicitly
requested. No real provider calls happen yet.

The current scope answers three practical questions:

- What workflow ran?
- Which coarse steps completed?
- Which artifacts were produced, and how can a human inspect them?

## Current Flow

```text
workflow execution
  -> run record
  -> step records
  -> artifact records
  -> show-run
  -> logs with run_id
```

The ReadySetRentables review normalization workflow writes local artifacts first.
When `run-workflow --persist` is used, Daedalus also saves the run, artifact, and
step records to local Postgres for inspection.

## Run-Level Observability

Each workflow execution has a `run_id` and a `WorkflowRunRecord`. The run record
captures workflow identity, domain, status, timestamps, `duration_ms`, source
input path, generated artifact paths, review count, and approval status.

The same run record is written as a local JSON artifact:

- `normalized_reviews.run.json`

When persistence is requested, the record is also stored in the `workflow_runs`
table so `list-runs` and `show-run` can inspect it later.

## Step-Level Observability

The workflow now collects coarse `WorkflowStepRecord` objects for the current
deterministic phases:

- `load_reviews`
- `write_normalized_artifact`
- `write_metadata_artifact`
- `write_summary_artifact`
- `write_run_record_artifact`

Each step has its own ID, the parent `run_id`, step name, status, timestamps,
duration, and optional error message. Successful workflow runs mark these steps
as completed with non-negative durations.

If a step action raises an exception, the workflow step helper records a failed
step with the error message and re-raises the original exception. Full failed-run
persistence is still deferred; the current behavior establishes failure-path step
semantics without changing the workflow's failed-run storage model.

When persistence is enabled, step records are stored in `workflow_steps`.
`show-run` displays a Steps section so operators can inspect the persisted
coarse workflow timeline.

## Artifact Observability

Artifacts remain first-class outputs. The current workflow writes:

- `normalized_reviews.json`
- `normalized_reviews.metadata.json`
- `normalized_reviews.summary.md`
- `normalized_reviews.run.json`

The metadata artifact connects the normalized review JSON to the workflow run,
input path, output path, artifact type, creation timestamp, and review count.
When persistence is enabled, artifact records are stored in `workflow_artifacts`
as an index of generated files.

Phase 4 also recognizes `review_theme_summary` as an artifact type for the
fake/local review theme summary markdown output. The standalone
`summarize-review-themes-fake` command writes `review_theme_summary.md` as a
file artifact. The explicit `record-review-theme-summary-artifact` command can
attach that existing markdown file to a persisted workflow run as an
`ArtifactRecord` with artifact type `review_theme_summary`.

Phase 5A also persists the graph-generated summary artifact automatically when
the LangGraph path is run with:

```sh
.venv/bin/daedalus run-workflow \
  --manifest workflows/readysetrentables_review_normalization.yaml \
  --execution-engine langgraph \
  --persist
```

After persistence, `show-run` can display the normal workflow artifacts, the
`review_theme_summary` artifact, and related fake model invocation metadata
together.

## Human Inspection

There are two inspection paths:

- Markdown summary inspection through `normalized_reviews.summary.md`
- Postgres-backed inspection through `daedalus show-run --run-id <run-id>`

The markdown summary is optimized for fast human review of one workflow output,
including the collected workflow steps. The `show-run` command is optimized for
persisted run inspection: it loads the run record, artifact records, step
records, and any model invocation records from Postgres, then formats a readable
summary through the run inspection formatter.

## Run Inspection Examples

For a one-command local integration check, use:

```sh
make db-check
```

This starts local Postgres, applies migrations, persists a workflow run, lists
recent runs, inspects the captured run with `show-run`, verifies workflow steps
are visible, cleans generated artifacts, and stops Postgres.

For a manual inspection flow, start Postgres and apply migrations:

```sh
make db-up
make migrate-db
```

Run the ReadySetRentables workflow with persistence enabled:

```sh
.venv/bin/daedalus run-workflow --manifest workflows/readysetrentables_review_normalization.yaml --persist
```

The command prints a generated `run_id`. Use `list-runs` to see recent persisted
runs:

```sh
.venv/bin/daedalus list-runs
```

Inspect one run with a placeholder run ID:

```sh
.venv/bin/daedalus show-run --run-id <run-id>
```

Then stop local Postgres:

```sh
make db-down
```

`show-run` prints a readable summary shaped like this:

```text
Workflow run <run-id>
workflow_name: readysetrentables_review_normalization
domain: readysetrentables_reviews
status: completed
duration_ms: <elapsed-ms>
review_count: 8
artifacts:
- normalized_reviews: artifacts/readysetrentables/normalized_reviews.json
- review_metadata: artifacts/readysetrentables/normalized_reviews.metadata.json
- workflow_summary: artifacts/readysetrentables/normalized_reviews.summary.md
- workflow_run_record: artifacts/readysetrentables/normalized_reviews.run.json
steps:
- load_reviews: status=completed duration_ms=<elapsed-ms>
- write_normalized_artifact: status=completed duration_ms=<elapsed-ms>
- write_metadata_artifact: status=completed duration_ms=<elapsed-ms>
- write_summary_artifact: status=completed duration_ms=<elapsed-ms>
- write_run_record_artifact: status=completed duration_ms=<elapsed-ms>
```

The placeholders above are deliberate. Do not paste real `.env` values,
passwords, private hosts, tokens, connection strings, or machine-specific values
into documentation.

## Structured Logging

Daedalus uses the standard Python logging module. Important lifecycle logs now
include contextual fields in the message, especially:

- `run_id`
- `workflow_name`
- `domain`
- `step_name` for step lifecycle logs

Logs are intentionally lightweight and safe. They should not include passwords,
password-bearing DSNs, `.env` contents, raw private datasets, API keys, provider
tokens, or sensitive prompt/response bodies.

## Model Invocation Observability

Phase 4 has added the first model invocation observability foundation. The
`model_invocations` table exists, `ModelInvocationRepository` can save and list
records, `ModelInvocationRecorder` creates safe invocation records, and
`show-run` can display persisted model invocation metadata when records exist.

The current fake/local checks can create fake invocation records without real
provider calls:

- `make fake-model-db-check` persists a workflow run, records one fake model
  invocation, and verifies that `show-run` displays it.
- `run-workflow --execution-engine langgraph --persist` runs the integrated fake
  review theme summary graph path, persists the `review_theme_summary` artifact,
  and persists fake model invocation metadata for the summary agent call.
- `summarize-review-themes-fake` remains a standalone file/artifact path. It
  exercises the review theme summary agent with `FakeModelClient` and writes a
  markdown artifact, but does not persist model invocation rows by itself.
- `record-review-theme-summary-artifact` records an existing
  `review_theme_summary.md` file as an artifact row for an existing persisted
  workflow run without printing artifact contents.

Model calls should attach to the workflow `run_id`, and to a `step_id` whenever
the call happens inside an observable workflow step. Agents, LangGraph nodes,
and direct workflow code should not call providers directly; they should go
through the shared `ModelClient` abstraction so budgets, artifacts, and
invocation metadata stay consistent.

Each model invocation record includes:

- `invocation_id`
- `run_id`
- `step_id` if available
- `agent_name`
- `provider`
- `model_name`
- `prompt_name`
- `prompt_version`
- `input_tokens`
- `output_tokens`
- `total_tokens`
- `estimated_cost_usd`
- `status`
- `started_at_utc`
- `completed_at_utc`
- `duration_ms`
- `input_artifact_path`
- `output_artifact_path`

This belongs with the token and cost governance rules in
[`docs/token-cost-governance.md`](token-cost-governance.md). Manifest-level
budgets, cloud-model opt-in, prompt versioning, and cache behavior should be
checked before a provider call is made, not reconstructed afterward from logs.

Model outputs should be written as artifacts when they are useful to inspect,
validate, approve, or replay. Raw prompts and responses should not be blindly
persisted in Postgres, and `model_invocations` intentionally stores metadata and
artifact paths rather than raw prompt text or raw response text. Store
references to sanitized input and output artifacts instead, and only persist
prompt/response bodies when an explicit data classification decision says it is
safe.

For the integrated LangGraph fake summary path, the persisted model invocation
record contains metadata such as `provider=fake`, `model_name`, `prompt_name`,
`prompt_version`, token counts, estimated cost, status, and duration. It does
not contain raw prompt text, raw model output text, or the review dataset.

LangGraph node tracing can later add richer graph-level spans, and future agents
can use the same model invocation records to make cost, token usage, and failure
inspection visible.

## Checks

`make check` is the fast unit-quality gate. It runs pytest, ruff, ruff format
check, and mypy without Docker or Postgres.

`make db-check` is the local integration path. It requires Docker and a local
ignored `.env`, starts Postgres, applies migrations, runs the workflow with
`--persist`, captures the run ID, lists recent runs, calls `show-run`, verifies
that workflow steps are visible, cleans generated artifacts, and stops Postgres.

`make fake-model-db-check` is a local-only Phase 4 check. It creates a persisted
workflow run, records one fake model invocation through `RecordingModelClient`,
then calls `show-run` to verify the Model Invocations section is visible. This
uses `FakeModelClient` only; it does not use provider SDKs, network calls, cloud
models, raw prompt logging, or raw response logging.

`make fake-summary-db-check` is a local-only Phase 5A check for the integrated
LangGraph fake review theme summary path. It runs
`run-workflow --execution-engine langgraph --persist`, then verifies that
`show-run` displays the `review_theme_summary` artifact and a fake model
invocation with `provider=fake`. This target requires Docker and a local ignored
`.env`.

Keeping these commands separate lets normal development and CI stay fast while
still providing an end-to-end local persistence inspection check.

## Future Preparation

The current architecture leaves clear attachment points for later observability
work:

- OpenTelemetry can attach spans to `run_id`, workflow identity, and step names.
- LangGraph node tracing can map graph nodes to `WorkflowStepRecord` rows.
- Agents can report actions as steps or future agent-specific records.
- Model invocation tracking can attach fake and future provider calls to
  `run_id` and generated artifacts.
- Token and cost tracking can follow the rules in
  [`docs/token-cost-governance.md`](token-cost-governance.md).

## Intentionally Deferred

- OpenTelemetry
- distributed tracing
- LangGraph node tracing
- production agent tracing
- real provider invocation tracking
- token/cost budget dashboards
- dashboards/UI
- production observability deployment
