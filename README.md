# Daedalus

Daedalus is a local-first Python AI workflow orchestration platform for
observable, human-approved AI pipelines.

## What It Demonstrates

- **Workflow orchestration** — deterministic and LangGraph execution engines,
  manifest-driven, with run/step/artifact records
- **Model-client abstraction** — `ModelClient` protocol with `FakeModelClient`,
  `RecordingModelClient`, and `OllamaModelClient` behind a shared boundary
- **Artifact lineage** — every model output is an artifact record linked to a
  workflow run; no raw prompts or raw outputs in Postgres
- **Model invocation tracking** — provider, model, prompt name/version, token
  counts, estimated cost, and status persisted per invocation
- **Token and cost governance** — `ModelBudget` enforced before any provider
  call; cloud-model opt-in is explicit
- **Deterministic evaluation and comparison** — structural checks on produced
  artifacts; fake-vs-Ollama comparison support; no model provider calls required
- **Local-first provider strategy** — fake paths work without any provider;
  Ollama is opt-in locally; cloud providers are deliberately deferred

## Current Capabilities

- Deterministic and LangGraph workflow execution from YAML manifests
- Workflow run, step, and artifact persistence to local Postgres
- `show-run` and `list-runs` for persisted run inspection
- `FakeModelClient` for provider-free local boundary checks
- `RecordingModelClient` wrapping any `ModelClient` to produce invocation records
- `OllamaModelClient` for explicit manual local provider calls
- Model budget validation and invocation metadata persistence
- Versioned prompt templates with name/version tracking on every invocation
- Fake review theme summary path integrated into LangGraph
- Manual Ollama review theme summary CLI with optional artifact/invocation
  persistence
- Generic evaluation harness: `EvaluationReport`, `EvaluationCheckResult`,
  evaluation artifact writers
- Generic comparison harness: `EvaluationComparisonReport`, comparison artifact
  writers
- ReadySetRentables review theme summary evaluator and comparison evaluator
- Evaluation/comparison artifact recording for persisted runs
- Phase 7 RSR pipeline domain contracts: review insight extraction and
  neighborhood profile models, artifact types, and writers
- Phase 8 read-only RSR source extraction boundary: source extraction models,
  `rsr_source_extract.json` artifact writer, synthetic offline fixture,
  deterministic evaluator, and `evaluate-rsr-source-extract` CLI command

## ReadySetRentables: First Domain

ReadySetRentables is the first concrete domain pipeline built on Daedalus.
Daedalus remains generic throughout; RSR-specific behavior stays under
`src/daedalus/domains/readysetrentables_reviews/`.

Current RSR support:

- Review normalization from Airbnb CSV to structured JSON artifacts
- Fake review theme summary generation through LangGraph (`FakeModelClient`)
- Manual Ollama review theme summary via `summarize-review-themes-ollama`
- Structural evaluation of `review_theme_summary.md`
- Comparison of two `review_theme_summary.md` artifacts
- Phase 7 domain contracts: `ReviewInsightExtractionInput`,
  `ReviewInsightExtractionResult`, `NeighborhoodProfileInput`,
  `NeighborhoodProfileResult`
- Artifact types and writers for `review_insights.json`,
  `neighborhood_profile.md`, and `neighborhood_profile.json`

## What Is Intentionally Not Implemented Yet

- Ollama is not automatic: it is not wired into LangGraph or `run-workflow` and
  is not a default provider anywhere
- Claude/Anthropic provider adapter is not implemented; no cloud provider
  clients exist
- The full RSR multi-agent pipeline (review insight extraction → neighborhood
  profile generation) is not yet wired into LangGraph or `run-workflow`
- Evaluation and comparison are deterministic and manual; they are not
  automatically triggered by workflows
- Evaluator-model scoring (using a model to judge subjective quality) is deferred
- OpenTelemetry, dashboards, and production deployment are deferred

## Quickstart

Install local development dependencies:

```sh
make install
```

Run the full local check suite (unit tests, lint, format, type check):

```sh
make check
```

`make check` is unit-only. It does not require Docker, Postgres, Ollama, or
network access.

Run the LangGraph fake summary check (no Docker or `.env` required):

```sh
make graph-fake-summary-check
```

Run the evaluation check (no Docker or `.env` required):

```sh
make evaluation-check
```

Run the comparison check (no Docker or `.env` required):

```sh
make comparison-check
```

Run the RSR source extraction fixture/evaluation check (no Docker or `.env`
required):

```sh
make source-extract-check
```

## Optional DB-Backed Checks

These targets require Docker and a local `.env`. They are not called by
`make check`.

Copy the example environment file and edit the placeholder values:

```sh
cp .env.example .env
```

Run the full local Postgres integration check:

```sh
make db-check
```

Verify persisted fake LangGraph summary path with `show-run` inspection:

```sh
make fake-summary-db-check
```

Verify persisted evaluation artifact recording:

```sh
make evaluation-db-check
```

Verify persisted comparison artifact recording:

```sh
make comparison-db-check
```

## Optional Local Ollama Checks

These targets require a running local Ollama instance with a compatible model.
They are not called by `make check`.

Verify the Ollama provider smoke check:

```sh
make ollama-local-check
```

Verify the manual Ollama review theme summary CLI:

```sh
make ollama-summary-local-check
```

## Project Status

Phase 6 (evaluation and comparison harness) is complete. Phase 7 (real RSR
pipeline modeling: domain contracts, artifact types and writers, prompt
placeholders, deterministic evaluator shells) is complete. Phase 8 (read-only
source extraction boundary: source models, `rsr_source_extract` artifact type
and writer, synthetic fixture, deterministic evaluator, CLI command, and local
make check) is complete for its offline scope. Phase 9 metadata Postgres
readiness is verified on the UM790. Phase 10 starts the real RSR read-only
source DB adapter plan; full RSR workflow wiring and provider expansion remain
deferred.

- Roadmap: [`docs/roadmap.md`](docs/roadmap.md)
- Phase 7 design: [`docs/phase-7-rsr-real-pipeline.md`](docs/phase-7-rsr-real-pipeline.md)
- Phase 8 design: [`docs/phase-8-rsr-source-extraction.md`](docs/phase-8-rsr-source-extraction.md)
- Phase 9 readiness: [`docs/phase-9-homelab-postgres-readiness.md`](docs/phase-9-homelab-postgres-readiness.md)
- Phase 10 adapter plan: [`docs/phase-10-rsr-source-db-adapter.md`](docs/phase-10-rsr-source-db-adapter.md)
- Observability and `show-run`: [`docs/observability.md`](docs/observability.md)
- Token and cost governance: [`docs/token-cost-governance.md`](docs/token-cost-governance.md)
- Model-client architecture: [`docs/model-client-architecture.md`](docs/model-client-architecture.md)
