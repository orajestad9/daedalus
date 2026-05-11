# Phase 7: ReadySetRentables Real Pipeline Modeling

Phase 7 models the real ReadySetRentables production pipeline on top of the
existing Daedalus generic infrastructure. The goal is to define domain contracts,
input/result models, artifact types, prompt template placeholders, and evaluator
shells before implementing Claude or wiring the full LangGraph graph.

Phase 7 comes after the evaluation and comparison harness because Daedalus can
now produce, evaluate, and compare model outputs through deterministic local
paths. Adding a real pipeline shape requires defining what outputs look like,
how they are evaluated, and which provider handles which step — before adding
provider SDK dependencies or cloud calls.

## Why Phase 7 Before Claude Integration

Phase 6 left Daedalus with:

- a working fake/local LangGraph review summary path
- a manual Ollama review summary CLI
- generic evaluation and comparison models
- artifact and model invocation persistence

Phase 7 uses those foundations to define the real RSR domain contracts. Defining
contracts first keeps the Claude integration step small and verifiable when it
arrives.

## Platform vs Domain Boundary

Daedalus remains generic throughout Phase 7. The generic platform provides:

- `ModelClient` protocol and `RecordingModelClient`
- `FakeModelClient` and `OllamaModelClient`
- `ModelBudget` and budget enforcement
- `ArtifactRecord` and `ArtifactRepository`
- `ModelInvocationRecord` and `ModelInvocationRepository`
- `EvaluationReport` and `EvaluationComparisonReport`
- generic artifact writers
- LangGraph orchestration wiring patterns

All ReadySetRentables pipeline behavior stays inside the ReadySetRentables domain
modules. Generic orchestrator, model-client, artifact, persistence, and evaluation
infrastructure must not hardcode RSR domain logic.

## Target Pipeline Shape

```text
Input review/listing/neighborhood data
  -> deterministic preprocessing
  -> build review insight extraction input
  -> run local Ollama review insight extraction
  -> write review_insights artifact
  -> build neighborhood profile input
  -> run Claude neighborhood profile generation (future)
  -> write neighborhood_profile.md artifact
  -> write neighborhood_profile.json artifact
  -> persist artifact records
  -> persist model invocation records
  -> run deterministic evaluations (future)
```

Each arrow is a distinct step with its own observable artifact or invocation
record. No step should call a provider directly; all provider calls go through
`ModelClient`.

## What Is Implemented Today

The following Daedalus infrastructure exists and is available to Phase 7:

- `ModelClient` protocol, `FakeModelClient`, `OllamaModelClient`,
  `RecordingModelClient`
- `ModelBudget` and budget enforcement
- `ArtifactRecord`, `ArtifactRepository`, recognized `ArtifactType` values
- `ModelInvocationRecord`, `ModelInvocationRepository`, `ModelInvocationRecorder`
- `EvaluationReport`, `EvaluationComparisonReport`, generic artifact writers
- LangGraph graph state, node, and graph runner patterns
- `run-workflow --persist` and `show-run` for end-to-end inspection
- manual `summarize-review-themes-ollama` as an Ollama CLI precedent
- manual `evaluate-review-theme-summary` as an evaluation CLI precedent

The `review_theme_summary` path is the first real RSR domain agent path and
serves as the reference implementation for Phase 7 domain contracts.

## What Is Implemented In Phase 7

### Review Insight Extraction Domain Models

`ReviewInsightExtractionInput`, `ReviewInsightTheme`, and
`ReviewInsightExtractionResult` are implemented in
`src/daedalus/domains/readysetrentables_reviews/review_insight_models.py`.

These are domain contract models only. No Ollama agent or workflow wiring exists
yet. They stay inside the RSR domain package and do not touch generic Daedalus
platform infrastructure.

### Review Insights Artifact Type And Writer

`ArtifactType.REVIEW_INSIGHTS` (`"review_insights"`) is now a recognized generic
artifact type in `src/daedalus/orchestrator/artifact_type.py`.

`write_review_insights_json(...)` is implemented in
`src/daedalus/domains/readysetrentables_reviews/review_insight_artifacts.py`.
It writes a `ReviewInsightExtractionResult` to `review_insights.json` as
indented UTF-8 JSON using Pydantic serialization. It creates parent directories
and returns the output path.

This is artifact support only. No Ollama agent, Claude agent, prompt template,
CLI command, or workflow wiring exists yet.

### Neighborhood Profile Domain Models

`NeighborhoodProfileInput`, `NeighborhoodProfileSection`, and
`NeighborhoodProfileResult` are implemented in
`src/daedalus/domains/readysetrentables_reviews/neighborhood_profile_models.py`.

`NeighborhoodProfileInput` holds a fully typed `ReviewInsightExtractionResult`
as its `review_insights` field, establishing the contract between the insight
extraction step and the future profile generation step.

These are domain contract models only. No Claude agent or workflow wiring exists
yet. They stay inside the RSR domain package and do not touch generic Daedalus
platform infrastructure.

### Neighborhood Profile Artifact Types And Writers

`ArtifactType.NEIGHBORHOOD_PROFILE_MARKDOWN` (`"neighborhood_profile_markdown"`)
and `ArtifactType.NEIGHBORHOOD_PROFILE_JSON` (`"neighborhood_profile_json"`) are
now recognized generic artifact types in
`src/daedalus/orchestrator/artifact_type.py`.

`write_neighborhood_profile_json(...)` and
`write_neighborhood_profile_markdown(...)` are implemented in
`src/daedalus/domains/readysetrentables_reviews/neighborhood_profile_artifacts.py`.

`write_neighborhood_profile_json` serializes a `NeighborhoodProfileResult` to
indented UTF-8 JSON using Pydantic serialization. `write_neighborhood_profile_markdown`
writes the result's `markdown` field with a small metadata header (run_id,
provider, model_name, prompt identity, market_name, neighborhood_name) prepended
as HTML comments. Both writers create parent directories and return the output path.

This is artifact support only. No Claude agent, prompt template, CLI command,
or workflow wiring exists yet.

### Prompt Template Placeholders

Versioned prompt template placeholder files now exist for both pipeline steps:

- `prompts/readysetrentables/review_insight_extraction/v0.md` — for the future
  local Ollama review insight extraction step; prompt identity is
  `readysetrentables_review_insight_extraction` / `v0`
- `prompts/readysetrentables/neighborhood_profile/v0.md` — for the future Claude
  neighborhood profile generation step; prompt identity is
  `readysetrentables_neighborhood_profile` / `v0`

Both files are placeholders. The prompt bodies describe the intended model task,
input structure, and output contract in plain language. They do not contain
secrets, private datasets, real review text, raw model outputs, or credentials.

Neither template is wired into an agent, `ModelClient`, or workflow yet. Prompt
names and versions are already defined as constants in the domain model files
(`DEFAULT_REVIEW_INSIGHT_PROMPT_NAME`, `DEFAULT_NEIGHBORHOOD_PROFILE_PROMPT_NAME`,
etc.) so `ModelInvocationRecord` can reference stable prompt identity before the
final prompt body is written.

The review insight extraction prompt is intended for local Ollama execution.
The neighborhood profile prompt is intended for a future Claude execution path;
the Claude/Anthropic provider adapter is not yet implemented.

### Deterministic Evaluator Shells

Deterministic evaluators for the new Phase 7 artifact types are implemented in
the RSR domain package:

- `evaluate_review_insights_json(...)` in
  `src/daedalus/domains/readysetrentables_reviews/review_insight_evaluator.py`
  — checks `review_insights.json` for existence, non-empty content, valid JSON,
  schema validity against `ReviewInsightExtractionResult`, themes presence, raw
  insight summary, prompt/model/provider metadata, and usage metadata
- `evaluate_neighborhood_profile_markdown(...)` and
  `evaluate_neighborhood_profile_json(...)` in
  `src/daedalus/domains/readysetrentables_reviews/neighborhood_profile_evaluator.py`
  — check `neighborhood_profile.md` for title, metadata header, summary/intro,
  risks/caveats, and placeholder-only output; check `neighborhood_profile.json`
  for valid JSON, schema validity against `NeighborhoodProfileResult`, sections,
  summary, prompt/model/provider metadata, and usage metadata

All three evaluators return generic `EvaluationReport` objects. They are local
and deterministic. They do not call Ollama, Claude, or any evaluator model.
Missing usage metadata produces a WARNING-severity check, not an ERROR.

These evaluator functions are not wired into `run-workflow`, LangGraph, or any
CLI command yet.

## Remaining Phase 7 Work

The following Phase 7 items are not implemented yet:

### Domain Agents

- `ReviewInsightExtractionAgent` — wraps `ModelClient`, intended for local Ollama
  execution; follows the same pattern as `ReviewThemeSummaryAgent`
- `NeighborhoodProfileAgent` — wraps `ModelClient`, intended for future Claude
  execution; not implemented until the Claude provider adapter exists

### Workflow Wiring

- LangGraph nodes for review insight extraction and neighborhood profile
  generation
- `run-workflow` integration for the full RSR pipeline
- Automatic artifact and model invocation persistence for the new steps
- Optional CLI commands for manual execution and artifact recording, following
  the precedent set by `summarize-review-themes-fake` and
  `summarize-review-themes-ollama`

### Provider Adapter

- Claude/Anthropic provider adapter behind the `ModelClient` boundary, with
  budget enforcement, prompt versioning, and invocation recording

## Proposed Domain Artifacts

| Artifact | ArtifactType | Format | Produced by |
|---|---|---|---|
| `review_insights.json` | `review_insights` | JSON | future `ReviewInsightExtractionAgent` via Ollama |
| `neighborhood_profile.md` | `neighborhood_profile_markdown` | Markdown | future `NeighborhoodProfileAgent` via Claude |
| `neighborhood_profile.json` | `neighborhood_profile_json` | JSON | future `NeighborhoodProfileAgent` via Claude |

Evaluation reports for these artifacts are written using the generic
`evaluation_report` artifact type already defined in Phase 6.

## Provider Roles

| Provider | Role |
|---|---|
| `FakeModelClient` | deterministic testing for all agent paths |
| `OllamaModelClient` | local structured review insight extraction |
| Future Claude adapter | cloud narrative synthesis and neighborhood profile generation |

Ollama handles the structured extraction step because it can run locally, allows
inspection and iteration without cloud costs, and the structured output can be
verified deterministically before the narrative generation step runs.

Claude is deferred until a provider adapter exists behind the `ModelClient`
boundary. Cloud calls must be opt-in, budget-governed, and invocation-recorded.

## Observability Expectations

Every model call in the RSR pipeline must produce a `ModelInvocationRecord` with:

- `run_id`
- `step_id` when inside an observable step
- `agent_name`
- `provider`
- `model_name`
- `prompt_name` and `prompt_version`
- token counts and estimated cost
- status and duration
- input and output artifact paths

Every produced artifact must be tracked as an `ArtifactRecord` in
`workflow_artifacts` when persistence is enabled.

`show-run` should eventually display the full RSR pipeline inspection view:

- all artifact paths and types
- all model invocation records (Ollama insight extraction, future Claude profile)
- evaluation report artifact paths when recorded

Raw prompts and raw model outputs must not be blindly persisted in Postgres.
`model_invocations` stores metadata and artifact paths only.

## Evaluation Expectations

Phase 7 evaluators should be deterministic and structural:

- `review_insights.json` schema validity (required fields, non-empty content)
- `neighborhood_profile.md` required-section checks
- `neighborhood_profile.json` schema validity
- token and cost metadata present when available
- placeholder detection for both insight and profile outputs

Future evaluation can add:

- token and cost threshold checks across providers
- provider/model/prompt version comparison using `EvaluationComparisonReport`
- fake-vs-Ollama insight extraction comparison
- Ollama-vs-Claude profile comparison (after Claude provider exists)

Evaluator-model scoring remains deferred.

## Intentionally Deferred

- Claude/Anthropic provider adapter implementation
- real Claude API calls
- Anthropic SDK dependency
- full RSR LangGraph graph wiring for insight extraction and profile generation
- automatic RSR profile generation in `run-workflow`
- cloud provider usage of any kind
- evaluator-model scoring
- RSR dashboard or OpenTelemetry spans
