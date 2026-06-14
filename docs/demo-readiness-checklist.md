# Demo Readiness Checklist

## Ready Now

- Core docs explain Daedalus as a local-first Python AI workflow orchestration
  platform.
- Deterministic workflow execution exists.
- LangGraph workflow execution exists for the current review workflow path.
- Daedalus metadata Postgres persistence exists for workflow runs, steps,
  artifacts, and model invocation records.
- `show-run` and `list-runs` can inspect persisted run metadata.
- `FakeModelClient` and `RecordingModelClient` provide local, testable model
  boundaries.
- Deterministic evaluation and comparison commands exist.
- ReadySetRentables source extraction from the source Postgres database is
  read-only and manual.
- `rsr_source_extract.json` generation works.
- Source extract evaluation works.
- Source extract artifacts can be recorded against Daedalus workflow runs.
- `build-review-insight-input` generates
  `review_insight_extraction_input.json`.
- `ReviewInsightExtractionAgent`, parser, CLI, and artifact writer exist.
- Ollama smoke check has passed with `qwen2.5-coder:7b` on the UM790.
- Safe diagnostic categories exist for review insight parser/provider failures.

## Needs UM790 Validation

Rerun the current blocker command after the safe diagnostic improvements:

```sh
.venv/bin/daedalus extract-review-insights-ollama \
  --input-json artifacts/readysetrentables/review_insight_extraction_input.json \
  --model qwen2.5-coder:7b \
  --output-json artifacts/readysetrentables/review_insights.json
```

Expected acceptable outcomes:

- Success: `review_insights.json` is written and the CLI prints safe metadata.
- Safe failure: the CLI reports a fixed diagnostic category, such as timeout,
  local Ollama request failure, empty model output, missing JSON object, invalid
  JSON, or schema mismatch.

Unacceptable outcomes:

- raw review text appears in terminal output
- raw prompt text appears in terminal output
- raw model output appears in terminal output
- artifact contents appear in terminal output
- secrets, DSNs, passwords, `.env` values, or private network details appear in
  terminal output

## Nice-To-Have Before Recording

- Capture a clean `make check` run.
- Capture a clean `make db-check` run if local Postgres and `.env` are already
  ready.
- Capture one cropped `show-run` output for persisted metadata.
- Capture source extraction and source evaluation command output on the UM790.
- Capture the file tree showing artifact filenames only.
- Capture the Mermaid diagrams from `docs/architecture.md`.
- Keep a short spoken explanation ready for why Ollama is manual and explicit
  instead of automatic.
- Prepare placeholder values for market names and run IDs in slides or captions.

## Do Not Block The Demo On This

- Claude/Anthropic provider support.
- Cloud provider SDK integration.
- LangGraph wiring for source-derived review insight extraction.
- Full source extraction -> review insights -> neighborhood profile workflow
  wiring.
- Neighborhood profile generation.
- Human approval gate implementation.
- RSR writeback/export implementation.
- Automatic evaluation after every workflow run.
- Autonomous retry or repair loops for malformed model JSON.
- Pixel-perfect architecture diagrams beyond the Mermaid diagrams in this doc
  set.

## Risks And Mitigations

- Risk: local Ollama returns malformed JSON.
  Mitigation: frame this as the current frontier and show the safe diagnostic
  category if the command fails.

- Risk: real source-derived artifacts contain review text.
  Mitigation: show artifact filenames and metadata only; do not open artifact
  contents on screen.

- Risk: terminal history or environment output exposes secrets or private
  network details.
  Mitigation: use a clean terminal profile, avoid `env`, avoid `.env`, crop
  terminal output, and rehearse commands before recording.

- Risk: Postgres is not running for persisted-demo commands.
  Mitigation: record `make check` and file-only paths first; treat `make
  db-check` as optional if the local `.env` and Docker environment are not ready.

- Risk: the audience reads the Ollama path as production automation.
  Mitigation: explicitly say Ollama is local, manual, and not wired into
  `run-workflow` or LangGraph for review insights yet.

- Risk: V1 scope sounds complete today.
  Mitigation: use the architecture diagrams' current/planned language and close
  with the checklist distinction between ready now, needs validation, and
  deferred work.
