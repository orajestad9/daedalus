# daedalus
Daedalus is a local-first Python multi-agent orchestration platform for building observable, human-approved AI pipelines. The first workflow automates ReadySetRentables review processing from Airbnb CSV data into validated JSON insights persisted to Postgres.

## Development Commands

Install local development dependencies:

```sh
make install
```

Run the full local check suite:

```sh
make check
```

Normalize the committed sample Airbnb review CSV into a JSON artifact:

```sh
make normalize-sample
```

## Workflow Manifests

Workflows can be described by YAML manifests under `workflows/`. The sample
ReadySetRentables manifest defines the workflow name, domain, input CSV path,
output JSON path, and whether human approval is required.
