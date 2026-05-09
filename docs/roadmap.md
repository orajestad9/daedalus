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
5A has since added a fake/local agent node with `FakeModelClient`. There are
still no real provider clients or real LLM calls.

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
`ModelClient` boundary and writes an inspectable summary artifact. It is still
fake/local only: no real provider clients, provider SDKs, network calls, or real
LLM calls exist yet.

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

Phase 5B is active/next. It starts by designing a local `OllamaModelClient`
provider that satisfies the existing `ModelClient` protocol without adding
cloud provider SDKs, cloud model usage, or real LLM calls in the design step.

The Phase 5B path should keep Daedalus local-first and explicit. Ollama support
should be opt-in, use safe local defaults, preserve `RecordingModelClient`,
budget validation, prompt versioning, artifact outputs, and model invocation
metadata, and leave `make check` free from live Ollama requirements.

See `docs/phase-5b-ollama-provider.md` for the Ollama provider design.

Upcoming Phase 5B work should stay incremental:

- implement `OllamaModelClientSettings`
- implement `OllamaModelClient` with mocked-HTTP unit tests
- add an optional local Ollama check outside `make check`
- wire Ollama into the review theme summary path only after the fake path
  remains stable

OpenTelemetry, dashboards, Kubernetes execution, production deployment,
autonomous planning, cloud provider clients, provider SDKs, and production-grade
LLM workflows remain deferred until a later task explicitly narrows one of those
areas.
