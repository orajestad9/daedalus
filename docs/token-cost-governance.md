# Token And Cost Governance

Daedalus will eventually coordinate agents, model clients, validators, approval
gates, and persistence. Token and cost governance must exist before those pieces
start calling LLM providers, because every model invocation can affect privacy,
latency, reproducibility, and operating cost.

This document defines the design baseline. It is not implementation code, and it
does not add model clients, agents, LangGraph, OpenTelemetry, or database tables.

## Why Governance Matters

Daedalus is local-first and human-approved. Model calls should be deliberate,
observable, bounded, and attached to workflow context. Without shared rules,
future agents could duplicate work, send excessive context to cloud providers,
skip approval constraints, or make costs hard to explain after a run completes.

Governance gives Daedalus a common contract for future phases:

- prefer deterministic work before probabilistic work
- keep cloud-model usage explicit
- connect every model call to a `run_id`
- record enough metadata to audit behavior and estimate cost
- avoid storing or logging secrets and sensitive raw prompts blindly

## Local-First Model Strategy

Daedalus should prefer local deterministic processing and local models whenever
they can satisfy the workflow quality bar. Cloud models should be opt-in at the
workflow or environment level, not an accidental default.

Future manifests should be able to describe whether cloud model calls are
allowed, which providers or model classes are acceptable, and what budgets apply.
If a workflow has not opted into cloud model usage, future agents and model
clients should fail closed instead of silently calling a provider.

## Deterministic Preprocessing Before Model Calls

Before any model invocation, workflows should reduce inputs with deterministic
Python code where possible. Examples include CSV parsing, normalization,
validation, filtering empty records, de-duplicating rows, extracting known fields,
and writing compact JSON artifacts.

Model calls should consume the smallest faithful artifact needed for the task,
not raw files or full workflow history by default.

## Model Invocation Tracking Requirements

Every future model invocation should be tracked as a first-class event connected
to a workflow run. The record should support audit, debugging, cost estimation,
budget enforcement, and later observability integrations.

At minimum, each invocation should eventually record:

- invocation identity
- workflow `run_id`
- agent or component name
- provider and model name
- prompt name and prompt version
- status
- start and completion timestamps
- token counts
- estimated cost
- input and output artifact paths when artifacts are written

Tracking should avoid full password-bearing DSNs, API keys, tokens, and sensitive
raw prompts or responses. If raw prompt or response retention is ever needed, it
should be explicit, redacted where appropriate, and governed by workflow policy.

## Token And Cost Fields

Future model-call records should include fields like:

- `input_tokens`
- `output_tokens`
- `total_tokens`
- `estimated_cost_usd`
- `provider`
- `model_name`
- `prompt_name`
- `prompt_version`
- `status`

Cost should be treated as an estimate unless provider billing reconciliation is
added later. Missing token data should be represented explicitly instead of
inventing values.

## Manifest-Level Budgets

Workflow manifests should eventually support token and cost budgets. Example
budget concepts include:

- maximum total tokens per workflow run
- maximum model invocations per workflow run
- maximum estimated cost in USD
- allowed providers
- allowed model names or model tiers
- whether cloud model usage is allowed

Budget checks should happen before a call is made whenever possible. If a call
would exceed the manifest budget, Daedalus should block it with a clear status
and preserve enough context for human review.

## Cloud Model Opt-In Behavior

Cloud provider calls must be opt-in. Future configuration should make it obvious
when a workflow can send data outside the local machine.

Recommended behavior:

- local deterministic code always remains available
- local models are preferred when suitable
- cloud models require explicit workflow or environment permission
- missing cloud opt-in fails closed
- approval gates can be required before cloud calls for sensitive workflows

## Prompt And Version Tracking

Prompts should have stable names and versions. A model invocation should record
the prompt name and prompt version so a future developer, reviewer, or agent can
understand which instruction set produced an output.

Prompt changes should be treated like code changes when they affect behavior.
Future prompt artifacts should be reviewable and should avoid embedding secrets.

## Caching Strategy

Daedalus should cache model results only when the cache key is safe and
meaningful. A future cache key might include:

- provider
- model name
- prompt name
- prompt version
- normalized input artifact hash
- relevant model parameters

Caches must not leak sensitive prompts, raw private data, API keys, or
password-bearing connection strings. Cached outputs should still attach to
`run_id` when reused so audit trails remain understandable.

## Structured-Output Requirements

Future model clients should prefer structured outputs over free-form text.
Structured outputs make validation, persistence, approval review, and retry
behavior easier to reason about.

When possible, model outputs should be written as artifacts and validated before
downstream workflow steps consume them.

## Token Reduction Patterns

- deterministic preprocessing
- compact JSON artifacts
- chunking with care
- representative samples
- local model first
- structured outputs
- prompt caching
- summary handoffs instead of full-history handoffs

## Rules For Future Agents

- agents must not call providers directly
- all model calls must go through a shared `ModelClient` abstraction
- all model calls must attach to `run_id`
- all model calls must respect manifest budgets
- model outputs should be written as artifacts

## Future `model_invocations` Table Concept

A future migration may add a table shaped roughly like this:

```sql
CREATE TABLE model_invocations (
    invocation_id UUID PRIMARY KEY,
    run_id UUID NOT NULL REFERENCES workflow_runs(run_id) ON DELETE CASCADE,
    agent_name TEXT NOT NULL,
    provider TEXT NOT NULL,
    model_name TEXT NOT NULL,
    prompt_name TEXT NOT NULL,
    prompt_version TEXT NOT NULL,
    input_tokens INTEGER,
    output_tokens INTEGER,
    total_tokens INTEGER,
    estimated_cost_usd NUMERIC(12, 6),
    status TEXT NOT NULL,
    started_at_utc TIMESTAMPTZ NOT NULL,
    completed_at_utc TIMESTAMPTZ,
    input_artifact_path TEXT,
    output_artifact_path TEXT
);
```

This is a design sketch only. Do not add this migration until model invocation
tracking is ready to be implemented.

## What Must Never Be Logged

Daedalus must never log or blindly persist:

- passwords
- API keys
- provider tokens
- password-bearing DSNs
- private IPs or machine-specific hostnames
- raw secrets from environment variables
- sensitive raw prompts or responses without explicit retention policy
- private customer data that has not been minimized, redacted, or approved for
  retention

Logs and database records should favor IDs, artifact paths, redacted summaries,
token counts, statuses, and timestamps over raw sensitive payloads.
