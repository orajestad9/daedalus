"""Core model-client types for future Daedalus model calls.

These models define the safe boundary that future LangGraph nodes and agents
should use before any real provider SDKs are introduced. They intentionally
carry prompt identity, artifact paths, budget context, and invocation metadata
rather than raw secret-bearing provider configuration or unbounded prompt text.
"""

from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, Field

from daedalus.orchestrator.run_lifecycle import calculate_duration_ms, utc_now


class ModelProvider(StrEnum):
    """Supported provider identifiers for future model routing."""

    FAKE = "fake"
    OLLAMA = "ollama"
    OPENAI = "openai"
    ANTHROPIC = "anthropic"


class ModelInvocationStatus(StrEnum):
    """Lifecycle statuses for a single model invocation."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    BLOCKED_BUDGET = "blocked_budget"


class ModelBudget(BaseModel):
    """Per-request or manifest-level budget constraints for model calls."""

    max_input_tokens: int | None = Field(default=None, ge=0)
    max_output_tokens: int | None = Field(default=None, ge=0)
    max_total_tokens: int | None = Field(default=None, ge=0)
    max_invocations: int | None = Field(default=None, ge=0)
    max_estimated_cost_usd: Decimal | None = Field(default=None, ge=0)
    allow_cloud_models: bool = False
    allowed_providers: tuple[ModelProvider, ...] = ()


class ModelRequest(BaseModel):
    """Structured request accepted by the future shared ModelClient."""

    run_id: UUID
    step_id: UUID | None = None
    agent_name: str
    provider: ModelProvider
    model_name: str
    prompt_name: str
    prompt_version: str
    input_artifact_path: Path
    output_artifact_path: Path | None = None
    response_schema_name: str | None = None
    budget: ModelBudget = Field(default_factory=ModelBudget)
    metadata: dict[str, str] = Field(default_factory=dict)


class ModelResponse(BaseModel):
    """Structured response returned by the future shared ModelClient."""

    invocation_id: UUID
    status: ModelInvocationStatus
    provider: ModelProvider
    model_name: str
    output_artifact_path: Path | None = None
    structured_output: dict[str, Any] | None = None
    input_tokens: int | None = Field(default=None, ge=0)
    output_tokens: int | None = Field(default=None, ge=0)
    total_tokens: int | None = Field(default=None, ge=0)
    estimated_cost_usd: Decimal | None = Field(default=None, ge=0)
    error_message: str | None = None


class ModelInvocationRecord(BaseModel):
    """Auditable record for one model invocation attached to workflow context."""

    invocation_id: UUID
    run_id: UUID
    step_id: UUID | None = None
    agent_name: str
    provider: ModelProvider
    model_name: str
    prompt_name: str
    prompt_version: str
    status: ModelInvocationStatus
    started_at_utc: datetime
    completed_at_utc: datetime | None = None
    duration_ms: int | None = Field(default=None, ge=0)
    input_tokens: int | None = Field(default=None, ge=0)
    output_tokens: int | None = Field(default=None, ge=0)
    total_tokens: int | None = Field(default=None, ge=0)
    estimated_cost_usd: Decimal | None = Field(default=None, ge=0)
    input_artifact_path: Path
    output_artifact_path: Path | None = None
    error_message: str | None = None

    @classmethod
    def start(cls, request: ModelRequest) -> "ModelInvocationRecord":
        """Create a running invocation record from a model request."""
        return cls(
            invocation_id=uuid4(),
            run_id=request.run_id,
            step_id=request.step_id,
            agent_name=request.agent_name,
            provider=request.provider,
            model_name=request.model_name,
            prompt_name=request.prompt_name,
            prompt_version=request.prompt_version,
            status=ModelInvocationStatus.RUNNING,
            started_at_utc=utc_now(),
            input_artifact_path=request.input_artifact_path,
            output_artifact_path=request.output_artifact_path,
        )

    def complete(self, response: ModelResponse) -> "ModelInvocationRecord":
        """Return a completed invocation record using response metadata."""
        completed_at_utc = utc_now()
        return self.model_copy(
            update={
                "status": ModelInvocationStatus.COMPLETED,
                "completed_at_utc": completed_at_utc,
                "duration_ms": calculate_duration_ms(self.started_at_utc, completed_at_utc),
                "input_tokens": response.input_tokens,
                "output_tokens": response.output_tokens,
                "total_tokens": response.total_tokens,
                "estimated_cost_usd": response.estimated_cost_usd,
                "output_artifact_path": response.output_artifact_path,
                "error_message": None,
            }
        )

    def fail(self, error_message: str) -> "ModelInvocationRecord":
        """Return a failed invocation record while preserving workflow context."""
        completed_at_utc = utc_now()
        return self.model_copy(
            update={
                "status": ModelInvocationStatus.FAILED,
                "completed_at_utc": completed_at_utc,
                "duration_ms": calculate_duration_ms(self.started_at_utc, completed_at_utc),
                "error_message": error_message,
            }
        )
