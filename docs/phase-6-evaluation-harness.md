# Phase 6 Evaluation Harness

Phase 6 introduces a generic evaluation harness for Daedalus outputs. The first
concrete example evaluates ReadySetRentables review theme summary artifacts, but
the platform layer remains domain-neutral so later domains can add their own
checks without hardcoding ReadySetRentables into the generic evaluation package.

Evaluation comes after the fake and Ollama model-client paths because Daedalus
can now produce comparable outputs through deterministic workflows,
`FakeModelClient`, and explicit local Ollama runs. Before adding more providers
or richer agent wiring, Daedalus needs a local way to ask: did this artifact
exist, was it structurally useful, which prompt/model/provider produced it, and
did the run stay inside expected token and cost bounds?

## What Is Implemented

The following Phase 6 capabilities are implemented and verified by `make check`:

**Generic evaluation models** (`src/daedalus/evaluation/models.py`):

- `EvaluationStatus` — `passed`, `warning`, `failed`, `skipped`
- `EvaluationSeverity` — `info`, `warning`, `error`
- `EvaluationCheckResult` — one deterministic check result
- `EvaluationReport` — aggregated report with counts, metadata, and timestamps
- `EvaluationComparisonStatus` — `match`, `different`, `improved`, `regressed`,
  `inconclusive`
- `EvaluationComparisonItem` — one comparison result between baseline and
  candidate values
- `EvaluationComparisonReport` — aggregated comparison report linking two
  artifact paths, two evaluation report IDs, comparator identity, and comparison
  items

**Generic artifact writers** (`src/daedalus/evaluation/artifacts.py`):

- `write_evaluation_report_json` — machine-readable JSON for an
  `EvaluationReport`
- `write_evaluation_report_markdown` — human-readable Markdown for an
  `EvaluationReport`
- `write_evaluation_comparison_report_json` — machine-readable JSON for an
  `EvaluationComparisonReport`
- `write_evaluation_comparison_report_markdown` — human-readable Markdown for
  an `EvaluationComparisonReport`

**Generic artifact types** (`src/daedalus/orchestrator/artifact_type.py`):

- `ArtifactType.EVALUATION_REPORT` — for evaluation JSON or Markdown files
- `ArtifactType.EVALUATION_COMPARISON_REPORT` — for comparison JSON or Markdown
  files, distinct from `EVALUATION_REPORT`

**ReadySetRentables domain evaluator**
(`src/daedalus/domains/readysetrentables_reviews/theme_summary_evaluator.py`):

- `evaluate_review_theme_summary_markdown(...)` — deterministic checks on a
  `review_theme_summary.md` artifact; returns a generic `EvaluationReport`; no
  model calls

**ReadySetRentables domain comparison evaluator**
(`src/daedalus/domains/readysetrentables_reviews/theme_summary_comparison.py`):

- `compare_review_theme_summary_markdown(...)` — deterministic comparison of
  two `review_theme_summary.md` artifacts; returns a generic
  `EvaluationComparisonReport`; no model calls

**CLI commands**:

- `evaluate-review-theme-summary` — evaluates a summary artifact and writes
  evaluation report JSON and/or Markdown
- `compare-review-theme-summaries` — compares two summary artifacts and writes
  comparison report JSON and/or Markdown
- `record-evaluation-report-artifact` — records an existing evaluation report
  file as `ArtifactType.EVALUATION_REPORT` for a persisted workflow run
- `record-evaluation-comparison-report-artifact` — records an existing
  comparison report file as `ArtifactType.EVALUATION_COMPARISON_REPORT` for a
  persisted workflow run

**Makefile targets**:

- `make evaluation-check` — file-only; no Docker, `.env`, Ollama, or network
  access required; not called by `make check`
- `make comparison-check` — file-only; no Docker, `.env`, Ollama, or network
  access required; not called by `make check`
- `make evaluation-db-check` — optional; may require Docker, Postgres, and
  `.env`; does not require Ollama; not called by `make check`
- `make comparison-db-check` — optional; may require Docker, Postgres, and
  `.env`; does not require Ollama; not called by `make check`

## What Is Not Implemented Yet

- automatic evaluation wiring into `run-workflow` or LangGraph
- automatic comparison wiring into `run-workflow` or LangGraph
- automatic evaluation artifact persistence
- evaluator-model scoring (using a model to judge subjective quality)
- `show-run` evaluation summary display
- live Ollama evaluation or comparison in `make check`
- cloud-provider comparisons
- evaluation persistence migrations
- future RSR review insight or neighborhood profile evaluators
- future Skimmr document summary evaluators
- dashboards or OpenTelemetry

## Problems Evaluation Solves

The evaluation harness helps Daedalus:

- verify that expected artifacts were produced
- catch empty or placeholder-only model outputs
- check required headings, sections, metadata, and schema shape
- compare fake and Ollama outputs without requiring cloud providers
- compare local and future cloud-provider outputs after explicit opt-in
- attach evaluation results to runs, artifacts, prompts, models, and providers
- preserve a reviewable history of quality checks alongside workflow artifacts

Checks are deterministic and local. They do not call live Ollama in `make check`,
do not call external providers by default, and do not use another model to judge
subjective quality.

## Generic Platform Boundary

Generic Daedalus evaluation defines reusable concepts that know nothing about
ReadySetRentables, review summaries, neighborhoods, or any future domain. Generic
evaluation code knows how to represent checks, aggregate pass and failure counts,
write reports, and connect reports to artifacts and runs. It does not know how to
score a review theme summary, validate a neighborhood profile, or interpret a
document summary.

## Domain-Specific Boundary

Domain-specific evaluation modules own the checks that require product or
workflow knowledge. The first domain-specific evaluator lives under the
ReadySetRentables review domain. The first domain-specific comparison evaluator
lives there too.

Domain-specific evaluation can later include:

- future ReadySetRentables review insight checks
- future ReadySetRentables neighborhood profile checks
- future Skimmr document summary checks
- domain-specific scoring rules

This split keeps the platform useful across domains while allowing each domain
to define its own required sections, schemas, thresholds, and quality signals.

## Generic Models

### EvaluationReport Models

`EvaluationStatus` represents the outcome of a check or report:

- `passed`
- `warning`
- `failed`
- `skipped`

`EvaluationSeverity` describes how important a failed or warning check is:

- `info`
- `warning`
- `error`

`EvaluationCheckResult` describes one deterministic check:

- check name
- status
- severity
- safe message
- optional artifact path
- optional metadata dictionary

`EvaluationReport` aggregates a set of checks:

- report ID
- run ID when available
- domain
- evaluated artifact path
- evaluated artifact type
- provider, model, prompt name, and prompt version when available
- check results
- summary counts by status and severity
- created timestamp

### EvaluationComparisonReport Models

`EvaluationComparisonStatus` represents the outcome of one comparison:

- `match`
- `different`
- `improved`
- `regressed`
- `inconclusive`

`EvaluationComparisonItem` describes one comparison between a baseline and
candidate value:

- comparison name
- status
- severity
- safe message
- optional baseline value
- optional candidate value
- optional details dictionary

`EvaluationComparisonReport` aggregates a set of comparison items:

- comparison report ID
- optional baseline report ID
- optional candidate report ID
- optional baseline artifact path
- optional candidate artifact path
- target name and type
- comparator name and version
- comparison items
- summary counts by status
- created timestamp

Messages, metadata, and details must not contain raw prompts, raw model output
text, raw review datasets, payload contents, secrets, API keys, or
password-bearing DSNs.

## Artifact Strategy

Evaluation results are written as artifacts so humans and future tools can
inspect them. Artifact names are derived from the evaluated artifact:

- `review_theme_summary.evaluation.json`
- `review_theme_summary.evaluation.md`
- `review_theme_summary.comparison.json`
- `review_theme_summary.comparison.md`

JSON is useful for machine inspection and future dashboards. Markdown is useful
for human review. `ArtifactType.EVALUATION_REPORT` and
`ArtifactType.EVALUATION_COMPARISON_REPORT` are both recognized generic artifact
types, so evaluation and comparison files can be represented as `ArtifactRecord`
rows without introducing domain-specific artifact types.

Evaluation and comparison artifacts contain check names, statuses, severities,
safe messages, and metadata. They do not contain artifact contents by default.
They do not embed raw prompts, raw model output text, representative review
text, raw datasets, provider payloads, or secrets.

Automatic evaluation or comparison persistence is intentionally deferred.

## Relationship To Artifacts

Evaluation starts from artifacts, not in-memory objects hidden inside a
workflow. A report can say which file it evaluated and which run or model
invocation produced that file when the metadata is available.

For ReadySetRentables, the current target is:

- `review_theme_summary.md`

Later targets can include:

- `review_insights.json`
- `neighborhood_profile.md`
- `neighborhood_profile.json`

## Relationship To Model Invocations

Evaluation reports preserve provider, model, prompt, and version context when it
is available from model invocation records or the evaluated artifact. That makes
it possible to compare:

- fake output vs local Ollama output
- one Ollama model vs another Ollama model
- one prompt version vs another prompt version
- local Ollama output vs future OpenAI or Claude output after explicit opt-in

The harness does not infer sensitive prompt bodies from invocation records.
`model_invocations` intentionally stores metadata and artifact paths, not raw
prompts or raw responses.

## First ReadySetRentables Checks

The ReadySetRentables evaluator checks `review_theme_summary.md`
deterministically:

- artifact exists
- file is non-empty
- contains expected title or section markers
- contains `run_id`
- contains prompt and model metadata
- contains a non-empty summary section
- token and cost metadata are present when available
- output is not obviously placeholder-only

These checks are intentionally structural. They do not claim whether the prose
is subjectively good, complete, or business-ready. No model provider calls are
made.

## ReadySetRentables Review Theme Summary Comparison Checks

The ReadySetRentables comparison evaluator compares two `review_theme_summary.md`
artifacts deterministically:

- baseline artifact exists
- candidate artifact exists
- both artifacts are non-empty
- title presence matches
- summary section presence matches
- prompt metadata presence matches
- model metadata presence matches
- usage section presence matches
- summary length delta (flags significant regressions)
- placeholder regression (flags candidate placeholder when baseline was not)

No model provider calls are made. The comparator is intended for
fake-vs-Ollama, prompt-vs-prompt, or model-vs-model comparisons.

## CLI And Inspection

### evaluate-review-theme-summary

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
written report paths.

### compare-review-theme-summaries

```sh
.venv/bin/daedalus compare-review-theme-summaries \
  --baseline artifacts/fake/review_theme_summary.md \
  --candidate artifacts/ollama/review_theme_summary.md \
  --output-json artifacts/readysetrentables/review_theme_summary.comparison.json \
  --output-md artifacts/readysetrentables/review_theme_summary.comparison.md
```

The comparison is deterministic and file-only. No model calls are made. If no
output path is provided, the comparison JSON is written next to the candidate
file as `review_theme_summary.comparison.json`. The command prints only target
identity, comparison counts, and written report paths.

### record-evaluation-report-artifact

```sh
.venv/bin/daedalus record-evaluation-report-artifact \
  --run-id <run-id> \
  --path artifacts/readysetrentables/review_theme_summary.evaluation.json
```

Records an existing evaluation report file as `ArtifactType.EVALUATION_REPORT`
for a persisted workflow run. This is manual and explicit; evaluation is not
automatically wired into workflows or LangGraph.

### record-evaluation-comparison-report-artifact

```sh
.venv/bin/daedalus record-evaluation-comparison-report-artifact \
  --run-id <run-id> \
  --path artifacts/readysetrentables/review_theme_summary.comparison.json
```

Records an existing comparison report file as
`ArtifactType.EVALUATION_COMPARISON_REPORT` for a persisted workflow run. This
is manual and explicit; comparison execution is not automatically wired into
workflows or LangGraph.

After either recording command, `show-run` can display the corresponding
artifact path alongside the other persisted artifacts for that run.

## Makefile Checks

### evaluation-check

```sh
make evaluation-check
```

Runs the LangGraph fake summary path, evaluates `review_theme_summary.md`,
verifies the JSON and Markdown evaluation artifacts exist, and cleans generated
artifacts. Does not require Docker, `.env`, Ollama, provider SDKs, or network
access. Not called by `make check`.

### comparison-check

```sh
make comparison-check
```

Runs the LangGraph fake summary path, copies `review_theme_summary.md` into
baseline and candidate inputs, runs `compare-review-theme-summaries`, verifies
the JSON and Markdown comparison artifacts exist, and cleans generated artifacts.
Does not require Docker, `.env`, Ollama, provider SDKs, or network access. Not
called by `make check`.

### evaluation-db-check

Verifies the full manual persisted evaluation path end-to-end: runs the LangGraph
workflow with `--persist`, evaluates `review_theme_summary.md`, records the
evaluation JSON as `ArtifactType.EVALUATION_REPORT`, and confirms `show-run`
includes `evaluation_report`. Optional; may require Docker, Postgres, and `.env`.
Does not require Ollama. Not called by `make check`.

### comparison-db-check

Verifies manual persisted comparison artifact recording end-to-end: runs the
LangGraph workflow with `--persist`, copies `review_theme_summary.md` into
baseline and candidate inputs, runs `compare-review-theme-summaries`, records
the comparison JSON as `ArtifactType.EVALUATION_COMPARISON_REPORT`, and confirms
`show-run` includes `evaluation_comparison_report`. Optional; may require Docker,
Postgres, and `.env`. Does not require Ollama. Not called by `make check`.

## Evaluator-Model Checks

Evaluator-model checks do not exist yet. When added, they must go behind the
same controls as other model calls:

- `ModelClient`
- `RecordingModelClient`
- `ModelBudget`
- prompt/version tracking
- model invocation records
- local-first provider policy
- explicit cloud-provider opt-in

Evaluator-model outputs should be artifacts, and their invocation metadata
should be recorded like any other model call.

## Security Rules

Evaluation and comparison code must follow the same safety rules as model-client
and workflow code:

- do not print or persist raw prompts unnecessarily
- do not print or persist raw model output text unnecessarily
- do not print or persist raw sensitive datasets
- do not store representative review text in evaluation metadata by default
- do not include provider request payload contents
- do not put secrets in evaluation artifacts
- do not document real `.env` values or password-bearing DSNs
- do not require live Ollama, cloud providers, or network calls in `make check`

Evaluation and comparison reports should be safe to share as metadata-oriented
artifacts unless a domain-specific evaluator explicitly documents otherwise.

## Future Work

- optional `run-workflow` flag to evaluate after workflow completion
- optional automatic evaluation artifact persistence
- fake-vs-Ollama comparison workflow examples
- evaluator-model scoring behind `ModelClient` controls
- future RSR `review_insights.json` and `neighborhood_profile.md` evaluators
- future Skimmr document summary evaluators
- `show-run` evaluation and comparison summary display
- cloud-provider comparison support after cloud providers are introduced
- dashboards or OpenTelemetry
