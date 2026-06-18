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

Manual UM790 testing confirmed that `ollama-smoke-check` can reach local Ollama
with `qwen2.5-coder:7b`. Review insight extraction has a stricter requirement
than the smoke check: the model must return a valid JSON object matching the
review insight schema.

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

Parser failures are categorized with safe diagnostics, such as empty output,
missing JSON object, invalid JSON, or schema mismatch. These diagnostics do not
include raw model output, parsed payload contents, prompt text, or review text.

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
  --output-json artifacts/readysetrentables/review_insights.json \
  --ollama-timeout-seconds 240
```

This command is implemented as a manual, explicit local-only step. It requires
the operator to choose the Ollama model name and requires local Ollama to be
running. It does not run under `make check`, does not wire Ollama into LangGraph
or `run-workflow`, and does not call Claude/Anthropic.

`--ollama-timeout-seconds` is optional. When omitted, the command preserves the
existing `OllamaModelClientSettings` timeout behavior, including the default or
`DAEDALUS_OLLAMA_TIMEOUT_SECONDS` environment value. When provided, it must be a
positive integer and is passed into the local Ollama client request timeout.

The command prints only safe metadata such as output path, provider,
model name, prompt identity, theme count, token counts, and estimated cost when
available. It does not print representative review text, raw prompt text, raw
model output text, or artifact contents.

When a persisted workflow run already exists, the same manual extraction command
can also record safe local Ollama invocation metadata after
`review_insights.json` is written:

```bash
.venv/bin/daedalus extract-review-insights-ollama \
  --input-json artifacts/readysetrentables/review_insight_extraction_input.json \
  --model <ollama-model-name> \
  --output-json artifacts/readysetrentables/review_insights.json \
  --run-id <workflow-run-uuid> \
  --record-model-invocation
```

`--record-model-invocation` requires `--run-id`. The persisted record uses
`agent_name=review_insight_extraction_agent`,
`prompt_name=readysetrentables_review_insight_extraction`, and
`prompt_version=v0`, plus the provider, model, token, and cost metadata from the
successful local Ollama result. `show-run` can then display the local Ollama
model invocation metadata alongside the run artifacts.

Generated `review_insights.json` artifacts can be evaluated with deterministic
local checks:

```bash
.venv/bin/daedalus evaluate-review-insights \
  --review-insights artifacts/readysetrentables/review_insights.json \
  --output-json artifacts/readysetrentables/review_insights.evaluation.json \
  --output-md artifacts/readysetrentables/review_insights.evaluation.md
```

The command writes JSON and Markdown evaluation reports and prints only safe
aggregate metadata such as pass/fail counts and output paths. It does not print
themes, strengths, risks, guest expectations, raw insight summaries,
representative review text, prompt text, or raw model output.

When extraction fails, the command reports a safe diagnostic category instead of
a single generic error. Known categories include: the Ollama request timed out,
the local Ollama request failed, the model output was empty, the model output
did not contain a valid JSON object, the model output JSON could not be parsed,
and the model output did not match the expected review insight JSON schema. An
unrecognized failure falls back to a generic safe category. These diagnostics
intentionally avoid prompt text, representative review text, parsed payload
contents, and raw model output, so none of those can leak through the CLI error.

Generated `review_insights.json` may contain AI-derived insights from real
source data. When generated from real ReadySetRentables data, it should remain
local and untracked unless a later guarded workflow explicitly scopes
publication or persistence.

The generated artifact can now be attached to an existing persisted Daedalus
workflow run without reading or printing the artifact contents:

```bash
.venv/bin/daedalus record-review-insights-artifact \
  --run-id <workflow-run-uuid> \
  --path artifacts/readysetrentables/review_insights.json
```

This records the artifact as `review_insights`, so `show-run` displays a line
like `review_insights: artifacts/readysetrentables/review_insights.json`.

## Repeatable Pipeline Command

The current manual demo path can also be run as one explicit command:

```bash
.venv/bin/daedalus run-rsr-review-insights-pipeline \
  --run-id <workflow-run-uuid> \
  --market-name san-diego \
  --max-reviews 10 \
  --model qwen2.5-coder:7b \
  --output-dir artifacts/readysetrentables \
  --ollama-timeout-seconds 240
```

The command creates `--output-dir` when needed and writes:

- `rsr_source_extract.json`
- `review_insight_extraction_input.json`
- `review_insights.json`
- `review_insights.evaluation.json`
- `review_insights.evaluation.md`

It then records `review_insights` for `review_insights.json`, records
`evaluation_report` for `review_insights.evaluation.json`, and records the
local Ollama model invocation against `--run-id`. The Markdown evaluation report
is written as the local human-readable companion report.

`--ollama-timeout-seconds` is optional here as well. When omitted, the pipeline
uses the same Ollama timeout settings path as the standalone extraction command.
When provided, the positive integer is forwarded to the local Ollama client only;
it does not change source extraction, prompt construction, evaluation, or
persistence behavior.

The pipeline keeps the same boundaries as the individual commands: RSR source
DB access is read-only, there is no ReadySetRentables DB writeback, there is no
LangGraph wiring, and there are no Claude/Anthropic/cloud provider calls.

Progress and final CLI output are safe summaries only. They may include paths,
run ID, model name, token counts, and aggregate evaluation counts. They must not
include review text, generated insight contents, prompt text, raw model output,
DSNs, passwords, `.env` values, or artifact contents.

## Evaluation Path

`review_insights.json` now has a deterministic evaluator and manual CLI command.
It validates the artifact against `ReviewInsightExtractionResult`, checks
provider/model/prompt lineage, theme shape, allowed sentiment values, evidence
counts, strengths, risks, guest expectations, raw insight summary presence,
available token/cost metadata, and obvious placeholder text.

No evaluator-model scoring is part of Phase 11. Quality checks should remain
deterministic and structural unless a later phase explicitly scopes an evaluator
model behind the `ModelClient` boundary.

## Safety Rules

- Do not print representative review text.
- Do not print raw prompt text.
- Do not print raw model output text by default.
- Require strict JSON-only model output for review insight extraction.
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
6. Add optional DB-backed artifact recording for `review_insights.json`. Done.
7. Add deterministic `review_insights.json` evaluation. Done.
8. Wire source-derived review insight extraction into LangGraph later.

## Explicitly Deferred

- automatic Ollama execution from `run-workflow`
- LangGraph nodes for review insight extraction
- neighborhood profile generation
- Claude/Anthropic provider support
- cloud provider clients
- writeback to ReadySetRentables
- DB schema changes
- Makefile DB-backed targets for real source data
