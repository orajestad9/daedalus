# daedalus
Daedalus is a local-first Python multi-agent orchestration platform for building
observable, human-approved AI pipelines. The first workflow automates
ReadySetRentables review processing from Airbnb CSV data into deterministic JSON
artifacts. Postgres persistence is intentionally deferred to a later phase.

## Development Commands

Install local development dependencies:

```sh
make install
```

Run the full local check suite:

```sh
make check
```

GitHub Actions runs the same `make check` quality gate on pushes and pull
requests targeting `main`.

Normalize the committed sample Airbnb review CSV into a JSON artifact:

```sh
make normalize-sample
```

The sample run writes four ignored local artifacts under
`artifacts/readysetrentables/`:

- `normalized_reviews.json`
- `normalized_reviews.metadata.json`
- `normalized_reviews.summary.md`
- `normalized_reviews.run.json`

## Workflow Manifests

Workflows can be described by YAML manifests under `workflows/`. The sample
ReadySetRentables manifest defines the workflow name, domain, input CSV path,
output JSON path, and whether human approval is required.

## Local Postgres

Phase 1 starts with a Docker Compose Postgres service for local development.
No real secrets are committed. To run it locally:

```sh
cp .env.example .env
```

Edit `.env` and replace every `change_me_*` placeholder with local-only values.
Never commit `.env`, real passwords, connection strings, hostnames, tokens, or
machine-specific values.

Start Postgres:

```sh
make db-up
```

Apply committed SQL migrations:

```sh
make migrate-db
```

Inspect logs if needed:

```sh
make db-logs
```

Stop the service:

```sh
make db-down
```

To delete the local database volume, run the destructive reset target:

```sh
make db-reset
```

`make migrate-db` loads local settings from `.env`. If `.env` is missing, copy
`.env.example` to `.env` and edit the values locally first. `.env` must never be
committed.
