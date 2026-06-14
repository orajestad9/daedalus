# Daedalus Demo Plan

Target length: 3-5 minutes.

Intended audience: technical hiring managers, engineers, and AI tooling
reviewers.

## Narrative

Daedalus is a local-first Python AI workflow orchestration platform for building
observable AI pipelines on a developer machine. The demo should show that it is
more than a script: it has workflow execution, artifact lineage, metadata
persistence, model invocation boundaries, deterministic evaluation, and a
guarded real-domain pipeline for ReadySetRentables.

The clean story is:

1. Start with the platform contract: local-first orchestration, observable runs,
   explicit model boundaries, no source DB writeback.
2. Show a deterministic/LangGraph workflow path that produces inspectable local
   artifacts and persisted metadata.
3. Show the ReadySetRentables source extraction boundary and deterministic
   evaluation.
4. Show the manual Ollama review insight path as the current frontier: agent,
   parser, artifact writer, and safe diagnostics exist, with UM790 validation as
   the next check.
5. Close with the V1 plan: agentic loop, human approval, cloud-provider option,
   neighborhood profile generation, and guarded export/writeback later.

## Video Sections

### 0:00-0:30 - What Daedalus is

Show the README and say:

- local-first Python AI workflow orchestration
- deterministic and LangGraph execution
- local artifacts plus Daedalus metadata Postgres
- model invocation tracking through a `ModelClient` boundary
- ReadySetRentables is the first real domain pipeline

Screenshot to capture: README top section or `docs/architecture.md` platform
diagram.

### 0:30-1:20 - Platform workflow and observability

Run or show:

```sh
make check
```

What it proves:

- tests, lint, format check, and type check pass locally
- the core platform has a repeatable quality gate

Optional persisted run path for the recording environment:

```sh
make db-check
```

What it proves:

- Daedalus Postgres migrations work
- deterministic and LangGraph workflow runs can persist run, step, artifact, and
  model invocation metadata
- `show-run` can inspect persisted run state

Screenshot to capture: terminal output showing the final success line and a
cropped `show-run` view that avoids secrets and raw artifact contents.

### 1:20-2:20 - ReadySetRentables source extraction boundary

Run later on the UM790:

```sh
.venv/bin/daedalus extract-rsr-source-data \
  --market-name <market-name> \
  --max-reviews 10 \
  --output-json artifacts/readysetrentables/rsr_source_extract.json
```

What it proves:

- Daedalus can read from the RSR Postgres source database through a dedicated
  read-only extraction path
- extraction writes a local artifact instead of changing source data

Then run:

```sh
.venv/bin/daedalus evaluate-rsr-source-extract \
  --source-extract artifacts/readysetrentables/rsr_source_extract.json \
  --output-json artifacts/readysetrentables/rsr_source_extract.evaluation.json \
  --output-md artifacts/readysetrentables/rsr_source_extract.evaluation.md
```

What it proves:

- source extracts can be checked deterministically
- evaluation outputs are artifacts, not ad hoc terminal-only judgments

Screenshot to capture: command success metadata and file tree showing artifact
names only. Do not open the real JSON artifacts on screen.

### 2:20-3:10 - Bridge into review insight extraction

Run later on the UM790:

```sh
.venv/bin/daedalus build-review-insight-input \
  --source-extract artifacts/readysetrentables/rsr_source_extract.json \
  --output-json artifacts/readysetrentables/review_insight_extraction_input.json
```

What it proves:

- Daedalus converts source extraction output into the typed input expected by
  the review insight agent
- the source data boundary and agent input boundary are separate

Screenshot to capture: successful command output and artifact filename only.
Do not show `review_insight_extraction_input.json` contents because it can
include representative review text.

### 3:10-4:20 - Manual local Ollama review insight path

First confirm Ollama connectivity on the UM790:

```sh
.venv/bin/daedalus ollama-smoke-check --model qwen2.5-coder:7b
```

What it proves:

- local Ollama is reachable
- local model execution is explicit and operator-selected

Then rerun the current known blocker validation:

```sh
.venv/bin/daedalus extract-review-insights-ollama \
  --input-json artifacts/readysetrentables/review_insight_extraction_input.json \
  --model qwen2.5-coder:7b \
  --output-json artifacts/readysetrentables/review_insights.json
```

What it proves if it succeeds:

- `ReviewInsightExtractionAgent` can call local Ollama
- parser/schema handling can produce `review_insights.json`
- the CLI reports safe metadata without printing raw review text or raw model
  output

What it proves if it fails safely:

- recent safe diagnostic improvements are working
- the command classifies the failure without leaking prompt text, raw model
  output, source-derived review text, secrets, or artifact contents

Screenshot to capture: success metadata or safe diagnostic category. Do not
capture raw model output or open `review_insights.json`.

### 4:20-5:00 - Current vs V1

Show `docs/architecture.md` planned V1 diagram and explain:

- current: deterministic workflows, LangGraph path, persistence, artifact
  lineage, fake model path, explicit local Ollama path, RSR source extraction,
  deterministic evaluation
- needs validation: real UM790 review insight extraction after safe diagnostic
  changes
- planned V1: source-derived LangGraph wiring, neighborhood profile generation,
  human approval gates, optional cloud providers, guarded export/writeback

Screenshot to capture: planned V1 diagram and the checklist summary.

## Screenshot List

- README top section or platform architecture diagram.
- `make check` success output.
- Optional `make db-check` success output.
- `show-run` output with run metadata only.
- RSR source extraction command success metadata.
- Source extract evaluation success metadata.
- File tree showing artifact filenames under `artifacts/readysetrentables/`
  without opening real artifacts.
- Review insight input build success metadata.
- Ollama smoke check result with `qwen2.5-coder:7b`.
- Review insight extraction success metadata or safe diagnostic category.
- Planned V1 agentic loop diagram.

## Safety Notes

- Do not show raw review text.
- Do not show real artifact contents.
- Do not show `.env` files or `.env` values.
- Do not show passwords, tokens, DSNs, secrets, or private IP addresses.
- Do not show raw model output.
- Do not show prompt text.
- Keep terminal windows cropped to command names, statuses, artifact filenames,
  run IDs, provider/model names, prompt identity, counts, and safe diagnostics.
- Use placeholders such as `<market-name>` in recorded docs or slides.
- Keep real generated artifacts local and untracked.
