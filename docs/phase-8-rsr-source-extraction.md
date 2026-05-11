# Phase 8: ReadySetRentables Read-Only Source Extraction Boundary

Phase 8 defines how Daedalus will safely read ReadySetRentables source data from
the real RSR application database without writing to it. The goal is to design
the boundary, source models, artifact shape, and adapter responsibilities before
any real database connection code is written.

This phase is documentation-first. Real Postgres connection code, SQL queries,
adapters, and DB-backed checks are intentionally deferred. The work that needs
real homelab access is scoped separately from the work that can happen safely
offline.

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

Phase 8 only defines the first three steps: the adapter, the sanitized result,
and the source artifact. Insight extraction, profile generation, and evaluation
already exist in Daedalus as Phase 7 contracts.

## Proposed Future Source Extraction Models

These RSR domain models will live under
`src/daedalus/domains/readysetrentables_reviews/` when implemented. They are
not implemented yet.

- `RsrSourceExtractionRequest` — compact input describing what to extract:
  market, neighborhood, property identifier, optional date range, and an
  optional review count cap. Includes `run_id` for lineage.
- `RsrSourceReviewRecord` — sanitized review record: rating, rating categories,
  short excerpt or truncated comment, language, sanitized timestamp. Excludes
  guest names, contact details, payment data, and any field not needed for
  insight extraction.
- `RsrSourceListingContext` — sanitized listing context: market, neighborhood,
  property type, capacity, and a small set of public listing attributes
  relevant to neighborhood profile generation. Excludes pricing, owner contact
  details, financial data, and operator-internal fields.
- `RsrSourceNeighborhoodContext` — sanitized neighborhood context: name,
  optional market, and a small set of public neighborhood attributes. Excludes
  any private operator data.
- `RsrSourceExtractionResult` — the aggregated typed result containing the
  request, listing context, neighborhood context, and the bounded list of
  review records. Includes `run_id`, source identity (`source_name`,
  `source_version`), and a sanitized extraction timestamp.

These models should follow the validation patterns already established in
`review_insight_models.py` and `neighborhood_profile_models.py`: no blank
required strings, non-negative counts, no secrets in details.

## Proposed Future Source Artifact

A new generic artifact type will be added when the source models are
implemented:

- `ArtifactType.RSR_SOURCE_EXTRACT` — for `rsr_source_extract.json`

The artifact will be written by a new RSR domain writer (for example,
`write_rsr_source_extract_json(...)`). The artifact format will use Pydantic
JSON serialization, indented for readability, matching the patterns in
`review_insight_artifacts.py` and `neighborhood_profile_artifacts.py`.

Phase 8 does not add the `ArtifactType` value or the writer yet. They are
mentioned here so the boundary is clear when the implementation step begins.

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
- the `ArtifactType.RSR_SOURCE_EXTRACT` enum value
- the source artifact writer
- the read-only repository adapter implementation
- the source extraction CLI command
- LangGraph and `run-workflow` integration of the extraction step
- DB-backed make checks for source extraction
- any write-back path from Daedalus into the RSR app DB
- the full RSR multi-agent workflow combining extraction, insight extraction,
  and profile generation
