# Phase 5A Fake Agent LangGraph Integration

Phase 5A wires the existing fake/local ReadySetRentables review theme summary
agent into the LangGraph workflow before Daedalus adds any real local provider
support. The compiled LangGraph workflow now includes the fake summary nodes and
writes `review_theme_summary.md` as part of graph execution. The purpose is to
prove the graph, model-client, artifact, budget, and observability boundaries
together while the model behavior is still fully deterministic and local.

No real provider SDKs, network calls, real LLM calls, cloud model usage,
OpenTelemetry, or new migrations should be added in Phase 5A.

## Why Phase 5A Comes Before Ollama

Daedalus already has a tested `ReviewThemeSummaryAgent`, `FakeModelClient`,
`RecordingModelClient`, model invocation records, prompt templates, and a
markdown artifact writer. Integrating those pieces into LangGraph with the fake
client first gives maintainers a stable graph path for:

- preserving `run_id` and workflow context through model-like nodes
- recording workflow steps around agent work
- recording fake model invocation metadata without provider risk
- writing `review_theme_summary.md` as a normal file artifact
- keeping `show-run` inspection focused on metadata and artifact paths

Ollama or another local provider should satisfy the same `ModelClient` contract
later. If the fake graph path is stable first, a future `OllamaModelClient` can
replace `FakeModelClient` behind the same boundary with less workflow churn.

## Current Integrated Pieces

The current system has these pieces joined in the LangGraph path:

- `ReadySetRentablesReviewGraphState`
- deterministic LangGraph nodes for loading reviews and writing normalization
  artifacts
- `ReviewThemeSummaryInput`, `ReviewThemeSummaryResult`, and
  `ReviewThemeSummaryTheme`
- `build_review_theme_summary_input(...)`
- `ReviewThemeSummaryAgent`
- `FakeModelClient`
- `RecordingModelClient`
- `ModelInvocationRecorder`
- `ModelInvocationRepository`
- `write_review_theme_summary_markdown(...)`
- `ArtifactType.REVIEW_THEME_SUMMARY`
- `summarize-review-themes-fake`
- `record-review-theme-summary-artifact`

`summarize-review-themes-fake` remains a manual file/artifact path for running
the fake summary agent outside the workflow. The LangGraph execution path now
creates `review_theme_summary.md` as part of graph execution. The deterministic
workflow remains unchanged and does not create this artifact.

## Integrated Workflow

The Phase 5A graph extends the deterministic graph with a fake agent branch
after the run record artifact is written.

Current node order:

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

The integrated path uses `FakeModelClient` only. All model-like
behavior must still go through the `ModelClient` protocol so later local
provider work can reuse the same graph shape.

## Graph State Additions

`ReadySetRentablesReviewGraphState` has typed fields for the fake summary
path:

- `review_theme_summary_input`
- `review_theme_summary_result`
- `review_theme_summary_markdown_path`

These fields should carry structured domain objects and paths, not loose prompt
text or raw model output text. The existing `run_id`, `batch`, artifact paths,
approval flags, and `steps` list should continue to be preserved across node
transitions.

## Graph Nodes

### `build_review_theme_summary_input`

This node:

- require `state.batch` to be populated
- call `build_review_theme_summary_input(...)`
- use the graph `run_id`
- produce compact deterministic input
- append a completed `WorkflowStepRecord` named
  `build_review_theme_summary_input`

It does not call a model client, read provider settings, or write artifacts.

### `run_fake_review_theme_summary_agent`

This node:

- require `state.review_theme_summary_input` to be populated
- construct `ReviewThemeSummaryAgent` with `FakeModelClient`
- call `agent.summarize(...)`
- store `review_theme_summary_result` in graph state
- append a completed `WorkflowStepRecord` named
  `run_fake_review_theme_summary_agent`

The node must not call provider SDKs directly. It must not read API keys,
provider environment variables, or cloud configuration. It must not make network
calls.

### `write_review_theme_summary_artifact`

This node:

- require `state.review_theme_summary_result` to be populated
- write `review_theme_summary.md` with
  `write_review_theme_summary_markdown(...)`
- populate `review_theme_summary_markdown_path`
- append a completed `WorkflowStepRecord` named
  `write_review_theme_summary_artifact`

It writes the artifact file and does not print artifact contents.

## Recording And Persistence

Phase 5A should keep persistence explicit and safe.

The graph integration produces a local `review_theme_summary.md` artifact path.
ArtifactRecord persistence for this file is still future work. Later persistence
work should create an `ArtifactRecord` with:

- `ArtifactType.REVIEW_THEME_SUMMARY`
- the same workflow `run_id`
- the generated `review_theme_summary.md` path

Model invocation persistence from the graph path is also future work. When a
`RecordingModelClient` is later used with a `ModelInvocationRecorder`, fake model
invocation metadata should be recorded with provider, model, prompt, version,
token, cost, status, duration, and artifact-path fields. Raw prompt text, raw
model output text, full review datasets, and artifact contents should not be
printed or blindly persisted.

Eventually, `show-run` should display:

- normal workflow artifacts
- the `review_theme_summary` artifact
- workflow steps for the fake summary nodes
- model invocation metadata for the fake agent call

## Preparing For OllamaModelClient

`FakeModelClient` and a future `OllamaModelClient` should satisfy the same
`ModelClient.complete(request) -> ModelResponse` contract. The graph node should
depend on the protocol, not provider-specific classes, so swapping the fake
client for a local provider later does not require changing graph state,
artifact semantics, prompt identity, budget validation, or invocation
recording.

Ollama support should come only after the fake graph path is tested and
inspectable. It should remain local-first and opt-in.

## Intentionally Deferred

- Ollama/local provider implementation
- OpenAI, Anthropic, or other cloud provider adapters
- provider SDK dependencies
- network calls
- real LLM calls
- cloud model execution
- automatic cloud fallback
- autonomous planning
- human-review loops inside the graph
- OpenTelemetry tracing
- dashboards/UI
- Kubernetes or production deployment

## Related Documents

- [`docs/langgraph-orchestration.md`](langgraph-orchestration.md)
- [`docs/model-client-architecture.md`](model-client-architecture.md)
- [`docs/review-theme-summary-agent.md`](review-theme-summary-agent.md)
- [`docs/observability.md`](observability.md)
- [`docs/token-cost-governance.md`](token-cost-governance.md)
