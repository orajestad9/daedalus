# Phase 6 Evaluation Harness Design

Phase 6 introduces a generic evaluation harness for Daedalus outputs. The first
concrete example should evaluate ReadySetRentables review theme summary
artifacts, but the platform layer must remain domain-neutral so later domains
can add their own checks without hardcoding ReadySetRentables into the generic
evaluation package.

Evaluation comes after the fake and Ollama model-client paths because Daedalus
can now produce comparable outputs through deterministic workflows,
`FakeModelClient`, and explicit local Ollama runs. Before adding more providers
or richer agent wiring, Daedalus needs a local way to ask: did this artifact
exist, was it structurally useful, which prompt/model/provider produced it, and
did the run stay inside expected token and cost bounds?

## Problems Evaluation Solves

The evaluation harness should help Daedalus:

- verify that expected artifacts were produced
- catch empty or placeholder-only model outputs
- check required headings, sections, metadata, and schema shape
- compare fake and Ollama outputs without requiring cloud providers
- compare local and future cloud-provider outputs after explicit opt-in
- attach evaluation results to runs, artifacts, prompts, models, and providers
- preserve a reviewable history of quality checks alongside workflow artifacts

The first checks should be deterministic and local. They should not call live
Ollama in `make check`, should not call external providers by default, and
should not use another model to judge subjective quality yet.

## Generic Platform Boundary

Generic Daedalus evaluation should define reusable concepts that know nothing
about ReadySetRentables, review summaries, neighborhoods, or any future domain.

Generic infrastructure should include:

- `EvaluationStatus`
- `EvaluationSeverity`
- `EvaluationCheckResult`
- `EvaluationReport`
- evaluation artifact writers
- evaluation CLI and inspection patterns
- optional persistence later

The generic core models now exist in `src/daedalus/evaluation/models.py`, and
generic report artifact writers now exist in
`src/daedalus/evaluation/artifacts.py`. Domain-specific checks, CLI commands,
and persistence remain intentionally deferred.

Generic evaluation code should know how to represent checks, aggregate pass and
failure counts, write reports, and connect reports to artifacts and runs. It
should not know how to score a review theme summary, validate a neighborhood
profile, or interpret a document summary.

## Domain-Specific Boundary

Domain-specific evaluation modules should own the checks that require product or
workflow knowledge. The first domain-specific module can live under the
ReadySetRentables review domain and evaluate `review_theme_summary.md`.

The first ReadySetRentables evaluator now exists as
`evaluate_review_theme_summary_markdown(...)` in
`src/daedalus/domains/readysetrentables_reviews/theme_summary_evaluator.py`. It
returns a generic `EvaluationReport` and keeps all checks deterministic,
local, and provider-free.

Domain-specific evaluation should include:

- ReadySetRentables review theme summary checks
- future ReadySetRentables review insight checks
- future ReadySetRentables neighborhood profile checks
- future Skimmr document summary checks
- any domain-specific scoring rules

This split keeps the platform useful across domains while allowing each domain
to define its own required sections, schemas, thresholds, and quality signals.

## Proposed Generic Models

`EvaluationStatus` should represent the outcome of a check or report:

- `passed`
- `warning`
- `failed`
- `skipped`

`EvaluationSeverity` should describe how important a failed or warning check is:

- `info`
- `warning`
- `error`
- `critical`

`EvaluationCheckResult` should describe one deterministic check:

- check name
- status
- severity
- safe message
- optional artifact path
- optional metadata dictionary

Messages and metadata must not contain raw prompts, raw model output text, raw
review datasets, payload contents, secrets, API keys, or password-bearing DSNs.

`EvaluationReport` should aggregate a set of checks:

- report ID
- run ID when available
- domain
- evaluated artifact path
- evaluated artifact type
- provider, model, prompt name, and prompt version when available
- check results
- summary counts by status and severity
- created timestamp

## Artifact Strategy

Evaluation results should be written as artifacts so humans and future tools can
inspect them. Initial artifact names can be derived from the evaluated artifact:

- `review_theme_summary.evaluation.json`
- `review_theme_summary.evaluation.md`

JSON is useful for machine inspection and future dashboards. Markdown is useful
for human review. `evaluation_report` is now a recognized generic
`ArtifactType`, so future evaluation JSON or Markdown files can be represented
as `ArtifactRecord` rows without introducing domain-specific artifact types.
Automatic evaluation persistence remains intentionally deferred.

Evaluation artifacts should contain check names, statuses, severities, safe
messages, and metadata. They should not contain artifact contents by default.
They should not embed raw prompts, raw model output text, representative review
text, raw datasets, provider payloads, or secrets.

## Relationship To Artifacts

Evaluation should start from artifacts, not in-memory objects hidden inside a
workflow. A report should be able to say which file it evaluated and which run
or model invocation produced that file when the metadata is available.

For ReadySetRentables, the first target is:

- `review_theme_summary.md`

Later targets can include:

- `review_insights.json`
- `neighborhood_profile.md`
- `neighborhood_profile.json`

## Relationship To Model Invocations

Evaluation reports should preserve provider, model, prompt, and version context
when it is available from model invocation records or the evaluated artifact.
That makes it possible to compare:

- fake output vs local Ollama output
- one Ollama model vs another Ollama model
- one prompt version vs another prompt version
- local Ollama output vs future OpenAI or Claude output after explicit opt-in

The harness should not infer sensitive prompt bodies from invocation records.
`model_invocations` intentionally stores metadata and artifact paths, not raw
prompts or raw responses.

## Prompt, Model, And Provider Versions

Every evaluation report should make prompt/model/provider identity visible when
possible:

- provider
- model name
- prompt name
- prompt version
- input and output token counts
- estimated cost

This metadata supports regression checks across prompt versions and provider
changes. It also lets maintainers explain why two artifacts differ without
storing raw prompts or model output text in the evaluation report.

## First ReadySetRentables Checks

The first ReadySetRentables evaluator should check `review_theme_summary.md`
deterministically. Proposed checks:

- artifact exists
- file is non-empty
- contains expected title or section markers
- contains `run_id`
- contains prompt and model metadata
- contains a non-empty summary section
- token and cost metadata are present when available
- output is not obviously placeholder-only

These checks are intentionally structural. They do not claim whether the prose
is subjectively good, complete, or business-ready.

## Future ReadySetRentables Checks

Future checks for a richer ReadySetRentables pipeline can include:

- `review_insights.json` schema validity
- `neighborhood_profile.md` required sections
- `neighborhood_profile.json` schema validity
- token and cost threshold checks
- provider, model, and prompt version comparisons
- comparison of summary coverage across fake, Ollama, and future cloud outputs

Domain-specific thresholds should stay close to the domain module rather than
inside the generic evaluation package.

## ReadySetRentables Review Theme Summary Comparison

A domain-specific comparison evaluator now exists in
`src/daedalus/domains/readysetrentables_reviews/theme_summary_comparison.py`:

- `compare_review_theme_summary_markdown` — compares two
  `review_theme_summary.md` artifacts deterministically and returns a generic
  `EvaluationComparisonReport`

Checks include: artifact existence, non-empty content, title presence, summary
section presence, prompt and model metadata presence, usage section presence,
summary length delta, and placeholder regression detection.

This evaluator is intended for future fake-vs-Ollama, prompt-vs-prompt, or
model-vs-model comparisons. No comparison CLI exists yet. No model, Ollama, or
cloud provider calls are made.

## Generic Comparison Models

Generic comparison report artifact writers now exist in
`src/daedalus/evaluation/artifacts.py`:

- `write_evaluation_comparison_report_json` — writes a machine-readable JSON
  artifact for an `EvaluationComparisonReport`
- `write_evaluation_comparison_report_markdown` — writes an inspectable Markdown
  artifact for an `EvaluationComparisonReport`

These writers support future fake-vs-Ollama, prompt-vs-prompt, model-vs-model, or
run-vs-run comparison artifacts. No comparison CLI exists yet. No persistence
wiring exists yet.

Generic comparison models now exist in `src/daedalus/evaluation/models.py`:

- `EvaluationComparisonStatus` — outcome for one comparison: `match`, `different`,
  `improved`, `regressed`, `inconclusive`
- `EvaluationComparisonItem` — one generic comparison result between a baseline and
  candidate value, with status, severity, message, and optional value fields
- `EvaluationComparisonReport` — aggregated comparison report that can link two
  evaluation report IDs, two artifact paths, a comparator name and version, and a
  list of comparison items

These models are intended for future fake-vs-Ollama, prompt-vs-prompt,
model-vs-model, or run-vs-run comparisons. No comparison CLI exists yet. No
provider or model calls are made by these models. They contain no
ReadySetRentables-specific fields.

## Comparison Strategy

The first comparison mode should be file and metadata based:

- compare fake summary artifacts against Ollama summary artifacts
- compare Ollama outputs from two local model names
- compare prompt version `v0` against a future `v1`
- compare token and estimated-cost metadata between runs

Later, Daedalus can compare Ollama against Claude or OpenAI after cloud
providers are explicitly introduced. Those comparisons should still use the same
generic report shape and should preserve provider/model/prompt metadata.

## Evaluator-Model Checks

Phase 6 should not start by using another model to judge subjective quality.
Evaluator-model checks can be added later, but only behind the same controls as
other model calls:

- `ModelClient`
- `RecordingModelClient`
- `ModelBudget`
- prompt/version tracking
- model invocation records
- local-first provider policy
- explicit cloud-provider opt-in

Evaluator-model outputs should be artifacts, and their invocation metadata
should be recorded like any other model call.

## CLI And Inspection Strategy

The first explicit local evaluation CLI now exists:

```sh
.venv/bin/daedalus evaluate-review-theme-summary \
  --summary artifacts/readysetrentables/review_theme_summary.md \
  --output-json artifacts/readysetrentables/review_theme_summary.evaluation.json \
  --output-md artifacts/readysetrentables/review_theme_summary.evaluation.md
```

If no output path is provided, the command writes JSON next to the summary as
`review_theme_summary.evaluation.json`. Failed checks are evaluation results,
not CLI execution failures, so the command still exits successfully when it can
write the report. The command prints only target identity, pass/fail counts, and
written report paths; it does not print artifact contents, raw prompt text, raw
model output text, raw datasets, or provider payloads.

The file-only local check can be run with:

```sh
make evaluation-check
```

That target runs the LangGraph fake summary path, evaluates
`review_theme_summary.md`, verifies the JSON and Markdown evaluation artifacts
exist, and cleans generated artifacts. It does not require Docker, `.env`,
Ollama, provider SDKs, or network access.

An existing persisted workflow run can manually attach an evaluation report
artifact with:

```sh
.venv/bin/daedalus record-evaluation-report-artifact \
  --run-id <run-id> \
  --path artifacts/readysetrentables/review_theme_summary.evaluation.json
```

The command records the file as `ArtifactType.EVALUATION_REPORT` so `show-run`
can display the artifact path. It is explicit/manual and does not wire
evaluation into workflows, LangGraph, or automatic persistence.

The `evaluation-db-check` Makefile target verifies the full manual persisted
evaluation path end-to-end: it runs the LangGraph workflow with `--persist`,
evaluates `review_theme_summary.md`, records the evaluation JSON as an
`ArtifactType.EVALUATION_REPORT`, and confirms `show-run` includes
`evaluation_report`. It is optional, may require Docker, Postgres, and `.env`,
and does not require Ollama. It is not called by `make check`.

The broader generic command shape can come later. The important boundary is that
evaluation is opt-in, deterministic by default, and artifact oriented.

`show-run` could later display evaluation artifacts or summary counts, such as:

- evaluation reports attached to the run
- number of passed, warning, failed, and skipped checks
- highest severity found
- paths to evaluation JSON or markdown artifacts

Persistence should be optional at first. The initial implementation can write
local evaluation artifacts without adding migrations.

## Security Rules

Evaluation code must follow the same safety rules as model-client and workflow
code:

- do not print or persist raw prompts unnecessarily
- do not print or persist raw model output text unnecessarily
- do not print or persist raw sensitive datasets
- do not store representative review text in evaluation metadata by default
- do not include provider request payload contents
- do not put secrets in evaluation artifacts
- do not document real `.env` values or password-bearing DSNs
- do not require live Ollama, cloud providers, or network calls in `make check`

Evaluation reports should be safe to share as metadata-oriented artifacts unless
a domain-specific evaluator explicitly documents otherwise.

## Intentionally Deferred

- implementation of evaluation models
- evaluation CLI commands
- evaluation persistence and migrations
- `show-run` evaluation display
- workflow or LangGraph evaluation wiring
- live Ollama evaluation checks in `make check`
- cloud-provider comparisons
- evaluator-model scoring
- dashboards or OpenTelemetry
