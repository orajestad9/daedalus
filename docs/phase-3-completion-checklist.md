# Phase 3 Completion Checklist

Phase 3 establishes a LangGraph orchestration baseline for the
ReadySetRentables review normalization workflow. The graph path reproduces the
existing deterministic workflow with the same artifact outputs, run records,
workflow step records, approval status, and optional Postgres persistence.

The important boundary is intentional: LangGraph currently orchestrates
deterministic Python nodes only. Daedalus has not added agents, model clients,
LLM calls, OpenTelemetry, autonomous planning, or token/model invocation tables.

## Completed Checklist

- [x] Added LangGraph as a project dependency.
- [x] Documented the LangGraph orchestration architecture.
- [x] Added `ReadySetRentablesReviewGraphState`.
- [x] Added deterministic graph nodes for the existing workflow phases.
- [x] Compiled the graph into a runnable ReadySetRentables review workflow.
- [x] Added direct `run-review-graph` CLI execution.
- [x] Added parity tests comparing stable LangGraph output to the deterministic
      workflow.
- [x] Added manifest `execution_engine` support.
- [x] Kept `deterministic` as the default execution engine.
- [x] Added `run-workflow --execution-engine` CLI override support.
- [x] Preserved manifest approval gate behavior.
- [x] Preserved optional Postgres persistence through `--persist`.
- [x] Extended `make db-check` to exercise persisted deterministic and
      LangGraph execution paths.
- [x] Documented current LangGraph usage and intentionally deferred work.

## Current LangGraph Execution Paths

LangGraph is opt-in through three paths:

- direct graph execution with `run-review-graph`
- manifest execution with `execution_engine: langgraph`
- one-off manifest override with `run-workflow --execution-engine langgraph`

The deterministic workflow remains the default path for manifest-driven
execution.

## Current Graph Nodes

The compiled graph runs these deterministic nodes in order:

```text
load_reviews
  -> write_normalized_artifact
  -> write_metadata_artifact
  -> write_summary_artifact
  -> write_run_record_artifact
```

Each graph node maps to a `WorkflowStepRecord` with the same step name. This
keeps markdown summaries, persisted step records, `show-run`, and future graph
inspection aligned around one vocabulary.

## Deterministic Workflow Command

Run the default deterministic manifest path:

```sh
.venv/bin/daedalus run-workflow --manifest workflows/readysetrentables_review_normalization.yaml
```

## Direct LangGraph Command

Run the compiled LangGraph workflow without using a manifest:

```sh
.venv/bin/daedalus run-review-graph --input sample_data/readysetrentables_reviews/airbnb_reviews_sample.csv --output artifacts/readysetrentables/normalized_reviews.json
```

## LangGraph Manifest Commands

Run a manifest that declares LangGraph:

```sh
.venv/bin/daedalus run-workflow --manifest workflows/readysetrentables_review_normalization_langgraph.yaml
```

Run the committed deterministic manifest with a one-off LangGraph override:

```sh
.venv/bin/daedalus run-workflow --manifest workflows/readysetrentables_review_normalization.yaml --execution-engine langgraph
```

## Persist And Inspect LangGraph Runs

Persist a LangGraph run to local Postgres:

```sh
.venv/bin/daedalus run-workflow --manifest workflows/readysetrentables_review_normalization.yaml --execution-engine langgraph --persist
```

List persisted workflow runs:

```sh
.venv/bin/daedalus list-runs
```

Inspect one persisted run:

```sh
.venv/bin/daedalus show-run --run-id <run-id>
```

Run the local integration check:

```sh
make db-check
```

`make db-check` requires Docker and a local `.env`. It starts Postgres, applies
migrations, runs persisted deterministic and LangGraph workflows, lists recent
runs, inspects the persisted LangGraph run, verifies workflow steps are visible,
cleans generated artifacts, and stops Postgres.

## Testing Coverage Summary

The current test suite covers:

- LangGraph dependency import.
- graph state defaults and isolation.
- graph node success and failure behavior.
- compiled graph construction and artifact output.
- graph parity against the deterministic normalized review output.
- manifest `execution_engine` validation and defaults.
- router selection for deterministic and LangGraph engines.
- CLI `run-review-graph` execution.
- CLI `run-workflow --execution-engine` override behavior.
- optional persistence service behavior for run, artifact, and step records.

Use the fast unit-quality gate for normal development:

```sh
make check
```

## What Remains Deterministic By Default

The committed ReadySetRentables manifest still uses `execution_engine:
deterministic`. Existing manifest-driven workflow execution therefore stays on
the trusted deterministic implementation unless a manifest or CLI invocation
explicitly opts into LangGraph.

The graph path reuses the existing ingestion and artifact helpers. It does not
replace domain parsing, artifact serialization, approval gate enforcement, or
Postgres repository responsibilities.

## Intentionally Deferred

- agents
- model clients
- LLM calls
- model invocation tracking
- token/cost database tables
- OpenTelemetry
- autonomous planning
- Kubernetes
- UI/dashboard
- production deployment
- LangGraph node tracing beyond current workflow step records
