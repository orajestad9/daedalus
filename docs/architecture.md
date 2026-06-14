# Daedalus Architecture

Daedalus is a local-first Python AI workflow orchestration platform for
observable, human-approved AI pipelines. The current implementation supports
deterministic workflows, optional LangGraph execution, local artifact files,
metadata persistence in Daedalus Postgres, model invocation tracking, fake model
paths, explicit local Ollama paths, deterministic evaluations/comparisons, and a
read-only ReadySetRentables source extraction boundary.

This page is demo-oriented. It distinguishes what exists now from V1 work that
is intentionally deferred.

## Current Platform Architecture

```mermaid
flowchart LR
    operator[Developer / operator]
    cli[Daedalus CLI]
    manifests[Workflow manifests]
    router[Workflow router]
    deterministic[Deterministic runner]
    langgraph[LangGraph runner]
    domain[RSR domain modules]
    artifacts[Local artifact files]
    evals[Deterministic evaluators and comparisons]
    modelBoundary[ModelClient boundary]
    fake[FakeModelClient]
    ollama[Manual local Ollama client]
    recording[RecordingModelClient]
    pg[(Daedalus metadata Postgres)]

    operator --> cli
    cli --> manifests
    cli --> router
    router --> deterministic
    router --> langgraph
    deterministic --> domain
    langgraph --> domain
    domain --> artifacts
    domain --> evals
    domain --> modelBoundary
    modelBoundary --> fake
    modelBoundary --> ollama
    modelBoundary --> recording
    recording --> pg
    cli --> pg
    artifacts --> pg

    cloud[Cloud model providers]
    writeback[RSR source DB writeback]
    agentLoop[Autonomous multi-agent loop]

    cloud -. planned/deferred .-> modelBoundary
    writeback -. planned/deferred .-> domain
    agentLoop -. planned/deferred .-> router
```

Current behavior:

- `run-workflow` can execute deterministic workflows and LangGraph workflows.
- Workflow runs, steps, artifacts, and model invocation records can be persisted
  to Daedalus Postgres.
- Generated artifacts are local files under `artifacts/`.
- Fake model paths are testable and provider-free.
- Ollama is explicit, local, and manual. It is not the default provider and is
  not wired into `run-workflow` or LangGraph for review insights.
- Deterministic evaluators and comparisons run as explicit CLI paths.

Deferred behavior:

- Cloud model providers are not implemented.
- Source-derived review insight extraction is not wired into LangGraph.
- No autonomous multi-agent loop is active.
- Daedalus does not write back to the ReadySetRentables source database.

## RSR Source Extraction And Review Insight Pipeline

```mermaid
flowchart TD
    rsrDb[(ReadySetRentables Postgres source DB)]
    extractor[Read-only source repository]
    sourceArtifact[rsr_source_extract.json]
    sourceEval[Source extract evaluator]
    sourceReports[Evaluation JSON / Markdown]
    recorder[Artifact recorder]
    daedalusPg[(Daedalus metadata Postgres)]
    builder[build-review-insight-input]
    insightInput[review_insight_extraction_input.json]
    agent[ReviewInsightExtractionAgent]
    parser[Review insight output parser]
    ollama[Explicit local Ollama model]
    insights[review_insights.json]
    insightEval[Review insight evaluator shell]
    profile[Neighborhood profile generation]
    writeback[RSR writeback / export]

    rsrDb -->|read-only manual extraction| extractor
    extractor --> sourceArtifact
    sourceArtifact --> sourceEval
    sourceEval --> sourceReports
    sourceArtifact --> recorder
    recorder --> daedalusPg
    sourceArtifact --> builder
    builder --> insightInput
    insightInput --> agent
    agent --> ollama
    ollama --> agent
    agent --> parser
    parser --> insights

    insights -. deterministic evaluator exists as planned/use-next path .-> insightEval
    insights -. planned V1 .-> profile
    profile -. planned/deferred .-> writeback

    classDef current fill:#e8f5e9,stroke:#2e7d32,color:#111;
    classDef needsValidation fill:#fff8e1,stroke:#f9a825,color:#111;
    classDef planned fill:#eeeeee,stroke:#777,stroke-dasharray: 5 5,color:#111;

    class rsrDb,extractor,sourceArtifact,sourceEval,sourceReports,recorder,daedalusPg,builder,insightInput,agent,parser current;
    class ollama,insights needsValidation;
    class insightEval,profile,writeback planned;
```

Current RSR behavior:

- Source extraction from the RSR Postgres database is read-only and manual.
- `rsr_source_extract.json` generation works.
- Source extract evaluation works through deterministic checks.
- Source extract artifacts can be recorded against Daedalus workflow runs.
- `review_insight_extraction_input.json` generation works.
- `ReviewInsightExtractionAgent`, parser, CLI, and artifact writer exist.

Needs UM790 validation:

- `extract-review-insights-ollama` with `qwen2.5-coder:7b` should be rerun
  after the safe diagnostic improvements. It should either write
  `review_insights.json` or fail with a safe diagnostic category.

## Demo-Ready Workflow Path

```mermaid
sequenceDiagram
    participant Dev as Developer
    participant CLI as Daedalus CLI
    participant WF as Workflow runner
    participant Files as Local artifacts
    participant Eval as Evaluators
    participant DB as Daedalus Postgres
    participant Ollama as Local Ollama

    Dev->>CLI: make check
    CLI->>WF: unit, lint, format, type checks
    WF-->>Dev: local quality gate

    Dev->>CLI: run-workflow --execution-engine langgraph --persist
    CLI->>WF: run manifest
    WF->>Files: write normalized reviews / fake summary artifacts
    WF->>DB: persist run, steps, artifacts, invocations
    CLI-->>Dev: run_id

    Dev->>CLI: show-run --run-id
    CLI->>DB: load run details
    CLI-->>Dev: inspectable metadata

    Dev->>CLI: source extraction and evaluation commands
    CLI->>Files: write source extract and reports
    CLI->>DB: optionally record source extract artifact

    Dev->>CLI: extract-review-insights-ollama
    CLI->>Ollama: explicit local model call
    Ollama-->>CLI: JSON-like model response
    CLI->>Files: write review_insights.json or safe failure
```

For the portfolio demo, keep the screen focused on commands, success metadata,
artifact filenames, and `show-run` output. Do not display raw review text,
artifact contents from real data, prompt text, raw model output, `.env` values,
DSNs, secrets, or private network details.

## Planned V1 Agentic Loop

```mermaid
flowchart TD
    trigger[Human-approved trigger]
    plan[Planner / workflow policy]
    extract[Read-only source extraction]
    inspect[Deterministic validation]
    insights[Review insight extraction]
    profile[Neighborhood profile generation]
    evaluate[Evaluation and comparison gates]
    approval[Human approval gate]
    publish[Export / optional guarded writeback]
    memory[(Daedalus metadata and artifacts)]

    trigger --> plan
    plan --> extract
    extract --> inspect
    inspect --> insights
    insights --> profile
    profile --> evaluate
    evaluate --> approval
    approval --> publish

    extract --> memory
    inspect --> memory
    insights --> memory
    profile --> memory
    evaluate --> memory
    approval --> memory

    publish -. current status: deferred .-> external[External destination]

    classDef planned fill:#eeeeee,stroke:#777,stroke-dasharray: 5 5,color:#111;
    classDef current fill:#e8f5e9,stroke:#2e7d32,color:#111;

    class trigger,plan,insights,profile,evaluate,approval,publish,external planned;
    class extract,inspect,memory current;
```

V1 intent:

- Keep source extraction read-only until an explicit guarded export or writeback
  path is designed.
- Route every model call through the `ModelClient` boundary.
- Preserve artifact lineage, model invocation metadata, prompt identity, token
  counts, costs when available, and deterministic evaluation outputs.
- Add human approval before any external publication or writeback.

Not V1-ready yet:

- LangGraph wiring for source-derived review insight extraction.
- Claude/Anthropic or other cloud provider clients.
- Neighborhood profile generation from review insights.
- Autonomous repair/retry loops for model JSON failures.
- Any writeback to the ReadySetRentables source application.
