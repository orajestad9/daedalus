# Phase 11: Ollama Review Insight Extraction Agent

Phase 11 adds the first manual local Ollama-powered review insight extraction
agent for the real ReadySetRentables pipeline. The agent will consume
`ReviewInsightExtractionInput` and produce `ReviewInsightExtractionResult`,
written as `review_insights.json`.

This phase starts from the Phase 10 bridge:

```text
real RSR source DB
  -> rsr_source_extract.json
  -> review_insight_extraction_input.json
```

Phase 11 should extend that bridge with an explicit local model step, without
making Ollama automatic and without adding cloud provider behavior.

## Target Flow

```text
rsr_source_extract.json
  -> build-review-insight-input
  -> review_insight_extraction_input.json
  -> local Ollama review insight extraction agent
  -> ReviewInsightExtractionResult
  -> review_insights.json
  -> evaluate review_insights
  -> optionally record artifacts later
```

`review_insight_extraction_input.json` may contain representative review text.
It should remain local and untracked when built from real source data.

## Provider Boundary

Ollama remains local, manual, and explicit in Phase 11. It is not the default
provider, is not wired into LangGraph, and is not wired into `run-workflow`.

Claude/Anthropic is not part of Phase 11. No cloud provider is used, no cloud
SDK is added, and no model call should bypass the existing `ModelClient`
boundary.

## Proposed Agent

The planned agent is:

- `ReviewInsightExtractionAgent`

Responsibilities:

- accept `ReviewInsightExtractionInput`
- load and use prompt identity `readysetrentables_review_insight_extraction`
  version `v0`
- call a `ModelClient` explicitly
- parse model output into `ReviewInsightExtractionResult`
- preserve provider, model, prompt name, and prompt version metadata
- preserve token and cost metadata when the model client provides it
- avoid printing representative review text
- avoid persisting raw prompt text or raw model output text by default

Non-responsibilities:

- source DB extraction
- LangGraph orchestration
- neighborhood profile generation
- Claude calls
- writing back to the ReadySetRentables DB

## Parser Boundary

`parse_review_insight_extraction_result(...)` now exists as a pure parser for
model output text. It expects JSON model output with review insight themes,
strengths, risks, guest expectations, and a raw insight summary. The parser
supports raw JSON, JSON in a fenced code block, or JSON surrounded by short
explanatory text.

The parser does not call Ollama, does not call any `ModelClient`, does not
persist raw model output, and does not print raw prompt or model text. It uses
caller-supplied run, provider, model, prompt, token, and cost metadata rather
than trusting model-provided metadata.

## Agent Boundary

`ReviewInsightExtractionAgent` now exists. It accepts
`ReviewInsightExtractionInput`, builds compact prompt text, calls an injected
`ModelClient`, and parses the returned text into `ReviewInsightExtractionResult`
with `parse_review_insight_extraction_result(...)`.

The agent can be tested with fake model clients and does not instantiate
`OllamaModelClient` directly. It does not wire into LangGraph and does not
connect to any database.

## Manual CLI Plan

The manual command for the local Ollama review insight extraction step is:

```bash
.venv/bin/daedalus extract-review-insights-ollama \
  --input-json artifacts/readysetrentables/review_insight_extraction_input.json \
  --model <ollama-model-name> \
  --output-json artifacts/readysetrentables/review_insights.json
```

This command is implemented as a manual, explicit local-only step. It requires
the operator to choose the Ollama model name and requires local Ollama to be
running. It does not run under `make check`, does not wire Ollama into LangGraph
or `run-workflow`, and does not call Claude/Anthropic.

The command prints only safe metadata such as output path, provider,
model name, prompt identity, theme count, token counts, and estimated cost when
available. It does not print representative review text, raw prompt text, raw
model output text, or artifact contents.

Generated `review_insights.json` may contain AI-derived insights from real
source data. When generated from real ReadySetRentables data, it should remain
local and untracked unless a later guarded workflow explicitly scopes
publication or persistence.

## Evaluation Path

Phase 7 already includes a deterministic `review_insights.json` evaluator shell.
Phase 11 can use that evaluator once a CLI or file path is available for the
generated `review_insights.json` artifact.

No evaluator-model scoring is part of Phase 11. Quality checks should remain
deterministic and structural unless a later phase explicitly scopes an evaluator
model behind the `ModelClient` boundary.

## Safety Rules

- Do not print representative review text.
- Do not print raw prompt text.
- Do not print raw model output text by default.
- Do not print artifact contents.
- Do not commit real `review_insight_extraction_input.json` artifacts.
- Do not commit real `review_insights.json` artifacts.
- Keep local Ollama model selection explicit.
- Keep token and cost metadata when available.
- Do not persist raw sensitive payloads to Postgres.
- Do not write results back to the ReadySetRentables app DB.

## Implementation Sequence

1. Add a deterministic model-output parser for the expected review insight
   extraction response shape. Done.
2. Add `ReviewInsightExtractionAgent` behind the `ModelClient` protocol. Done.
3. Write fake-client tests first, including parser failure paths and metadata
   preservation.
4. Add a manual local Ollama CLI command. Done.
5. Add a file-only local check that uses synthetic input and a fake model path.
6. Add optional DB-backed artifact and invocation recording later.
7. Wire source-derived review insight extraction into LangGraph later.

## Explicitly Deferred

- automatic Ollama execution from `run-workflow`
- LangGraph nodes for review insight extraction
- neighborhood profile generation
- Claude/Anthropic provider support
- cloud provider clients
- writeback to ReadySetRentables
- DB schema changes
- Makefile DB-backed targets for real source data
