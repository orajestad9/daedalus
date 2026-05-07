## Roadmap

### Phase 0: Deterministic Local Foundation

Phase 0 foundation work is complete. Daedalus now has a deterministic
ReadySetRentables review normalization workflow, manifest-driven execution,
durable local artifacts, run records, structured logging, CI, and a first human
approval gate.

See `docs/phase-0-completion-checklist.md` for the current completion summary
and Phase 1 readiness criteria.

### Phase 1: Persistence And Observability

Phase 1 should build on the Phase 0 boundaries without moving core
responsibilities out of their packages. Likely next steps include Postgres
workflow persistence, richer observability, and additional workflow
implementations.

The first Phase 1 foundation is a local Docker Compose Postgres service with
placeholder-only environment configuration. Database dependencies, migrations,
connection code, repositories, and app container builds remain intentionally
deferred.
