# ReadySetRentables Review Theme Summary Agent

This document describes the first AI-assisted Daedalus agent foundation. The
agent exists today behind fake/local paths using `FakeModelClient` only. No
provider SDK, network call, real model call, graph model invocation persistence,
or automatic artifact-record persistence exists yet.

## Purpose

The review theme summary agent will summarize recurring themes from normalized
ReadySetRentables guest review data. Its job is to produce a concise artifact
that helps a human operator quickly understand common positive themes,
improvement themes, and follow-up opportunities.

This is intentionally narrow. It does not make operational decisions, change
review data, contact guests, update listings, or perform autonomous planning.

## Why This Is The First Safe AI-Assisted Feature

Review theme summarization is a good first AI-assisted feature because the
workflow already has deterministic normalized review artifacts, run IDs,
workflow step records, local persistence, prompt versioning, and model
invocation observability. The model can operate on a compact, sanitized view of
review data instead of raw source files or full workflow history.

The first implementation uses `FakeModelClient` in tests and in the
`summarize-review-themes-fake` CLI path so Daedalus can validate agent
boundaries, artifacts, budgets, and invocation recording without provider SDKs,
network calls, real LLM calls, or cloud model usage.

## Current Fake/Local Implementation

Daedalus includes a fake/local standalone CLI path:

- `summarize-review-themes-fake`

This command runs the review theme summary agent with `FakeModelClient`. It does
not call real LLMs, does not install or use provider SDKs, does not read provider
credentials, and does not make network calls.

The command reads an existing normalized reviews JSON artifact, builds compact
deterministic input with `build_review_theme_summary_input(...)`, calls the
agent through the shared `ModelClient` protocol, and writes:

- `review_theme_summary.md`

`review_theme_summary` is now a recognized `ArtifactType` for future
persistence and lineage tracking. The fake/local CLI writes the markdown file;
an explicit companion CLI can record that file as an artifact for an existing
persisted workflow run.

The command prints only safe metadata such as `run_id`, output path, provider,
model name, token counts, and estimated cost. It does not print raw prompt text,
raw model output text, or raw review datasets.

Safe local example:

```sh
make clean

.venv/bin/daedalus normalize-reviews \
  --input sample_data/readysetrentables_reviews/airbnb_reviews_sample.csv \
  --output artifacts/readysetrentables/normalized_reviews.json

.venv/bin/daedalus summarize-review-themes-fake \
  --input artifacts/readysetrentables/normalized_reviews.json \
  --output artifacts/readysetrentables/review_theme_summary.md
```

The standalone summary command is file/artifact-only. It is separate from
`run-workflow`, automatic Postgres persistence, and real provider execution.

The LangGraph workflow now also runs the fake summary path when explicitly
selected:

```sh
.venv/bin/daedalus run-workflow \
  --manifest workflows/readysetrentables_review_normalization.yaml \
  --execution-engine langgraph
```

That graph path writes `review_theme_summary.md` next to the normalized review
artifact. The deterministic `run-workflow` path remains unchanged and does not
create `review_theme_summary.md`.

To verify this path without Docker, Postgres, `.env`, provider SDKs, or real
model calls, run:

```sh
make fake-summary-check
```

The target normalizes the sample reviews, runs `summarize-review-themes-fake`,
verifies `artifacts/readysetrentables/review_theme_summary.md` exists, and then
cleans generated artifacts.

Current implemented pieces include:

- `ReviewThemeSummaryInput`
- `ReviewThemeSummaryTheme`
- `ReviewThemeSummaryResult`
- `build_review_theme_summary_input(...)`
- `ReviewThemeSummaryAgent`
- `write_review_theme_summary_markdown(...)`
- `summarize-review-themes-fake`
- `run-workflow --execution-engine langgraph` fake summary artifact generation
- `record-review-theme-summary-artifact`
- `make fake-summary-check`
- `make graph-fake-summary-check`
- `make fake-summary-db-check` for optional Docker/Postgres verification

## Expected Inputs

The agent should accept structured inputs, not loose prompt text:

- normalized review batch or compact deterministic review summary input
- `run_id`
- optional `step_id`
- `prompt_name`, initially `readysetrentables/review_theme_summary`
- `prompt_version`, initially `v0`
- `ModelBudget`
- input artifact path for the compact model input
- output artifact path for the model-produced summary

The agent should not send raw huge datasets to a model. Deterministic
preprocessing should reduce normalized review data into the smallest faithful
input artifact needed for theme summarization.

## Expected Outputs

The first useful output should be an inspectable artifact, for example:

- `review_theme_summary.md`

A later version may produce structured JSON such as:

- `review_theme_summary.json`

The artifact should be linked to the workflow run through artifact records when
persistence is enabled. The model invocation record should point to the input
and output artifact paths.

## Artifact Persistence

`review_theme_summary.md` is now represented by the recognized artifact type:

- `review_theme_summary`

### Recording The Summary Artifact

Daedalus now has an explicit local CLI path for attaching a generated fake
review theme summary artifact to an existing persisted workflow run:

- `record-review-theme-summary-artifact`

The command records an existing `review_theme_summary.md` file as an
`ArtifactRecord` with `ArtifactType.REVIEW_THEME_SUMMARY`. It does not read or
print the file contents, raw prompt text, raw model output text, or raw review
datasets. After the artifact is recorded, `show-run` can display the
`review_theme_summary` artifact alongside the normal persisted workflow
artifacts.

Safe manual flow:

```sh
.venv/bin/daedalus run-workflow \
  --manifest workflows/readysetrentables_review_normalization.yaml \
  --persist

.venv/bin/daedalus summarize-review-themes-fake \
  --input artifacts/readysetrentables/normalized_reviews.json \
  --output artifacts/readysetrentables/review_theme_summary.md \
  --run-id <run-id>

.venv/bin/daedalus record-review-theme-summary-artifact \
  --run-id <run-id> \
  --path artifacts/readysetrentables/review_theme_summary.md

.venv/bin/daedalus show-run --run-id <run-id>
```

This is currently an explicit/manual artifact-recording CLI path. The LangGraph
workflow can generate `review_theme_summary.md`, but it does not automatically
persist that file as an `ArtifactRecord` yet.

If Docker and a local ignored `.env` are available, the local integration target
can exercise the persisted path:

```sh
make fake-summary-db-check
```

That target creates a persisted workflow run, writes the fake summary markdown,
records the `review_theme_summary` artifact row, and verifies that `show-run`
can display it.

The later automatic persisted flow should be:

1. Run the ReadySetRentables review workflow.
2. Build compact review theme summary input from the normalized review batch.
3. Run `ReviewThemeSummaryAgent` through `ModelClient`.
4. Write `review_theme_summary.md`.
5. Create an `ArtifactRecord` with `ArtifactType.REVIEW_THEME_SUMMARY`.
6. Persist model invocation metadata when a `RecordingModelClient` is used.
7. Inspect the run with `show-run`.

Later `show-run` output should make the full path inspectable:

- normal workflow artifacts
- the `review_theme_summary` artifact path
- model invocation metadata
- provider, model, prompt, version, token, and cost fields

Automatic `ArtifactRecord` persistence and graph model invocation persistence
are not implemented yet. The current commands keep artifact recording explicit
so the boundary remains easy to inspect.

## Prompt Template Usage

The agent should load the committed versioned prompt template:

- `prompts/readysetrentables/review_theme_summary/v0.md`

Prompt identity should be recorded on each model invocation:

- `prompt_name=readysetrentables/review_theme_summary`
- `prompt_version=v0`

Prompt templates must remain generic and reviewable. They must not contain
secrets, API keys, password-bearing DSNs, private hostnames, private customer
data, or machine-specific values.

## ModelClient Usage

The agent must not call provider SDKs directly. It should depend on the shared
`ModelClient` protocol and should be able to run against:

- `FakeModelClient` for tests and local boundary checks
- a future local provider adapter, such as Ollama
- future cloud provider adapters only when explicitly opted in

The first implementation should use `RecordingModelClient` where persistence is
available so successful and failed model calls create `ModelInvocationRecord`
objects.

## Budget Enforcement

Every request should include a `ModelBudget`. The budget should constrain:

- input tokens
- output tokens
- total tokens
- estimated cost
- allowed providers
- cloud model opt-in

Budget validation should happen through the shared model-client path. If a
response exceeds budget, Daedalus should record a failed invocation and surface a
clear error without printing prompt text or output text.

## Model Invocation Recording

Each model invocation should record safe metadata:

- `run_id`
- optional `step_id`
- agent name
- provider
- model name
- prompt name
- prompt version
- token counts
- estimated cost
- status
- timestamps and `duration_ms`
- input artifact path
- output artifact path
- safe error message when applicable

Raw prompt text and raw response text should not be blindly persisted to
Postgres. If retained at all, they should live in artifact-controlled outputs
after an explicit data classification decision.

## Artifact Output Strategy

The agent should write model outputs as artifacts. A markdown artifact is the
best first target because it is easy for humans to inspect and fits the existing
summary-oriented workflow style.

The input to the model should also be artifact-backed when practical. A compact
input artifact makes token use easier to inspect, supports reproducibility, and
keeps `show-run` focused on metadata rather than raw prompt bodies.

## LangGraph Fit

The agent now runs in the LangGraph path after the deterministic run record
artifact step. The current graph shape is:

```text
load_reviews
  -> write_normalized_artifact
  -> write_metadata_artifact
  -> write_summary_artifact
  -> write_run_record_artifact
  -> build_review_theme_summary_input
  -> run_fake_review_theme_summary_agent
  -> write_review_theme_summary_artifact
```

The nodes map to `WorkflowStepRecord` entries and preserve the same `run_id`.
Model invocation persistence and `step_id` attachment for the fake model call
remain future work.

## Intentionally Deferred

- real Ollama adapter
- OpenAI or Anthropic provider adapters
- provider SDK dependencies
- network calls
- cloud model execution
- autonomous planning
- agent-to-agent coordination
- graph model invocation persistence
- automatic `review_theme_summary` artifact-record persistence
- new database migrations
- OpenTelemetry spans
- dashboards or UI

## Related Documents

- [`docs/model-client-architecture.md`](model-client-architecture.md)
- [`docs/token-cost-governance.md`](token-cost-governance.md)
- [`docs/observability.md`](observability.md)
- [`docs/langgraph-orchestration.md`](langgraph-orchestration.md)
