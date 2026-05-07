# Phase 0 Completion Checklist

## Summary

Phase 0 establishes the deterministic, local-first foundation for Daedalus. The
ReadySetRentables review workflow can ingest synthetic Airbnb review CSV data,
normalize it into structured models, write durable artifacts, and run through
both direct CLI arguments and a YAML workflow manifest.

This phase is intentionally small: it creates stable boundaries for workflows,
artifacts, manifests, run records, logging, and approval gates before adding
agents, model clients, databases, distributed execution, or observability
systems.

## Completed Checklist

- [x] Python 3.12 `src/` layout project baseline.
- [x] `pytest`, `ruff`, and `mypy` checks wired through `make check`.
- [x] Makefile with repeatable local development commands.
- [x] ReadySetRentables review domain models.
- [x] Synthetic sample Airbnb review CSV data.
- [x] Deterministic CSV ingestion using `csv.DictReader`.
- [x] Normalized review JSON artifact export.
- [x] Companion metadata JSON artifact.
- [x] Human-readable markdown workflow summary artifact.
- [x] Generic workflow run record JSON artifact.
- [x] CLI command for direct review normalization.
- [x] CLI command for manifest-driven workflow execution.
- [x] YAML workflow manifest loading and validation.
- [x] Orchestrator-layer workflow router.
- [x] Structured logging baseline.
- [x] Workflow `run_id` support.
- [x] Human approval gate for manifest-driven runs.
- [x] Approval status recorded in workflow results and summaries.
- [x] Shared `WorkflowStatus`, `ArtifactType`, `WorkflowName`, and
  `WorkflowDomain` enums.
- [x] GitHub Actions CI runs `make check` on pushes and pull requests targeting
  `main`.

## Runnable Commands

Run the full local check suite:

```sh
make check
```

Normalize the committed sample CSV into artifacts:

```sh
make normalize-sample
```

Run the workflow directly through the CLI:

```sh
daedalus normalize-reviews --input sample_data/readysetrentables_reviews/airbnb_reviews_sample.csv --output artifacts/readysetrentables/normalized_reviews.json
```

Run the workflow from its manifest:

```sh
daedalus run-workflow --manifest workflows/readysetrentables_review_normalization.yaml
```

## Current Artifact Outputs

The ReadySetRentables review normalization workflow currently writes:

- `normalized_reviews.json`
- `normalized_reviews.metadata.json`
- `normalized_reviews.summary.md`
- `normalized_reviews.run.json`

These artifacts make the workflow both machine-readable and human-inspectable.
The normalized JSON contains review data, metadata connects the output to the
run, the markdown summary gives a quick review surface, and the run record
captures workflow execution state for future persistence.

## Architecture Boundaries Established

- Domain-specific review logic lives under
  `src/daedalus/domains/readysetrentables_reviews/`.
- Manifest loading lives in shared platform code under `src/daedalus/shared/`.
- Workflow routing and run-record concepts live in
  `src/daedalus/orchestrator/`.
- Telemetry setup is centralized under `src/daedalus/telemetry/`.
- CLI code delegates workflow routing to the orchestrator instead of owning
  routing logic.
- Approval enforcement is handled by the orchestrator for manifest-driven
  workflows.
- Generated artifacts are written under ignored local artifact paths.
- CI runs the same `make check` command used locally, keeping human and agent
  quality gates aligned.

## Intentionally Deferred

Phase 0 does not include:

- Postgres persistence.
- OpenTelemetry.
- LangGraph.
- Actual LLM/model clients.
- Agents.
- Docker.
- Kubernetes.
- Persistent approval records.
- UI/dashboard.

## Phase 1 Readiness Criteria

Daedalus is ready to move into Phase 1 when:

- `make check` passes from a clean working tree.
- `make normalize-sample` writes all four expected artifacts.
- `daedalus run-workflow --manifest workflows/readysetrentables_review_normalization.yaml`
  succeeds.
- The run record provides enough structure to map cleanly to a future
  `workflow_runs` persistence table.
- Approval requirements are enforced before manifest-driven execution.
- Future work can extend existing boundaries instead of moving core workflow
  responsibilities out of their established packages.
