# Phase 8: ReadySetRentables Read-Only Source Extraction Boundary

Phase 8 defines how Daedalus will safely read ReadySetRentables source data from
the real RSR application database without writing to it. The goal is to design
the boundary, source models, artifact shape, and adapter responsibilities before
any real database connection code is written.

The offline scope of Phase 8 is complete: source extraction models, a generic
`rsr_source_extract` artifact type, an artifact writer, a synthetic fixture,
a deterministic evaluator, an `evaluate-rsr-source-extract` CLI command, and
a local `source-extract-check` make target now exist. Real Postgres connection
code, SQL queries, adapters, and DB-backed checks are intentionally deferred.
The work that needs real homelab access is scoped separately from the work that
can happen safely offline.

## Why A Read-Only Boundary

The ReadySetRentables application database is the system of record for live
listings, reviews, neighborhoods, and operational data. Daedalus is an
orchestration and analysis layer, not a source-of-truth application.

Treating RSR as read-only from Daedalus during Phase 8:

- protects production and application data from accidental writes
- makes extracted snapshots reproducible against a point-in-time view
- keeps the workflow testable with fixtures and mocked repositories
- lets a human review extracted artifacts and downstream model outputs before
  any future write-back path is considered
- preserves the existing Daedalus boundary: domain code does not call providers
  directly, and now source code does not write to the RSR app DB

Any future write-back path (such as recording approved profiles back into RSR)
will be a separate phase with its own boundary review.

## Three Distinct Databases And Artifact Stores

Phase 8 keeps three concerns physically and conceptually separate:

| Store | Owner | Role | Daedalus Access |
|---|---|---|---|
| RSR source DB | ReadySetRentables app | live listings, reviews, neighborhoods | read-only |
| Daedalus metadata DB | Daedalus | workflow runs, artifact records, step records, model invocations, evaluation/comparison artifact records | read/write |
| Daedalus artifact directory | Daedalus | extracted source snapshots, `review_insights.json`, `neighborhood_profile.md`/`.json`, evaluation reports | read/write |

Phase 8 does not propose changes to the Daedalus metadata DB schema or
artifact directory. It introduces a new read-only consumer of the RSR source
DB and a new generic artifact type for extracted source snapshots.

## Target Future Pipeline Shape

```text
ReadySetRentables source DB
  -> read-only extraction adapter
  -> sanitized RsrSourceExtractionResult
  -> rsr_source_extract.json artifact
  -> deterministic preprocessing
  -> build review insight extraction input
  -> run local Ollama review insight extraction
  -> write review_insights.json
  -> build neighborhood profile input
  -> run Claude neighborhood profile generation (future)
  -> write neighborhood_profile.md / .json
  -> persist artifact records and model invocation records
  -> run deterministic evaluations
```

Phase 8 implements the sanitized result, the source artifact, a synthetic
fixture, and a deterministic evaluator for the source extract. The read-only
adapter is only proposed at the contract level; real DB extraction is deferred.
Insight extraction, profile generation, and evaluation already exist in Daedalus
as Phase 7 contracts.

## Source Extraction Models

These RSR domain models are implemented in
`src/daedalus/domains/readysetrentables_reviews/source_extraction_models.py`.

- `RsrSourceExtractionRequest` — compact input describing what to extract:
  market name (required), optional neighborhood and property type, optional
  review count cap (`max_reviews > 0` when provided), and flags for whether
  to include listing and neighborhood context.
- `RsrSourceReviewRecord` — sanitized review record: `review_id` and
  `review_text` (required, non-blank), optional `listing_id`, `rating`
  (0–5 when provided), `created_at`, and a `metadata` dict. Excludes guest
  names, contact details, payment data.
- `RsrSourceListingContext` — sanitized listing context: `listing_id`
  (required, non-blank), optional `listing_name`, `property_type`,
  `bedrooms` (≥0), `bathrooms` (≥0), `accommodates` (≥0), `average_rating`
  (0–5 when provided), and a `metadata` dict. Excludes pricing, owner contact
  details, and operator-internal fields.
- `RsrSourceNeighborhoodContext` — sanitized neighborhood context:
  `market_name` and `neighborhood_name` (both required, non-blank), optional
  `city`, `state`, `country` (non-blank when provided), and a `metadata` dict.
- `RsrSourceExtractionResult` — the aggregated sanitized result: the original
  `request`, a timezone-aware `extracted_at_utc`, lists of `reviews` and
  `listings`, an optional `neighborhood`, `source_name` (default
  `"readysetrentables"`), `source_version` (default `"v0"`), and a `metadata`
  dict.

All models follow the validation patterns established in `review_insight_models.py`
and `neighborhood_profile_models.py`: no blank required strings, non-negative
counts, 0–5 float ranges for ratings, no secrets in field values.

## Source Artifact

`ArtifactType.RSR_SOURCE_EXTRACT` (`"rsr_source_extract"`) is now a recognized
generic artifact type in `src/daedalus/orchestrator/artifact_type.py`.

`write_rsr_source_extract_json(...)` is implemented in
`src/daedalus/domains/readysetrentables_reviews/source_extraction_artifacts.py`.
It writes an `RsrSourceExtractionResult` to `rsr_source_extract.json` as
indented UTF-8 JSON using Pydantic serialization. It creates parent directories
and returns the output path.

This is artifact support only. No SQL, DB adapter, CLI command, or workflow
wiring exists yet.

## Synthetic Fixture

`build_sample_rsr_source_extraction_result()` is implemented in
`src/daedalus/domains/readysetrentables_reviews/source_extraction_fixtures.py`.
It returns a deterministic `RsrSourceExtractionResult` with clearly synthetic
data (3 reviews, 2 listings, 1 neighborhood context, market name "Sample Market")
for use in offline tests and future pipeline checks.

- Does not connect to the real RSR database.
- Does not include real review data, real listing names, or private information.
- Can be written with `write_rsr_source_extract_json(...)`.
- Metadata includes `"fixture": "true"` and `"source": "synthetic"` on all records.

## Source Extract Evaluator

`evaluate_rsr_source_extract_json(...)` is implemented in
`src/daedalus/domains/readysetrentables_reviews/source_extraction_evaluator.py`.
It evaluates `rsr_source_extract.json` artifacts deterministically and returns a
generic `EvaluationReport`. Checks cover existence, non-empty content, valid JSON,
schema validity against `RsrSourceExtractionResult`, reviews presence and text,
listing context, neighborhood context, source metadata, and a synthetic fixture
marker check that distinguishes fixture artifacts from future real extractions.

- Does not connect to the real RSR database.
- Does not call any model provider.
- Is not wired into workflows yet.

### Manual CLI

The `evaluate-rsr-source-extract` CLI command writes evaluation report artifacts
for an `rsr_source_extract.json` file:

```sh
.venv/bin/daedalus evaluate-rsr-source-extract \
  --source-extract artifacts/readysetrentables/rsr_source_extract.json \
  --output-json artifacts/readysetrentables/rsr_source_extract.evaluation.json \
  --output-md artifacts/readysetrentables/rsr_source_extract.evaluation.md
```

If neither `--output-json` nor `--output-md` is provided, the command writes a
default JSON report next to the source extract file as
`rsr_source_extract.evaluation.json`. An optional `--run-id <uuid>` is preserved
in the report. The command is deterministic and file-only; it does not connect
to the RSR database, does not call models, and is not wired into workflows yet.

### Local Makefile Check

`make source-extract-check` builds the synthetic fixture, writes
`rsr_source_extract.json`, evaluates it, and writes both JSON and Markdown
evaluation report artifacts under `artifacts/readysetrentables/`. It is
file-only and deterministic.

- Does not require Docker, Postgres, `.env`, Ollama, or network access.
- Does not use real RSR data.
- Is not called by `make check`.

## Proposed Future Adapter

A new read-only repository adapter will live under the RSR domain package:

- `RsrSourceReadOnlyRepository`

Responsibilities:

- run read-only SQL queries against the RSR source DB
- return typed domain models (`RsrSourceReviewRecord`,
  `RsrSourceListingContext`, `RsrSourceNeighborhoodContext`)
- never issue `INSERT`, `UPDATE`, `DELETE`, `CREATE`, `ALTER`, `DROP`,
  `TRUNCATE`, or any other write or DDL statement
- never include raw connection strings, passwords, or DSNs in error messages
  or logs
- never log full review text or sensitive guest data
- accept an injected connection or settings object to keep tests deterministic

The adapter will satisfy a small `RsrSourceRepositoryProtocol`-style interface
so the workflow code can be tested with a fake/in-memory implementation
without requiring a real RSR DB.

Connection settings will be loaded from a separate environment scope
(`DAEDALUS_RSR_SOURCE_*`) distinct from `DAEDALUS_POSTGRES_*` so the Daedalus
metadata DB and the RSR source DB cannot be accidentally mixed.

## Testing Strategy

Phase 8 work will be testable without homelab access:

- unit tests against in-memory or fixture-backed repositories first
- mocked-repository tests for any extraction workflow logic
- `make check` must remain DB-free, Docker-free, Ollama-free, and
  network-free
- an optional `make rsr-source-extract-db-check` may be introduced later,
  guarded by an explicit `.env`, only after homelab access is available;
  this would never be called by `make check`

## Security Rules

- prefer a dedicated read-only DB user for any future real connection
- never commit `.env` files, DSNs, hostnames, or passwords
- never commit real review text or private datasets
- sanitize or minimize extracted data: drop guest names, contact details,
  payment data, and any field not strictly needed downstream
- truncate or excerpt long review bodies rather than copying entire records
- redact PII in any error messages and logs
- do not include request payload contents in error messages
- raw queries, schema names, and table names must not appear in committed
  documentation when they reveal sensitive structure; this Phase 8 design
  document deliberately stays at the model/contract level

## What Is Intentionally Deferred

- real RSR Postgres connection code
- real SQL queries
- real RSR DB schema mapping
- production `.env` configuration for the RSR source DB
- the read-only repository adapter implementation
- a real source extraction CLI command that connects to the RSR DB
- LangGraph and `run-workflow` integration of the extraction step
- DB-backed make checks for source extraction
- any write-back path from Daedalus into the RSR app DB
- the full RSR multi-agent workflow combining extraction, insight extraction,
  and profile generation
