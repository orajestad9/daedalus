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

Phase 7 is active. It models the real ReadySetRentables production pipeline on
top of the existing Daedalus generic infrastructure. Phase 6 left Daedalus with
working fake/local paths, a manual Ollama CLI path, generic evaluation and
comparison models, and artifact and model invocation persistence. Phase 7 uses
those foundations to define real RSR domain contracts before implementing Claude
or wiring the full LangGraph graph.

Planned Phase 7 work:

- `ReviewInsightExtractionInput` and `ReviewInsightExtractionResult` domain
  contract models for the local Ollama insight extraction step
- `NeighborhoodProfileInput` and `NeighborhoodProfileResult` domain contract
  models for the future Claude neighborhood profile generation step
- `ReviewInsightExtractionAgent` — wraps `ModelClient`, intended for local
  Ollama execution; follows the same pattern as `ReviewThemeSummaryAgent`
- `NeighborhoodProfileAgent` shell — wraps `ModelClient`, not implemented until
  the Claude provider adapter exists
- `ArtifactType.REVIEW_INSIGHTS` and `ArtifactType.NEIGHBORHOOD_PROFILE`
  recognized artifact type values
- `write_review_insights_json(...)`, `write_neighborhood_profile_markdown(...)`,
  and `write_neighborhood_profile_json(...)` artifact writers
- versioned prompt template placeholder files at
  `prompts/readysetrentables/review_insight_extraction/v0.md` and
  `prompts/readysetrentables/neighborhood_profile/v0.md`
- `evaluate_review_insights_json(...)` — structural evaluator shell for
  `review_insights.json`
- `evaluate_neighborhood_profile_markdown(...)` — structural evaluator shell for
  `neighborhood_profile.md`

All Phase 7 domain contracts, agents, and evaluators stay inside RSR domain
modules. Generic platform infrastructure must not hardcode RSR logic. Claude
integration, cloud provider calls, and full LangGraph pipeline wiring remain
deferred until Phase 8.

See `docs/phase-7-rsr-real-pipeline.md` for the Phase 7 design baseline.

OpenTelemetry, dashboards, Kubernetes execution, production deployment,
autonomous planning, cloud provider clients, provider SDKs, and production-grade
LLM workflows remain deferred until a later task explicitly narrows one of those
areas.
