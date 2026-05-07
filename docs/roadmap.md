## Roadmap

### Phase 0: Deterministic Local Foundation

Phase 0 foundation work is complete. Daedalus now has a deterministic
ReadySetRentables review normalization workflow, manifest-driven execution,
durable local artifacts, run records, structured logging, CI, and a first human
approval gate.

See `docs/phase-0-completion-checklist.md` for the current completion summary
and Phase 1 readiness criteria.

### Phase 1: Persistence And Observability

The Phase 1 local persistence baseline is complete enough to move toward Phase
2. It builds on the Phase 0 boundaries without moving core responsibilities out
of their packages. The default unit-quality gate remains database-free.

The first Phase 1 foundation includes a local Docker Compose Postgres service
with placeholder-only environment configuration, SQL migrations, connection
helpers, repositories, optional persisted workflow execution, and a local
`make db-check` integration command. Operators can persist runs with
`run-workflow --persist`, inspect one run with `show-run`, and list recent runs
with `list-runs`.

See `docs/phase-1-persistence.md` for the current persistence workflow. App
container builds, production deployment, model invocation persistence, and richer
observability remain intentionally deferred.

Token and cost governance is a cross-cutting requirement for future phases. See
`docs/token-cost-governance.md` before adding model clients, agents, LangGraph
workflows, cloud-model calls, or model invocation persistence.

### Phase 2: Model And Agent Foundations

Phase 2 should introduce model-client and agent foundations only after honoring
the token/cost governance rules. The next work should keep model calls behind a
shared abstraction, attach future invocations to `run_id`, preserve artifact
boundaries, and avoid direct provider calls from agents.
