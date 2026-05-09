# daedalus
Daedalus is a local-first Python multi-agent orchestration platform for building
observable, human-approved AI pipelines. The first workflow automates
ReadySetRentables review processing from Airbnb CSV data into deterministic JSON
artifacts, with optional local Postgres persistence for workflow run, artifact,
and step records.

## Development Commands

Install local development dependencies:

```sh
make install
```

Run the full local check suite:

```sh
make check
```

`make check` is unit-only and does not require Docker or Postgres.

GitHub Actions runs the same `make check` quality gate on pushes and pull
requests targeting `main`.

Normalize the committed sample Airbnb review CSV into a JSON artifact:

```sh
make normalize-sample
```

The sample run writes four ignored local artifacts under
`artifacts/readysetrentables/`:

- `normalized_reviews.json`
- `normalized_reviews.metadata.json`
- `normalized_reviews.summary.md`
- `normalized_reviews.run.json`

## Workflow Manifests

Workflows can be described by YAML manifests under `workflows/`. The sample
ReadySetRentables manifest defines the workflow name, domain, input CSV path,
output JSON path, whether human approval is required, and the execution engine.
The default execution engine is `deterministic`; LangGraph can be selected
explicitly with `execution_engine: langgraph` or temporarily overridden with
`daedalus run-workflow --execution-engine langgraph`.

Before adding agents or model clients, review
[`docs/token-cost-governance.md`](docs/token-cost-governance.md). Daedalus
treats token usage, cloud-model opt-in, model-call tracking, and prompt privacy
as first-class design constraints.
For the Phase 4 model-client design baseline, see
[`docs/model-client-architecture.md`](docs/model-client-architecture.md).
For the current fake/local review theme summary agent path, see
[`docs/review-theme-summary-agent.md`](docs/review-theme-summary-agent.md).
For the Phase 5A fake-agent LangGraph integration plan, see
[`docs/phase-5a-fake-agent-langgraph.md`](docs/phase-5a-fake-agent-langgraph.md).
For the Phase 5B local Ollama provider design, see
[`docs/phase-5b-ollama-provider.md`](docs/phase-5b-ollama-provider.md).

For the current run, step, artifact, logging, and persisted inspection model,
including practical `show-run` examples, see
[`docs/observability.md`](docs/observability.md).

For the Phase 3 LangGraph orchestration plan, see
[`docs/langgraph-orchestration.md`](docs/langgraph-orchestration.md).
For the current Phase 3 completion summary, see
[`docs/phase-3-completion-checklist.md`](docs/phase-3-completion-checklist.md).
For a direct local graph run:

```sh
.venv/bin/daedalus run-review-graph --input sample_data/readysetrentables_reviews/airbnb_reviews_sample.csv --output artifacts/readysetrentables/normalized_reviews.json
```

The LangGraph path now also writes `review_theme_summary.md` through the
fake/local review theme summary agent. It still uses `FakeModelClient` only and
does not make real LLM calls. When run through
`run-workflow --execution-engine langgraph --persist`, it can persist the
`review_theme_summary` artifact record and fake model invocation metadata for
`show-run` inspection.

For the fake/local Phase 4 review theme summary path:

```sh
.venv/bin/daedalus summarize-review-themes-fake --input artifacts/readysetrentables/normalized_reviews.json --output artifacts/readysetrentables/review_theme_summary.md
```

This uses `FakeModelClient` only. It does not call real LLMs, use provider SDKs,
or print raw prompts, raw model output, or raw review datasets.
After a workflow run has been persisted, the generated markdown can be recorded
explicitly with `record-review-theme-summary-artifact` so `show-run` can display
the `review_theme_summary` artifact.

To verify that local fake summary path end to end without Docker or `.env`:

```sh
make fake-summary-check
```

To verify the LangGraph-generated fake summary artifact without Docker or
`.env`:

```sh
make graph-fake-summary-check
```

## Local Postgres

Phase 1 includes optional local Postgres persistence for workflow run records
and generated artifact records. Phase 2 extends persisted inspection with
workflow step records. See
[`docs/phase-1-persistence.md`](docs/phase-1-persistence.md) for the full
workflow.

No real secrets are committed. To run Postgres locally:

```sh
cp .env.example .env
```

Edit `.env` and replace every `change_me_*` placeholder with local-only values.
Keep the `POSTGRES_*` values aligned with the `DAEDALUS_POSTGRES_*` values used
by Docker Compose.
Never commit `.env`, real passwords, connection strings, hostnames, tokens, or
machine-specific values.

Start Postgres:

```sh
make db-up
```

Apply committed SQL migrations:

```sh
make migrate-db
```

Run the workflow and persist the completed run:

```sh
daedalus run-workflow --manifest workflows/readysetrentables_review_normalization.yaml --persist
```

List persisted runs:

```sh
daedalus list-runs
```

Inspect one persisted run:

```sh
daedalus show-run --run-id <workflow-run-uuid>
```

Inspect logs if needed:

```sh
make db-logs
```

Stop the service:

```sh
make db-down
```

To delete the local database volume, run the destructive reset target:

```sh
make db-reset
```

`make migrate-db` loads local settings from `.env`. If `.env` is missing, copy
`.env.example` to `.env` and edit the values locally first. `.env` must never be
committed.

## Local Integration Check

Run the local Postgres integration check:

```sh
make db-check
```

`make db-check` requires Docker and a local `.env`. It starts Postgres, applies
committed SQL migrations, runs the ReadySetRentables workflow with
Postgres-backed persistence through both the deterministic and LangGraph
execution paths, captures the LangGraph run ID, lists recent workflow runs,
inspects the persisted LangGraph run with `show-run`, verifies workflow steps
are visible, cleans generated local artifacts, and stops Postgres. This target
is intentionally separate from `make check` so normal unit checks stay fast and
database-free.
