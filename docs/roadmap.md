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

### Phase 3: Model Invocation And Agent Foundations

Phase 3 should introduce model invocation tracking and model-client foundations
only after honoring the token/cost governance rules. That work should keep model
calls behind a shared abstraction, attach future invocations to `run_id` and
`step_id` when available, preserve artifact boundaries, and avoid direct
provider calls from agents. Model invocation tracking should be added before or
alongside those clients so provider, model, prompt version, token usage,
estimated cost, status, timing, and input/output artifact references are
observable from the first model-backed workflow.

OpenTelemetry, LangGraph node tracing, dashboards, Kubernetes execution, and
production deployment remain later work unless a Phase 3 task explicitly narrows
one of those areas.
