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
or the CLI override. LangGraph currently orchestrates deterministic nodes only;
there are still no agents, model clients, or LLM calls.

LangGraph should initially own workflow control flow and structured graph state,
while domain parsing, artifact writing, Postgres repositories, and model
provider calls remain outside graph nodes.

See `docs/langgraph-orchestration.md` for the Phase 3 design baseline.
See `docs/phase-3-completion-checklist.md` for the current completion summary.

### Phase 4: Agents And Model-Client Baseline

Phase 4 is active next. It should introduce the first cautious model-client and
agent foundations, not production autonomy. The goal is to define a shared model
invocation boundary, keep all provider calls behind that boundary, attach future
invocations to `run_id` and `step_id` when available, preserve artifact outputs,
and enforce the token/cost governance rules before any cloud-model usage
expands.

The initial Phase 4 work should remain local-first and observable. It should
avoid direct provider calls from agents, avoid hidden prompt or cost behavior,
and keep model outputs inspectable as artifacts when useful.

See `docs/model-client-architecture.md` for the Phase 4 design baseline. The
first implementation steps should favor a fake/in-memory model client or local
Ollama adapter before any cloud provider integration.

OpenTelemetry, LangGraph node tracing, dashboards, Kubernetes execution,
production deployment, autonomous planning, token/model invocation tables, and
production-grade LLM workflows remain deferred until a later task explicitly
narrows one of those areas.
