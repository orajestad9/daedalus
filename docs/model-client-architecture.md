# Model Client Architecture

Phase 4 starts by defining the model-client boundary before Daedalus adds
agents, provider SDKs, or LLM calls. This document is design guidance only. It
does not add implementation code, dependencies, cloud model usage, or database
tables.

Daedalus is local-first and human-approved. Model calls must be deliberate,
observable, budgeted, and attached to workflow context from the beginning.

## Why A Shared ModelClient

Daedalus needs one shared `ModelClient` abstraction so LangGraph nodes, future
agents, validators, and approval workflows all use the same invocation path.
That path should enforce budgets, provider opt-in, prompt/version tracking,
structured output expectations, artifact writing, and safe logging.

Agents and nodes must not call providers directly. Direct provider calls would
make token usage, cost, privacy, retry behavior, and audit trails drift across
the codebase.

## Proposed Architecture Flow

```text
LangGraph node or agent
  -> ModelClient
  -> provider adapter
  -> local/cloud model
  -> ModelInvocationRecord
  -> output artifact
```

The graph node or agent should know what task it needs performed. The
`ModelClient` should know how to validate the request, choose an allowed
provider, enforce budgets, capture invocation metadata, and return a structured
response. Provider adapters should own provider-specific API details.

## Proposed Future Interfaces

These names describe the intended shape. They are not implemented yet.

- `ModelClient`: shared entry point for all model calls.
- `ModelRequest`: structured request with run context, prompt identity, input
  artifact references, output schema expectations, provider constraints, and
  budget context.
- `ModelResponse`: structured response with status, parsed output, token
  counts when available, model metadata, and output artifact paths.
- `ModelProvider`: provider adapter interface implemented by local and cloud
  providers.
- `ModelInvocationRecord`: audit record for one model call, attached to
  `run_id` and `step_id` when available.
- `ModelBudget`: manifest or runtime budget object covering token, cost,
  invocation count, provider, and model constraints.

## Provider Strategy

Phase 4 should start with a fake or in-memory model client, or a local Ollama
adapter, before cloud providers. That lets Daedalus test model-call boundaries,
artifacts, budgets, and observability without sending workflow data outside the
local machine.

Proposed provider order:

1. Ollama or another local provider first.
2. OpenAI provider later.
3. Anthropic provider later.

Cloud providers must require explicit opt-in through environment configuration
and workflow policy. Missing opt-in should fail closed with a clear error.

## Local-First Model Strategy

Daedalus should prefer deterministic preprocessing and local models whenever
they meet the workflow quality bar. Cloud models should not become an accidental
default because a package is installed or an environment variable exists.

Before a model call, workflows should reduce inputs through deterministic code:
parse files, normalize records, filter irrelevant fields, validate schemas, and
write compact artifacts. Model calls should consume the smallest faithful input
artifact needed for the task.

## Token And Cost Governance

Every model call should respect the rules in
[`docs/token-cost-governance.md`](token-cost-governance.md). The `ModelClient`
should eventually enforce:

- maximum tokens per workflow run
- maximum model invocations per workflow run
- maximum estimated cost
- allowed providers
- allowed models or model tiers
- cloud-model opt-in
- prompt/version requirements

Budget checks should happen before a provider call whenever possible. If a call
would exceed budget, Daedalus should block it clearly and preserve enough
context for human review.

## Model Invocation Logging

Future model invocation records should be first-class observability events. They
should attach to:

- `run_id`
- `step_id` when the call happens inside a workflow step
- agent or component name
- provider
- model name
- prompt name
- prompt version
- status
- start and completion timestamps
- `duration_ms`
- token counts when available
- estimated cost when available
- input artifact path
- output artifact path

See [`docs/observability.md`](observability.md) for the current run, artifact,
step, and future model invocation observability model.

## Prompt And Version Tracking

Prompts should have stable names and versions. A model invocation should record
which prompt produced the output so maintainers can explain behavior after a
run completes.

Versioned prompt templates live under `prompts/` using safe, reviewable paths
such as `prompts/readysetrentables/review_theme_summary/v0.md`. Future model
requests should load prompts by `prompt_name` and `prompt_version`, then record
those identifiers on the invocation record. Prompt loading must reject absolute
paths and path traversal, and prompt files must not contain secrets, credentials,
private customer data, or connection strings.

Prompt changes should be treated like behavior changes. Future prompt templates
should avoid embedding secrets and should be reviewable like code or workflow
configuration.

## Structured Output Requirements

The `ModelClient` should prefer structured outputs over free-form text whenever
the downstream workflow expects machine-readable data. Responses should be
validated before later nodes or agents consume them.

Structured outputs make retries, approvals, persistence, and inspection easier
to reason about. If a provider cannot produce structured output directly, the
adapter or a validation step should make the conversion explicit.

## Artifact-Based Output Strategy

Model outputs should be written as artifacts when they are useful to inspect,
validate, approve, or replay. Database records should point to artifact paths
and invocation metadata rather than blindly storing large or sensitive raw
payloads.

Artifact-based output keeps `show-run`, markdown summaries, future dashboards,
and human approval tools aligned with the rest of Daedalus.

## Provider Routing Strategy

Provider routing should be policy-driven. A future `ModelClient` can choose a
provider based on:

- manifest budgets and allowed providers
- local-first preference
- required output schema
- model capability requirements
- cloud opt-in state
- retry and fallback policy

Routing should be explicit and inspectable. It should not silently fall back to
a cloud provider when a local provider is unavailable unless the workflow has
explicitly allowed that behavior.

## Secrets Handling Rules

Never log, print, persist, or document:

- API keys
- provider tokens
- password-bearing DSNs
- database passwords
- raw secrets from environment variables
- private hostnames or private IPs
- sensitive raw prompts or responses unless explicitly redacted and
  artifact-controlled

Provider credentials belong only in ignored local environment files or managed
secret stores in later deployment phases. CLI output and logs should use
provider names, model names, run IDs, artifact paths, statuses, timestamps, and
redacted summaries instead of secret-bearing values.

## Relationship To LangGraph

LangGraph currently orchestrates deterministic nodes only. Future model-backed
nodes should call `ModelClient`, not provider SDKs. Graph state should carry
structured domain objects and artifact references, not loose prompt text.

See [`docs/langgraph-orchestration.md`](langgraph-orchestration.md) before
adding model-backed graph nodes.

## Intentionally Deferred

- provider SDK installation
- actual model clients
- agents
- LLM calls
- token/model invocation database tables
- cloud model execution
- OpenTelemetry spans
- production secret management
- autonomous planning
