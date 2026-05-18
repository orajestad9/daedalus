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

## First Read-Only Smoke Test

A manual UM790 smoke test successfully extracted a small source snapshot with
`market_name` set to `"san-diego"` and `--max-reviews 10`. The command wrote
`rsr_source_extract.json` and reported `review_count=10`, `listing_count=1`,
and `neighborhood_present=true`.

This confirms the read-only RSR source DB path works at a small scale. Do not
commit or document real review text or private source data. The
`synthetic_fixture_marker` evaluator check is now a fixture-vs-real
classification warning for source extracts without synthetic markers, not a
failed quality check for valid real extracts.

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
