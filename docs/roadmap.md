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

Phase 2 is now focused on local observability and run inspection before adding
model or agent execution. Current Phase 2 progress includes workflow
`duration_ms`, lifecycle timing helpers, workflow step records, a
`workflow_steps` schema, step persistence support, runtime step collection,
`show-run` step display, workflow steps in summary markdown artifacts, a run
inspection formatter, structured logging context with `run_id`, and a stronger
`make db-check` path that verifies persisted run inspection.

See `docs/observability.md` for the current observability architecture.

### Later Phases: Model And Agent Foundations

Model-client and agent foundations should be introduced only after honoring the
token/cost governance rules. That work should keep model calls behind a shared
abstraction, attach future invocations to `run_id`, preserve artifact
boundaries, and avoid direct provider calls from agents.
