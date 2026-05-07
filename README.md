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
