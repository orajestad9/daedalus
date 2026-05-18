## Roadmap

### Phase 0: Deterministic Local Foundation

Phase 0 foundation work is complete. Daedalus now has a deterministic
ReadySetRentables review normalization workflow, manifest-driven execution,
durable local artifacts, run records, structured logging, CI, and a first human
approval gate.

See `docs/phase-0-completion-checklist.md` for the current completion summary
and Phase 1 readiness criteria.

### Phase 1: Persistence

The Phase 1 local persistence baseline is complete. It builds on the Phase 0
boundaries without moving core responsibilities out of their packages. The
default unit-quality gate remains database-free.

The first Phase 1 foundation includes a local Docker Compose Postgres service
with placeholder-only environment configuration, SQL migrations, connection
helpers, repositories, optional persisted workflow execution, and a local
`make db-check` integration command. Operators can persist runs with
`run-workflow --persist`, inspect one run with `show-run`, and list recent runs
with `list-runs`.

See `docs/phase-1-persistence.md` for the current persistence workflow. App
container builds, production deployment, model invocation persistence, and richer
observability were intentionally deferred from Phase 1.

Token and cost governance is a cross-cutting requirement for future phases. See
`docs/token-cost-governance.md` before adding model clients, agents, LangGraph
workflows, cloud-model calls, or model invocation persistence.

### Phase 2: Observability And Run Inspection

The Phase 2 local observability baseline is complete enough to move toward Phase
3. Phase 2 added workflow `duration_ms`, lifecycle timing helpers, workflow step
records, a `workflow_steps` schema, step persistence support, runtime step
collection, failure-path step recording tests, `show-run` step display, workflow
steps in summary markdown artifacts, a run inspection formatter, structured
logging context with `run_id`, future model invocation observability
requirements, and a stronger `make db-check` path that verifies persisted run
inspection.

See `docs/observability.md` for the current observability architecture.

### Phase 3: LangGraph Orchestration Baseline

Phase 3 is complete or near-complete. It establishes a LangGraph orchestration
baseline that reproduces the existing deterministic ReadySetRentables workflow
without changing artifact outputs, persistence behavior, approval gates, or
tests.

Current Phase 3 progress includes the LangGraph dependency, architecture
documentation, typed graph state, deterministic graph nodes, a compiled graph
runner, direct `run-review-graph` CLI execution, graph/deterministic parity
tests, manifest `execution_engine` routing, a `run-workflow --execution-engine`
override, and `make db-check` coverage for persisted LangGraph execution.

The deterministic workflow remains the default execution engine. LangGraph is
opt-in through direct graph execution, manifest `execution_engine: langgraph`,
or the CLI override. Phase 3 itself orchestrated deterministic nodes only; Phase
5A has since added a fake/local agent node with `FakeModelClient`, and Phase 5B
has since added explicit manual local Ollama CLI paths. LangGraph itself still
does not call real providers.

LangGraph should initially own workflow control flow and structured graph state,
while domain parsing, artifact writing, Postgres repositories, and model
provider calls remain outside graph nodes.

See `docs/langgraph-orchestration.md` for the Phase 3 design baseline.
See `docs/phase-3-completion-checklist.md` for the current completion summary.

### Phase 4: Agents And Model-Client Baseline

Phase 4 is complete. It introduced the first cautious model-client and agent
foundations, not production autonomy. The goal was to define a shared model
invocation boundary, keep all provider calls behind that boundary, attach future
invocations to `run_id` and `step_id` when available, preserve artifact outputs,
and enforce the token/cost governance rules before any cloud-model usage
expands.

The initial Phase 4 work remains local-first and observable. Current progress
includes core model-client types, `FakeModelClient`, `RecordingModelClient`,
budget validation, model invocation records and repositories, fake model
invocation inspection through `show-run`, versioned prompt templates, review
theme summary input/result models, deterministic compact input building, a
review theme summary agent tested with `FakeModelClient`, a markdown artifact
writer, the `summarize-review-themes-fake` CLI command, recognized
`review_theme_summary` artifact records, the
`record-review-theme-summary-artifact` CLI command, `make fake-summary-check`
for a no-Docker local artifact check, and the Phase 5A
`make fake-summary-db-check` path for inspecting the persisted graph summary
artifact and fake model invocation metadata with `show-run`.

The first AI-assisted feature path is the ReadySetRentables review theme summary
agent, which summarizes compact normalized review inputs through the shared
`ModelClient` boundary and writes an inspectable summary artifact. Phase 4
itself was fake/local only; Phase 5B now adds explicit manual local Ollama usage
without making Ollama a workflow or LangGraph default.

See `docs/model-client-architecture.md` for the Phase 4 design baseline. Future
provider implementation should favor a local Ollama adapter before any cloud
provider integration.
See `docs/review-theme-summary-agent.md` for the current fake/local agent path.

### Phase 5A: Fake-Agent LangGraph Integration

Phase 5A is complete. It wires the fake/local ReadySetRentables review theme
summary agent into the LangGraph workflow before Daedalus adds Ollama or any
other real provider client.

Current Phase 5A progress includes graph state fields for review theme summary
data, fake summary input building, a fake summary agent node using
`FakeModelClient`, a `write_review_theme_summary_artifact` node, and compiled
LangGraph wiring that writes `review_theme_summary.md`. Persisted LangGraph runs
now also save the `review_theme_summary` artifact record and fake model
invocation metadata so `show-run` can display provider, model, prompt, token,
cost, and status fields. The deterministic workflow remains unchanged.

The goal is to prove the integrated graph path with `FakeModelClient`, versioned
prompts, workflow steps, `review_theme_summary.md` artifact output, artifact
record persistence, and fake invocation metadata while keeping real provider
SDKs, network calls, and real LLM calls out of scope.

See `docs/phase-5a-fake-agent-langgraph.md` for the integration baseline.

### Phase 5B: Local Ollama Provider

Phase 5B is complete. It adds a local `OllamaModelClient` provider that satisfies
the existing `ModelClient` protocol without adding cloud provider SDKs or cloud
model usage.

The Phase 5B path should keep Daedalus local-first and explicit. Ollama support
should be opt-in, use safe local defaults, preserve `RecordingModelClient`,
budget validation, prompt versioning, artifact outputs, and model invocation
metadata, and leave `make check` free from live Ollama requirements.

Current Phase 5B progress includes `OllamaModelClientSettings`, Ollama
request/response helpers, `OllamaModelClient` with injectable transport,
`ollama-smoke-check`, `summarize-review-themes-ollama`,
`make ollama-local-check`, `make ollama-summary-local-check`, and optional
artifact and model invocation persistence through `summarize-review-themes-ollama
--persist-artifact --persist-invocation --run-id <run-id>`.

See `docs/phase-5b-ollama-provider.md` for the Ollama provider design.

Upcoming Phase 5B work should stay incremental:

- add optional local Ollama evaluation examples outside `make check`
- consider a LangGraph Ollama opt-in path only after the manual Ollama path
  remains stable
- keep deterministic and fake LangGraph paths unchanged while Ollama matures

### Phase 6: Evaluation Harness

Phase 6 is complete. It introduces a generic evaluation harness for checking
model outputs and workflow artifacts across domains. The first concrete example
is ReadySetRentables `review_theme_summary.md`. Generic Daedalus evaluation does
not hardcode ReadySetRentables into the platform layer.

Current Phase 6 progress includes generic evaluation models
(`EvaluationStatus`, `EvaluationSeverity`, `EvaluationCheckResult`,
`EvaluationReport`), generic comparison models (`EvaluationComparisonStatus`,
`EvaluationComparisonItem`, `EvaluationComparisonReport`), generic evaluation
and comparison report artifact writers, `ArtifactType.EVALUATION_REPORT` and
`ArtifactType.EVALUATION_COMPARISON_REPORT`, a deterministic ReadySetRentables
review theme summary evaluator, a deterministic ReadySetRentables review theme
summary comparison evaluator, the `evaluate-review-theme-summary` CLI, the
`compare-review-theme-summaries` CLI, the `record-evaluation-report-artifact`
CLI, the `record-evaluation-comparison-report-artifact` CLI, file-only local
checks (`evaluation-check`, `comparison-check`), and optional DB-backed checks
(`evaluation-db-check`, `comparison-db-check`).

All Phase 6 evaluation and comparison checks are deterministic, local, and
artifact-based. They do not require live Ollama in `make check`, do not call
external providers, and do not use another model to judge subjective quality.
Evaluation and comparison are not automatically wired into `run-workflow` or
LangGraph; both remain explicit and opt-in.

Possible future Phase 6 or later work:

- optional `run-workflow` flag to evaluate after workflow completion
- optional automatic evaluation artifact persistence
- fake-vs-Ollama comparison workflow examples
- evaluator-model scoring behind `ModelClient` controls
- future RSR `review_insights.json` and `neighborhood_profile.md` evaluators
- future Skimmr document summary evaluators
- `show-run` evaluation and comparison summary display

See `docs/phase-6-evaluation-harness.md` for the current evaluation harness
capabilities and future work.

### Phase 7: ReadySetRentables Real Pipeline Modeling

Phase 7 is complete. It modeled the real ReadySetRentables production pipeline
on top of the existing Daedalus generic infrastructure: domain contracts,
artifact types and writers, prompt template placeholders, and deterministic
evaluator shells for the real pipeline steps. Phase 7 deliberately did not
implement Claude or wire the full multi-agent LangGraph workflow.

Phase 7 deliverables:

- `ReviewInsightExtractionInput`, `ReviewInsightTheme`, and
  `ReviewInsightExtractionResult` domain contract models
- `NeighborhoodProfileInput`, `NeighborhoodProfileSection`, and
  `NeighborhoodProfileResult` domain contract models
- `ArtifactType.REVIEW_INSIGHTS`,
  `ArtifactType.NEIGHBORHOOD_PROFILE_MARKDOWN`, and
  `ArtifactType.NEIGHBORHOOD_PROFILE_JSON` recognized artifact type values
- `write_review_insights_json(...)`, `write_neighborhood_profile_markdown(...)`,
  and `write_neighborhood_profile_json(...)` artifact writers
- versioned prompt template placeholder files at
  `prompts/readysetrentables/review_insight_extraction/v0.md` and
  `prompts/readysetrentables/neighborhood_profile/v0.md`
- deterministic evaluator shells:
  `evaluate_review_insights_json(...)`,
  `evaluate_neighborhood_profile_markdown(...)`, and
  `evaluate_neighborhood_profile_json(...)`

All Phase 7 domain contracts, models, writers, and evaluators stay inside RSR
domain modules. Generic platform infrastructure does not hardcode RSR logic.

See `docs/phase-7-rsr-real-pipeline.md` for the Phase 7 design baseline.

Deferred for later phases (not blocking Phase 8):

- `ReviewInsightExtractionAgent` for local Ollama execution behind `ModelClient`
- `NeighborhoodProfileAgent` shell for future Claude execution behind
  `ModelClient`
- Claude/Anthropic provider adapter
- LangGraph and `run-workflow` wiring for the full RSR pipeline
- optional CLI commands for manual execution and artifact recording

### Phase 8: ReadySetRentables Read-Only Source Extraction Boundary

The offline scope of Phase 8 is complete. It designs the safe read-only boundary
for later extracting RSR source data from the real ReadySetRentables application
database into Daedalus domain inputs and ships the offline parts that do not
require homelab access. The real Postgres connection code, SQL, and DB-backed
checks are scoped for later steps when homelab access is available.

Phase 8 offline deliverables:

- design doc for the read-only source extraction boundary
- `RsrSourceExtractionRequest`, `RsrSourceReviewRecord`,
  `RsrSourceListingContext`, `RsrSourceNeighborhoodContext`, and
  `RsrSourceExtractionResult` source extraction models
- `ArtifactType.RSR_SOURCE_EXTRACT` generic artifact type
- `write_rsr_source_extract_json(...)` artifact writer
- `build_sample_rsr_source_extraction_result()` synthetic fixture
- `evaluate_rsr_source_extract_json(...)` deterministic evaluator
- `evaluate-rsr-source-extract` CLI command
- `make source-extract-check` local file-only Makefile target
- proposed `RsrSourceReadOnlyRepository` adapter responsibilities
- testing strategy using fake fixtures and mocked repositories first

Phase 8 explicitly does not:

- add real Postgres connection code for the RSR source DB
- add real SQL queries
- mark real DB integration as implemented
- write back to the RSR application database
- require homelab access for `make check`

See `docs/phase-8-rsr-source-extraction.md` for the Phase 8 design baseline.

### Phase 9: Homelab / Daedalus Metadata Postgres Readiness

Phase 9 is complete for Daedalus metadata DB readiness. It validated the UM790 /
homelab environment for Daedalus metadata Postgres before touching the real
ReadySetRentables source database. The completed metadata DB readiness work
proves local metadata persistence, migrations, workflow run inspection, artifact
records, model invocation records, evaluation report artifact records, and
comparison report artifact records on the homelab host while keeping RSR source
extraction deferred.

Verified Phase 9 metadata DB readiness:

- Daedalus is cloned under `~/apps/daedalus` on the UM790
- the UM790 repo is clean and current on `main`
- Python virtual environment setup and editable install have been verified
- Docker and Docker Compose are available
- Daedalus metadata Postgres starts successfully from a local untracked `.env`
- `make check` passes
- `make db-check` passes
- `make fake-summary-db-check` passes
- `make evaluation-db-check` passes
- `make comparison-db-check` passes
- migrations, deterministic and LangGraph persisted workflow runs, artifact
  persistence, fake model invocation persistence, evaluation/comparison
  artifact recording, `list-runs`, `show-run`, and cleanup behavior are
  verified

Real RSR source database extraction remains a future phase. Phase 9 does not add
source DB connection code, SQL, read-only repository/adapter code, DB-backed RSR
source extraction checks, multi-agent workflow wiring, Claude/Anthropic support,
cloud provider support, or write-back behavior.

See `docs/phase-9-homelab-postgres-readiness.md` for the Phase 9 readiness
baseline and homelab workflow rules.

### Phase 10: RSR Read-Only Source DB Adapter

Phase 10 has validated the first real ReadySetRentables source DB bridge on the
UM790 at small scale. The current adapter path includes separate
`RSR_SOURCE_POSTGRES_*` settings, an RSR source DB connection helper, source DB
row mappers, `RsrSourceReadOnlyRepository.extract_source_data(...)`, the manual
`extract-rsr-source-data` CLI, the deterministic `evaluate-rsr-source-extract`
CLI, and the manual `record-rsr-source-extract-artifact` CLI for linking an
existing `rsr_source_extract.json` to a persisted Daedalus workflow run. Phase
10 also includes the pure `ReviewInsightExtractionInput` builder and the
file-only `build-review-insight-input` CLI.

The verified UM790 smoke test used `market_name="san-diego"` and
`--max-reviews 10`, wrote `rsr_source_extract.json`, evaluated the artifact,
recorded it as `ArtifactType.RSR_SOURCE_EXTRACT`, and confirmed through
`show-run` that the `rsr_source_extract` artifact is visible in run inspection.
Only aggregate counts were documented; real review text and artifact contents
remain private.

The source extract to review insight input bridge has also been manually
verified on UM790. Real source rows were transformed into
`review_insight_extraction_input.json` with safe metadata showing
`market_name=san-diego`, `representative_review_count=10`,
`average_rating=4.99`, and all six supported rating categories. Representative
review text is carried forward in the local artifact but is not printed or
documented.

The Phase 10 source DB bridge remains manual and guarded. It is not wired into
LangGraph or `run-workflow`, does not run under `make check`, does not make
model calls, and does not write back to the ReadySetRentables app DB. A future
optional DB-backed Makefile target may automate the smoke path, but it should
remain outside `make check`, require local `RSR_SOURCE_POSTGRES_*` settings,
use a small review limit, and avoid printing source data.

Next likely RSR pipeline work is the local Ollama review insight extraction
agent that consumes `ReviewInsightExtractionInput`, keeping Claude/Anthropic,
full multi-agent LangGraph workflow wiring, and automatic downstream review
insight extraction deferred until explicitly scoped.

Still deferred beyond Phase 10 adapter work:

- optional guarded DB-backed source extraction check target
- local Ollama review insight extraction agent
- Ollama workflow wiring for source-derived review insight extraction
- Claude/Anthropic provider support
- full multi-agent workflow wiring
- writing results back to ReadySetRentables
- cloud provider clients and provider SDK expansion

See `docs/phase-10-rsr-source-db-adapter.md` for the Phase 10 adapter status.

OpenTelemetry, dashboards, Kubernetes execution, production deployment,
autonomous planning, cloud provider clients, provider SDKs, and production-grade
LLM workflows remain deferred until a later task explicitly narrows one of those
areas.
