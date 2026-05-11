# Daedalus Repo Instructions

Daedalus is a local-first Python AI workflow orchestration platform.

Core platform goals:
- deterministic workflows
- LangGraph workflow orchestration
- artifact lineage
- model invocation tracking
- token/cost governance
- prompt versioning
- local-first model execution
- deterministic evaluation and comparison harnesses

## Architecture Boundary

- Generic platform code must stay generic.
- ReadySetRentables-specific behavior belongs under domain modules.
- Do not hardcode ReadySetRentables logic into generic orchestrator, model-client, artifact, persistence, or evaluation infrastructure.
- Prefer small, scoped changes.
- Do not do broad refactors unless explicitly asked.

Current important boundaries:
- Ollama is manual/local-only. Not wired into LangGraph, not wired into run-workflow, not default anywhere.
- No cloud provider clients exist yet. Do not add provider SDK dependencies.
- Evaluation and comparison are deterministic and manual. Not automatically wired into LangGraph or run-workflow.
- `make check` must not require Postgres, Docker, Ollama, or network access.

## Security Rules

- Do not commit secrets or API keys.
- Do not print or persist raw prompt text unless explicitly required.
- Do not print or persist raw model output text unless explicitly required.
- Do not print artifact contents in CLI success messages.
- Do not print review datasets.
- Do not include request payload contents in error messages.
- Do not add cloud model usage unless explicitly requested.

## Token Usage Rules

- Minimize token usage while still completing the task.
- Do not produce long explanations or restate the whole plan after every command.
- Inspect only the files needed for the task. Prefer targeted searches over reading the whole repo.
- Make the smallest correct change. Do not rewrite unrelated code.
- Do not run expensive or unnecessary commands.
- Run only the checks requested by the task unless a narrower test is clearly enough first.
- If anything is unclear, ask one concise question. If the task is clear, proceed.

## Workflow Rules

- Do not commit unless explicitly instructed.
- Do not push unless explicitly instructed.
- Before editing, briefly identify the files you expect to touch.
- After changes, summarize: (1) files changed, (2) what changed, (3) checks run, (4) any issues or follow-ups.

## Default Check

Run `make check` unless the task says otherwise. `make check` runs pytest, ruff lint, ruff format check, and mypy. It is unit-only and does not require Docker or Postgres.
