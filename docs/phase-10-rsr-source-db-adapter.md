# Phase 10: ReadySetRentables Source DB Adapter

Phase 10 will implement a safe read-only adapter from the real
ReadySetRentables source Postgres database into Daedalus source extraction
models. This design step documents the intended boundary before any DB settings,
connection helpers, SQL, repositories, CLI commands, Makefile targets, or
workflow wiring are added.

Phase 10 starts after Phase 9 verified that the UM790 can run Daedalus metadata
Postgres successfully. That verification does not validate the real
ReadySetRentables source database.

## Stores And Boundaries

Daedalus must keep three stores separate:

| Store | Role | Access |
|---|---|---|
| ReadySetRentables source DB | real application/source data | read-only from Daedalus; no schema changes; no writes |
| Daedalus metadata DB | workflow runs, workflow steps, artifact records, model invocation records, evaluation/comparison artifact records | Daedalus read/write metadata only |
| Daedalus artifact directory | `rsr_source_extract.json`, `review_insights.json`, `neighborhood_profile.md`/`.json`, evaluation reports, comparison reports | local artifact files |

The RSR source DB remains the application system of record. Daedalus should
extract sanitized snapshots into artifacts first, then evaluate and inspect those
artifacts before any downstream model or workflow expansion.

## Target Future Flow

```text
ReadySetRentables source DB
  -> RsrSourceReadOnlyRepository
  -> RsrSourceExtractionResult
  -> rsr_source_extract.json
  -> evaluate-rsr-source-extract
  -> future review insight extraction input
  -> future review_insights.json
```

Phase 8 already provides the source extraction models, artifact writer,
synthetic fixture, deterministic evaluator, `evaluate-rsr-source-extract` CLI,
and file-only `source-extract-check`. Phase 10 should connect the real source DB
to those existing domain models without changing generic Daedalus infrastructure
or adding model-provider calls.

## Proposed Adapter

The future adapter should be named:

- `RsrSourceReadOnlyRepository`

Responsibilities:

- accept an `RsrSourceExtractionRequest`
- execute read-only queries
- return an `RsrSourceExtractionResult`
- map raw DB rows into sanitized domain models:
  `RsrSourceReviewRecord`, `RsrSourceListingContext`, and
  `RsrSourceNeighborhoodContext`
- avoid writes, deletes, updates, schema changes, temp table mutations, and
  migrations
- avoid logging secrets, DSNs, raw private data, or full review dumps
- expose clear safe errors without connection strings or passwords

The adapter belongs under the ReadySetRentables domain package. Generic
orchestrator, artifact, persistence, model-client, and evaluation
infrastructure should remain generic.

## Settings Boundary

`RsrSourcePostgresSettings` now defines the future RSR source DB settings shape,
and `load_rsr_source_postgres_settings(...)` reads required
`RSR_SOURCE_POSTGRES_*` variables without connecting to a database. These
settings are separate from the Daedalus metadata DB `POSTGRES_*` settings.

- `RSR_SOURCE_POSTGRES_HOST`
- `RSR_SOURCE_POSTGRES_PORT`
- `RSR_SOURCE_POSTGRES_DB`
- `RSR_SOURCE_POSTGRES_USER`
- `RSR_SOURCE_POSTGRES_PASSWORD`

Rules:

- real values belong only in local untracked `.env`
- prefer a dedicated read-only database user
- do not commit RSR source DB credentials
- do not reuse Daedalus metadata DB settings for the RSR source DB

## Connection Boundary

`connect_rsr_source_postgres(...)` now exists as the RSR source DB connection
helper. It is separate from the Daedalus metadata DB connection helper, accepts
`RsrSourcePostgresSettings`, passes keyword arguments instead of a
password-bearing DSN, and supports injected connection callables in tests.

The helper does not run SQL, verify schema, mutate the RSR database, print
connection details, or expose the raw password in failure messages. Repository
and query implementation is still deferred.

## Mapper Boundary

Source DB mapper helpers now exist for converting already-fetched row
dictionaries into RSR source extraction domain models. They map review rows,
listing rows, neighborhood rows, and complete row groups into
`RsrSourceExtractionResult`.

The mappers do not contain SQL, connect to the real RSR database, print row
contents, or implement repository/query behavior. Repository and query
implementation is still deferred.

## Repository Boundary

`RsrSourceReadOnlyRepository.extract_source_data(...)` now has a first
read-only implementation. It accepts an injected connection, does not open
connections itself, does not own credentials or settings, and maps
`public.reviews`, `public.listings`, `public.neighborhoods`, and
`public.markets` into `RsrSourceExtractionResult`.

The repository uses parameterized `SELECT` queries and applies the
`ensure_read_only_query(...)` guardrail before execution. The guardrail allows
apparent `SELECT`/`WITH` queries and rejects obvious write or schema mutation
keywords. This guardrail is not a full SQL parser or a security boundary.

The first query implementation excludes `reviews.reviewer_name` and sensitive
listing fields such as listing URLs, latitude/longitude, price, revenue, and
occupancy from mapped metadata. Unit coverage uses fake connections and fake
cursors only; it does not connect to the real RSR source database.

## Manual Source Extraction CLI

`extract-rsr-source-data` now exists as a manual, explicit command for writing a
sanitized RSR source snapshot:

```bash
.venv/bin/daedalus extract-rsr-source-data \
  --market-name "Example Market" \
  --neighborhood-name "Example Neighborhood" \
  --max-reviews 25 \
  --output-json artifacts/readysetrentables/rsr_source_extract.json
```

The command uses `RSR_SOURCE_POSTGRES_*` settings, not the Daedalus metadata DB
`POSTGRES_*` settings. It connects to the RSR source DB through the read-only
repository, writes `rsr_source_extract.json`, and prints only a short count
summary. It does not persist anything to the Daedalus metadata DB yet.

This command is not called by `make check`. No Makefile DB-backed source
extraction target exists yet.

## Verified UM790 Smoke Test

A manual UM790 smoke test successfully extracted a small real source snapshot:

```bash
.venv/bin/daedalus extract-rsr-source-data \
  --market-name "san-diego" \
  --max-reviews 10 \
  --output-json artifacts/readysetrentables/rsr_source_extract.json
```

The safe CLI summary reported:

- `review_count=10`
- `listing_count=1`
- `neighborhood_present=true`

The source extract was evaluated with:

```bash
.venv/bin/daedalus evaluate-rsr-source-extract \
  --source-extract artifacts/readysetrentables/rsr_source_extract.json \
  --output-json artifacts/readysetrentables/rsr_source_extract.evaluation.json \
  --output-md artifacts/readysetrentables/rsr_source_extract.evaluation.md
```

The existing `rsr_source_extract.json` file was then manually recorded against a
persisted Daedalus workflow run with:

```bash
.venv/bin/daedalus record-rsr-source-extract-artifact \
  --run-id <run-id> \
  --path artifacts/readysetrentables/rsr_source_extract.json
```

`show-run` displayed the recorded artifact as:

```text
rsr_source_extract: artifacts/readysetrentables/rsr_source_extract.json
```

This confirms the read-only RSR source DB path works at a small scale. Do not
commit or document real review text or private source data. The
`synthetic_fixture_marker` evaluator check is now a fixture-vs-real
classification warning for source extracts without synthetic markers, not a
failed quality check for valid real extracts.

The verified smoke path proves:

- `RSR_SOURCE_POSTGRES_*` settings load correctly from local untracked env.
- the RSR source DB connection works.
- the read-only repository query works at small scale.
- source DB rows map into `RsrSourceExtractionResult`.
- `rsr_source_extract.json` writing works with real data.
- the deterministic evaluator works with real-style extracts.
- `ArtifactRecord` persistence works for `rsr_source_extract`.
- `show-run` can inspect the recorded source extract artifact.

Current boundaries remain:

- extraction is still manual.
- recording is still manual.
- source extraction is not wired into LangGraph.
- source extraction is not wired into `run-workflow`.
- no model calls are made.
- no writeback to the RSR app DB exists.
- no Claude/Anthropic provider exists.
- no automatic downstream review insight extraction exists yet.

## Manual Artifact Recording CLI

An existing source extract file can be recorded against an existing workflow run
with:

```bash
.venv/bin/daedalus record-rsr-source-extract-artifact \
  --run-id <run-id> \
  --path artifacts/readysetrentables/rsr_source_extract.json
```

This command is manual. It records the existing file as
`ArtifactType.RSR_SOURCE_EXTRACT` in the Daedalus metadata DB. It uses the
Daedalus metadata DB connection, not the RSR source DB connection, and it does
not extract data or print source extract contents. After recording, `show-run`
can display the artifact with the rest of the workflow run metadata.

## Future Guarded DB Check Plan

A future optional Makefile target could verify the manual source bridge flow:

- run a persisted workflow.
- extract RSR source data.
- evaluate the source extract.
- record the `rsr_source_extract` artifact.
- use `show-run` to verify the recorded `rsr_source_extract` artifact.

That future target is intentionally not added yet. If added, it must be
optional, excluded from `make check`, require local `RSR_SOURCE_POSTGRES_*`
settings, avoid printing review text or artifact contents, use a small
`max_reviews` value, and remain safe for UM790/homelab-only operation.

## Review Insight Input Builder

`ReviewInsightExtractionInput` can now be built from an
`RsrSourceExtractionResult`. This bridges `rsr_source_extract.json` data from
the read-only source DB path into the compact input shape expected by a future
local Ollama review insight extraction agent.

The builder is pure transformation logic. It does not call Ollama or any
`ModelClient`, does not connect to a database, does not add CLI or LangGraph
wiring, and does not print review text or artifact contents.

## Schema Discovery Plan

Before writing adapter SQL, inspect the real RSR DB schema using read-only
metadata queries. Capture only schema-level notes needed to design safe
extraction. Do not commit private hostnames, DSNs, credentials, private data, or
raw review contents.

Discovery categories:

- candidate review tables
- candidate listing tables
- candidate neighborhood/location tables
- useful columns for review text, rating, listing ID, market, neighborhood,
  bedrooms, bathrooms, accommodates, and average rating
- row counts and sample-safe metadata only

Do not commit real table names unless they are safe to document and already
approved for committed docs. Do not add real extraction SQL until the schema
discovery results are reviewed.

## Test Strategy

- unit tests use fake rows and fake repository fixtures
- repository query tests use fake connections/cursors and capture SQL without
  touching a real database
- `make check` remains DB-free, Docker-free, Ollama-free, and network-free
- `source-extract-check` remains file-only
- any future DB-backed source extraction check is optional and guarded by local
  untracked `.env`
- any future DB-backed source extraction check is not called by `make check`

The first implementation should prove mapping and sanitization with fake data
before connecting to the real RSR source DB.

## Safety Rules

- prefer a dedicated read-only DB user
- perform no writes to the RSR source DB
- commit no real data
- include no raw review dumps in tests
- include no private IPs, hostnames, passwords, DSNs, or `.env` values in docs
- sanitize and minimize extracted fields
- produce artifacts first
- do not write generated results back to RSR in Phase 10

## Intentionally Deferred

This design step does not add:

- `rsr-source-extract-db-check`
- workflow or LangGraph wiring
- review insight agent
- Claude/Anthropic provider
- writing generated profiles back to RSR
