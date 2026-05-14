# Phase 9: Homelab Postgres Readiness

Phase 9 validates the UM790 / homelab environment for Daedalus metadata
Postgres before Daedalus touches the real ReadySetRentables source database.
This phase is about proving that the local-first Daedalus runtime can persist
workflow metadata safely on the homelab host. It is not real RSR extraction.

## Database Boundary

Daedalus uses separate database responsibilities:

| Database | Role | Phase 9 Status |
|---|---|---|
| Daedalus metadata DB | workflow runs, workflow steps, artifact records, model invocation records, and approval/evaluation/comparison metadata as applicable | validated on UM790 |
| ReadySetRentables source DB | real application/source data for listings, reviews, neighborhoods, and operational context | not touched in Phase 9 |

The ReadySetRentables source database remains out of scope for this phase. Real
read-only extraction, SQL, and repository/adapter work are deferred until a
future phase with its own boundary review.

## Verified UM790 Readiness

The UM790 has been prepared and checked for Daedalus metadata Postgres usage:

- Daedalus repo cloned under `~/apps/daedalus`
- repo is clean and current on `main`
- Python 3.12.3 is available
- `.venv` was created
- dependencies were installed
- editable Daedalus install points to the repo root
- `make check` passes
- Docker and Docker Compose are available
- Daedalus metadata Postgres starts successfully
- migrations apply successfully
- `make db-check` passes

`make db-check` currently validates:

- migrations
- deterministic persisted workflow run
- LangGraph persisted workflow run
- artifact persistence
- model invocation persistence
- `list-runs`
- `show-run`

The verified `show-run` path displayed persisted artifacts and one fake model
invocation for the LangGraph workflow without exposing raw artifact contents or
raw prompt/model output text in committed documentation.

## UM790 Metadata DB Runbook

Use this checklist to repeat or troubleshoot the UM790 Daedalus metadata
Postgres setup.

Setup checklist:

- clone the repo under `~/apps/daedalus`
- create `.venv`
- install dependencies
- run `python -m pip install -e .` from the repo root
- verify the editable install points to the repo root
- create local `.env` from `.env.example` with a non-conflicting local
  Postgres host port
- confirm `.env` is untracked
- run `make check`
- run `make db-check`

Useful commands:

```sh
cd ~/apps/daedalus
source .venv/bin/activate
python -m pip show daedalus
.venv/bin/daedalus --help
git status --short
docker compose ps
make check
make db-check
```

### Port Collisions

The UM790 may already run other Postgres containers. Check existing containers
before choosing a Daedalus metadata DB host port:

```sh
docker ps
```

Avoid common occupied Postgres ports. Keep Docker Compose
`DAEDALUS_POSTGRES_HOST_PORT` aligned with Python `POSTGRES_PORT` in the local
untracked `.env`. Do not commit `.env`.

### Stale Editable Install

Symptom:

- `make check` passes, but `.venv/bin/daedalus --help` shows old CLI commands

Cause:

- the editable install points to `.venv/src/daedalus` or another stale path

Fix:

```sh
python -m pip uninstall -y daedalus
python -m pip install -e .
python -m pip show daedalus
```

The final `pip show` output should point to the repo root.

### DB Check Troubleshooting

- if `make db-check` fails before migrations, inspect Docker, Postgres, and
  local `.env` configuration
- if `make db-check` fails on CLI arguments, check the editable install
- if `make db-check` fails on port binding, choose a different local untracked
  port
- if `make db-check` leaves containers running, use `docker compose down`
- do not change tracked code directly on the UM790

## Port And Environment Guidance

The default Daedalus example Postgres host port may conflict on this UM790
because other Postgres containers already use common local ports. The UM790 uses
a local untracked `.env` with a non-conflicting Daedalus metadata Postgres host
port.

Rules for homelab metadata Postgres configuration:

- do not commit `.env`
- do not commit passwords, DSNs, private IP addresses, or real environment
  values
- keep Docker Compose Postgres variables and Python `POSTGRES_*` variables
  aligned
- use a non-conflicting host port when common Postgres ports are already in use
- keep local runtime files such as `.env`, `.venv`, Docker volumes, logs, and
  generated artifacts untracked

## Install And Editable Package Guidance

After cloning Daedalus on a host, create a virtual environment, install
dependencies, and install Daedalus editable from the repo root:

```sh
python -m pip install -e .
```

Stale editable installs can point at `.venv/src/daedalus` and show old CLI
command lists. Verify the active editable install and CLI surface with:

```sh
python -m pip show daedalus
.venv/bin/daedalus --help
```

The editable install should point to the cloned repo root, not a stale copy
under `.venv/src/daedalus`.

## Git Workflow Rule

All code, docs, tests, and Makefile changes happen on the dev machine or coding
workspace. Changes are committed and pushed to GitHub, then the UM790 pulls from
GitHub.

Do not edit tracked code directly on the UM790. Local runtime files remain
local and untracked.

## Intentionally Deferred

Phase 9 does not add:

- real RSR source DB connection code
- read-only RSR repository/adapter code
- real SQL queries
- `rsr-source-extract` DB-backed check
- multi-agent workflow wiring
- Claude/Anthropic provider support
- cloud provider support
- writes back to ReadySetRentables
