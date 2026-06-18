# Daedalus

Daedalus is a local-first Python AI workflow orchestration platform for building
observable, human-approved AI pipelines on a developer machine. It currently
combines deterministic YAML workflows, optional LangGraph execution, local
artifact generation, Daedalus metadata Postgres persistence, model invocation
records, deterministic evaluation/comparison tools, and a guarded
ReadySetRentables source extraction boundary without making cloud model calls or
writing back to the source application.

## What Daedalus Demonstrates

- **Workflow orchestration**: deterministic and LangGraph execution paths driven
  by workflow manifests.
- **Artifact lineage**: generated files are represented as artifact records tied
  to workflow runs.
- **Model invocation tracking**: provider, model, prompt identity, token counts,
  estimated cost, status, and artifact paths can be persisted for inspection.
- **Local-first model strategy**: fake model paths are provider-free, Ollama is
  explicit and local, and cloud providers are deferred.
- **Deterministic evaluation/comparison**: artifact checks and comparison reports
  run without model calls.
- **Safe source DB extraction boundary**: ReadySetRentables source extraction is
  read-only, sanitized, and separate from Daedalus metadata persistence.

## Current Capabilities

- Deterministic review normalization workflow from YAML manifests.
- LangGraph review workflow with the fake review theme summary path.
- Daedalus metadata Postgres persistence for workflow runs, steps, artifacts,
  and model invocation records.
- `show-run` and `list-runs` inspection for persisted runs.
- `FakeModelClient` and `RecordingModelClient` for local, testable model
  boundaries.
- Manual Ollama paths for review theme summaries and in-progress review insight
  extraction.
- ReadySetRentables read-only source DB extraction into `rsr_source_extract.json`.
- Source extract evaluation through deterministic local checks.
- Source extract to `review_insight_extraction_input.json` bridge.
- Review insight extraction agent, output parser, artifact writer, and CLI work
  in progress.
- Review insights evaluation through deterministic local checks.
- Existing `review_insights.json` artifacts can be recorded against persisted
  workflow runs for `show-run` inspection.

## ReadySetRentables Status

ReadySetRentables is the first concrete domain pipeline. RSR-specific behavior
lives under `src/daedalus/domains/readysetrentables_reviews/`; generic
orchestration, persistence, model-client, and evaluation code stays reusable.

Current RSR state:

- Source DB extraction works manually through the separate RSR source DB settings
  and writes sanitized local artifacts.
- `review_insight_extraction_input.json` generation from `rsr_source_extract.json`
  works.
- Local Ollama review insight extraction is in progress. The CLI exists, but the
  live path still needs more reliable JSON output/schema handling and clearer
  safe failure diagnostics.
- Claude/Anthropic provider support and neighborhood profile generation are
  deferred.
- Real generated artifacts should remain local and untracked under `artifacts/`.

## Intentional Limitations

- Ollama is not a default provider.
- Ollama is not wired into LangGraph or `run-workflow`.
- Claude/Anthropic provider support is not implemented.
- The full source extraction -> review insights -> neighborhood profile
  multi-agent workflow is not wired yet.
- Deterministic evaluation and comparison are explicit commands, not automatic
  workflow steps.
- There is no writeback to the ReadySetRentables source database.
- Real source-derived artifacts can contain review text and should not be
  printed, documented, or committed.

## Useful Commands

Run the local unit-quality gate:

```sh
make check
```

`make check` does not require Docker, Postgres, Ollama, or network access.

Run the file-only RSR source extraction fixture/evaluation check:

```sh
make source-extract-check
```

Run optional Daedalus metadata Postgres integration checks:

```sh
make db-check
```

`make db-check` requires Docker and a local `.env`; it is not part of
`make check`.

Manual RSR source extract path:

```sh
daedalus extract-rsr-source-data \
  --market-name <market-name> \
  --max-reviews 10 \
  --output-json artifacts/readysetrentables/rsr_source_extract.json

daedalus build-review-insight-input \
  --source-extract artifacts/readysetrentables/rsr_source_extract.json \
  --output-json artifacts/readysetrentables/review_insight_extraction_input.json

daedalus extract-review-insights-ollama \
  --input-json artifacts/readysetrentables/review_insight_extraction_input.json \
  --model <local-ollama-model> \
  --output-json artifacts/readysetrentables/review_insights.json

daedalus evaluate-review-insights \
  --review-insights artifacts/readysetrentables/review_insights.json \
  --output-json artifacts/readysetrentables/review_insights.evaluation.json \
  --output-md artifacts/readysetrentables/review_insights.evaluation.md

daedalus record-review-insights-artifact \
  --run-id <run-id> \
  --path artifacts/readysetrentables/review_insights.json
```

Inspect a persisted run:

```sh
daedalus show-run --run-id <run-id>
```

## Next Development Steps

- Fix/improve Ollama review insight JSON reliability.
- Complete manual `review_insights.json` generation.
- Later wire source extraction and review insights into LangGraph.
- Later add Claude/Anthropic neighborhood profile generation.
- Later add human approval gates and optional RSR writeback/export.

## Project Notes

- Demo architecture: [`docs/architecture.md`](docs/architecture.md)
- Demo plan: [`docs/demo-plan.md`](docs/demo-plan.md)
- Demo readiness checklist:
  [`docs/demo-readiness-checklist.md`](docs/demo-readiness-checklist.md)
- Roadmap: [`docs/roadmap.md`](docs/roadmap.md)
- Observability and `show-run`: [`docs/observability.md`](docs/observability.md)
- Model-client architecture: [`docs/model-client-architecture.md`](docs/model-client-architecture.md)
- Token and cost governance: [`docs/token-cost-governance.md`](docs/token-cost-governance.md)
- Phase 10 RSR source DB adapter:
  [`docs/phase-10-rsr-source-db-adapter.md`](docs/phase-10-rsr-source-db-adapter.md)
- Phase 11 Ollama review insight status:
  [`docs/phase-11-ollama-review-insight-agent.md`](docs/phase-11-ollama-review-insight-agent.md)
