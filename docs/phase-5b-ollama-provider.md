# Phase 5B Ollama Provider Design

Phase 5B designs the first real local provider adapter for Daedalus:
`OllamaModelClient`. This phase comes after the fake LangGraph review theme
summary path because Daedalus already has the safer pieces working first:
`ModelClient`, `FakeModelClient`, `RecordingModelClient`, budget validation,
model invocation records, prompt templates, artifact writing, and persisted
`show-run` inspection.

The goal is to replace fake model behavior behind the same protocol in a later
implementation step, not to change workflow routing, add cloud providers, or
introduce autonomous behavior.

No implementation code, provider SDK dependencies, network calls, real LLM
calls, OpenTelemetry, migrations, cloud model usage, or workflow wiring should
be added by this design document.

## Why Ollama Comes After The Fake Graph Path

The fake graph path proves the workflow shape without provider risk:

- graph nodes preserve `run_id`, workflow steps, artifacts, and approval flags
- `ReviewThemeSummaryAgent` already depends on `ModelClient`
- fake model invocation records are persisted only at the explicit `--persist`
  boundary
- `review_theme_summary.md` is written as an artifact
- `show-run` can inspect artifact records and model invocation metadata

Ollama should come next because it is local-first and does not require API keys.
It lets Daedalus test a real model boundary while keeping data on the developer
machine.

## Proposed Classes

Phase 5B now includes the typed settings model
`OllamaModelClientSettings` and pure Ollama generate-response parsing helpers.
The real client and HTTP calls are still intentionally deferred.

### `OllamaModelClient`

`OllamaModelClient` should implement:

```text
ModelClient.complete(request: ModelRequest) -> ModelResponse
```

It should accept a structured `ModelRequest`, call a local Ollama HTTP endpoint,
and return a structured `ModelResponse` with provider, model, output text,
status, token metadata when available, and safe error information when needed.

### `OllamaModelClientSettings`

The settings model is explicit and local by default:

- `base_url`
- `model_name`
- `request_timeout_seconds`
- `enabled`

Current safe defaults are local and fail closed:

- `base_url`: `http://localhost:11434`
- `enabled`: `false` unless explicitly configured

No API key should be required for Ollama.

## Responsibilities

`OllamaModelClient` should:

- satisfy the existing `ModelClient` protocol
- accept `ModelRequest`
- return `ModelResponse`
- use the model name from settings or the request according to a clear policy
- send requests only to the configured local Ollama base URL
- use an explicit request timeout
- handle connection failures with clear, safe errors
- map provider responses into Daedalus model-client types
- avoid printing raw prompt text or raw model output text
- avoid storing raw prompts or raw responses in Postgres
- use Python standard library HTTP support if practical, or existing project
  dependencies only

`OllamaModelClient` should not:

- enforce persistence directly
- open database connections
- know about workflow manifests or CLI routing
- write workflow artifacts by itself
- call cloud providers
- require API keys
- import OpenAI, Anthropic, or other cloud SDKs
- silently fall back to a cloud provider
- log raw prompts, raw model output text, review datasets, or artifact contents

## ModelClient Boundary

Agents and graph nodes should continue to depend on `ModelClient`, not on
Ollama-specific code. A future graph node or CLI command can choose:

```text
ReviewThemeSummaryAgent
  -> RecordingModelClient
  -> OllamaModelClient
  -> local Ollama HTTP endpoint
```

The agent should not need to know whether the model client is fake or Ollama.
The response should still become a `ReviewThemeSummaryResult`, and the markdown
writer should still produce `review_theme_summary.md`.

## Recording And Persistence

`OllamaModelClient` should not persist invocation rows itself. Persistence
should remain the responsibility of `RecordingModelClient`,
`ModelInvocationRecorder`, and the existing persistence service.

When `RecordingModelClient` wraps `OllamaModelClient`, successful and failed
calls should produce `ModelInvocationRecord` metadata with:

- `run_id`
- `step_id` when available
- `agent_name`
- `provider=ollama`
- `model_name`
- `prompt_name`
- `prompt_version`
- token counts when available
- estimated cost, likely zero or `None` for local Ollama unless a local cost
  policy is introduced
- status
- timestamps and `duration_ms`
- input and output artifact paths

Raw prompt text and raw model output text should not be stored in
`model_invocations`.

## Budget Validation

Budget validation should continue to happen through `RecordingModelClient` and
`validate_model_budget(...)`. The Ollama adapter can populate token fields when
Ollama provides enough metadata. If usage fields are unavailable, the current
budget helper should keep its established behavior for `None` response fields.

Provider policy should still require explicit local-provider opt-in. Cloud
provider opt-in must remain separate and disabled by default.

## Prompt Templates

The review theme summary agent should keep loading versioned prompt templates
with:

- `prompt_name=readysetrentables/review_theme_summary`
- `prompt_version=v0`

Prompt text can be included in the local request to Ollama, but it must not be
printed, logged, or stored in Postgres. Prompt identity should be recorded as
metadata through `ModelInvocationRecord`.

## Review Theme Summary Integration

The first real local usage should be the existing review theme summary agent.
The future switch should be small:

```text
FakeModelClient
  -> OllamaModelClient
```

The rest of the path should remain stable:

- deterministic review normalization
- compact review theme summary input
- `ReviewThemeSummaryAgent`
- `RecordingModelClient`
- `ReviewThemeSummaryResult`
- `review_theme_summary.md`
- `ArtifactType.REVIEW_THEME_SUMMARY`
- `ModelInvocationRecord`
- `show-run`

LangGraph should continue to keep persistence outside graph nodes. A graph node
may carry invocation records in state, but database writes should happen only at
the explicit persistence boundary.

## Configuration Strategy

Ollama configuration should be explicit and local. A future settings loader may
read ignored local environment values such as whether Ollama is enabled, which
local model to use, and the request timeout. Documentation and tests should use
placeholder values only.

Recommended future settings fields:

- `base_url`
- `model_name`
- `request_timeout_seconds`
- `enabled`

The implementation should fail closed when `enabled` is false. Missing local
Ollama or missing model availability should produce clear errors without
suggesting cloud fallback.

## Timeout And Error Handling

The adapter should use an explicit timeout for every request. Error handling
should distinguish:

- Ollama disabled by configuration
- connection refused or unavailable local service
- request timeout
- model not found or unavailable
- invalid or unexpected response shape
- provider response error

Errors should be safe for invocation metadata and CLI display. They should not
include raw prompts, raw model output text, credentials, DSNs, hostnames beyond
safe local placeholders, or full response bodies.

## Model Availability Checks

Before real usage, Daedalus should have a lightweight way to verify that the
configured local model is available. This should be optional and local-only. It
should not be part of `make check` because `make check` must not require a live
Ollama service.

An optional future target such as `ollama-local-check` may verify:

- Ollama is enabled locally
- the local endpoint is reachable
- the configured model is available
- a small synthetic request works
- no raw prompt or raw response text is printed

## Testing Strategy

Unit tests for `OllamaModelClient` should use mocked HTTP. They should not
require a live Ollama process, network access, model downloads, Docker, or
provider SDKs.

Tests should cover:

- `OllamaModelClient` satisfies `ModelClient`
- disabled settings fail clearly before HTTP
- request body maps from `ModelRequest`
- response body maps into `ModelResponse`
- timeout and connection failures produce safe errors
- missing model errors are clear
- raw prompt text is not logged or included in exception messages
- raw model output text is not logged or included in exception messages
- budget behavior remains covered through `RecordingModelClient`

Optional integration tests or local checks can require a developer-managed
Ollama process, but they must not run as part of `make check`.

## Acceptance Criteria Before Real Ollama Usage

Before Daedalus uses a real local Ollama call in a workflow or graph path:

- the fake path remains passing
- `graph-fake-summary-check` remains passing
- `make check` remains DB-free and Ollama-free
- Ollama client unit tests use mocked HTTP
- no live Ollama requirement is introduced into `make check`
- an optional `ollama-local-check` can require local Ollama
- no provider SDK dependencies are added unless a later task explicitly narrows
  that decision
- no OpenAI or Anthropic integration is added
- no cloud provider fallback exists
- invocation records still store metadata only
- raw prompts, raw model output text, review datasets, and artifact contents are
  not printed or blindly persisted

## Security Rules

Ollama is local-first, but it still handles model inputs and outputs. The same
Daedalus security rules apply:

- do not commit real secrets
- do not document real `.env` values
- do not log API keys, tokens, password-bearing DSNs, private hosts, private IPs,
  or machine-specific values
- do not print raw prompt text
- do not print raw model output text
- do not print raw review datasets
- do not store raw prompt or response bodies in Postgres
- do not add cloud model usage in Phase 5B

## Intentionally Deferred

- `OllamaModelClient` implementation
- `OllamaModelClientSettings` implementation
- workflow or LangGraph wiring to Ollama
- live Ollama local checks
- model download or model-management commands
- OpenAI provider
- Anthropic provider
- cloud model execution
- provider SDK dependencies
- OpenTelemetry
- Kubernetes or production deployment

## Related Documents

- [`docs/model-client-architecture.md`](model-client-architecture.md)
- [`docs/review-theme-summary-agent.md`](review-theme-summary-agent.md)
- [`docs/phase-5a-fake-agent-langgraph.md`](phase-5a-fake-agent-langgraph.md)
- [`docs/token-cost-governance.md`](token-cost-governance.md)
- [`docs/observability.md`](observability.md)
