# LangGraph Orchestration

Phase 3 introduces a LangGraph orchestration baseline for Daedalus without
changing the behavior of the deterministic ReadySetRentables review workflow.
LangGraph is now available as a project dependency for this workflow path, but
Phase 3 still does not create agents, add model clients, or make LLM calls.

## Why LangGraph Now

Daedalus already has the pieces a graph runtime should preserve: manifests,
approval gates, artifacts, run records, workflow step records, optional
Postgres persistence, and `run_id` logging context. Introducing LangGraph after
those boundaries exist makes the graph an orchestration layer rather than a
place where parsing, artifact writing, persistence, or model-provider logic gets
mixed together.

The first graph should reproduce the existing deterministic workflow before it
adds branching, retries, model calls, or agents.

## Current Deterministic Workflow

The ReadySetRentables workflow currently performs deterministic Python work:

1. Load Airbnb review CSV data.
2. Write normalized review JSON.
3. Write artifact metadata JSON.
4. Write human-readable summary markdown.
5. Write workflow run record JSON.

The workflow produces the same file artifacts as before:

- `normalized_reviews.json`
- `normalized_reviews.metadata.json`
- `normalized_reviews.summary.md`
- `normalized_reviews.run.json`

When `run-workflow --persist` is used, Postgres persistence remains optional and
happens after workflow execution through the existing persistence service.

## Manifest Execution Engine

Workflow manifests can now choose the execution engine with `execution_engine`.
Supported values are:

- `deterministic`
- `langgraph`

The default is `deterministic`, so existing manifests remain on the trusted
deterministic workflow unless they explicitly opt into LangGraph. The committed
`workflows/readysetrentables_review_normalization.yaml` manifest is explicit
about this default. The sample
`workflows/readysetrentables_review_normalization_langgraph.yaml` manifest runs
the same ReadySetRentables workflow through the compiled LangGraph path for
manual comparison and testing.

The manifest router still enforces approval before execution. For LangGraph
runs, the router adapts the final graph state back into the existing
`ReviewNormalizationWorkflowResult` shape so CLI output, persistence, and future
callers can keep using the same workflow result contract.

For ad hoc comparison runs, the CLI can override the manifest setting without
editing the YAML file:

```bash
.venv/bin/daedalus run-workflow \
  --manifest workflows/readysetrentables_review_normalization.yaml \
  --execution-engine langgraph
```

The override is scoped to that command invocation. Approval gates and optional
`--persist` behavior remain unchanged.

The local `make db-check` integration command now exercises both persisted
paths: the default deterministic manifest run and a LangGraph override run. It
then inspects the persisted LangGraph run with `show-run` to verify that run,
artifact, and workflow step records remain inspectable through Postgres.

## What LangGraph Is Responsible For

LangGraph should eventually own workflow control flow:

- node ordering
- explicit graph state transitions
- branching when later workflows need it
- retry boundaries when they are intentionally designed
- attaching graph nodes to `WorkflowStepRecord` names
- preserving `run_id` and workflow context across nodes

Graph nodes should operate on structured state and domain objects. They should
not pass loose prompt text around as the primary workflow interface.

## What LangGraph Is Not Responsible For Yet

The initial LangGraph baseline should not own:

- CSV parsing rules
- Pydantic domain models
- artifact serialization details
- Postgres SQL or repository logic
- direct provider calls
- agent behavior
- human approval persistence
- OpenTelemetry spans

No model calls should be introduced in Phase 3 Step 1.

## Proposed Graph Shape

The first graph should mirror the current deterministic phases:

```text
load_reviews
  -> write_normalized_artifact
  -> write_metadata_artifact
  -> write_summary_artifact
  -> write_run_record_artifact
```

This keeps current artifact outputs and tests stable while allowing the workflow
execution boundary to move toward a graph runtime.

## Proposed Graph State

The graph state should carry structured Pydantic and domain objects where
practical. Proposed state fields include:

- `run_id`
- `input_csv_path`
- `output_json_path`
- `batch`
- `metadata_json_path`
- `summary_markdown_path`
- `run_record_json_path`
- `steps`
- `approval_required`
- `approved`

State should favor typed paths, domain batches, metadata objects, and step
records over unstructured strings. Prompt text should not become the graph's
default transport format.

## Proposed Graph Nodes

Initial nodes should match the current step names:

- `load_reviews`
- `write_normalized_artifact`
- `write_metadata_artifact`
- `write_summary_artifact`
- `write_run_record_artifact`

Each node should map directly to one `WorkflowStepRecord.step_name` so persisted
inspection, markdown summaries, and future LangGraph traces use the same
vocabulary.

## Artifacts And Persistence

Artifacts should remain file-based. LangGraph should call the same artifact
writers or equivalent domain-layer helpers so the current output files remain
unchanged.

Postgres persistence should remain opt-in through `--persist`. The graph should
produce a workflow result with enough structured data for the existing
persistence service to save run, artifact, and step records. SQL should stay in
repository classes, not in graph nodes.

## Approval Gates

The current manifest-driven approval gate runs before workflow execution. Later,
an `approval_check` node may make approval state explicit inside graph execution,
especially for workflows with multiple human decision points.

For the initial LangGraph baseline, approval behavior should remain compatible
with the current router and CLI behavior.

## Token And Cost Governance

Token and cost governance applies before any graph node can call a model. Future
model-backed graph nodes must use a shared `ModelClient` abstraction, attach
invocations to `run_id` and `step_id` when available, respect manifest budgets,
and write model outputs as artifacts when useful.

See [`docs/token-cost-governance.md`](token-cost-governance.md) and
[`docs/observability.md`](observability.md) before adding model invocation
nodes.

## Deferred Nodes

These nodes are intentionally deferred:

- `approval_check`
- `persist_run`
- `model_invocation`
- `validation`
- `human_review`

They should be added only when the surrounding persistence, governance,
approval, and inspection behavior is designed and tested.

## Intentionally Deferred

- replacing the existing deterministic workflow behavior
- model clients
- agents
- LLM calls
- token/model invocation tables
- OpenTelemetry
- LangGraph node tracing
- dashboard/UI work
- Docker app images
- Kubernetes execution
