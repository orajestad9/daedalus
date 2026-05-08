"""Model invocation observability records.

This module describes completed model-call events for future persistence and
inspection. Records intentionally store model identity, token/cost metadata, and
artifact paths, but not raw prompt text or raw model output text.
"""

from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from pathlib import Path
from uuid import UUID, uuid4

from pydantic import BaseModel, Field

from daedalus.model_clients.types import ModelProvider, ModelRequest, ModelResponse
from daedalus.orchestrator.run_lifecycle import calculate_duration_ms


class ModelInvocationStatus(StrEnum):
    """Terminal statuses for one model invocation event."""

    SUCCEEDED = "succeeded"
    FAILED = "failed"


class ModelInvocationRecord(BaseModel):
    """Machine-readable record of one completed model invocation."""

    invocation_id: UUID
    run_id: UUID
    step_id: UUID | None = None
    agent_name: str | None = None
    provider: ModelProvider
    model_name: str
    prompt_name: str
    prompt_version: str
    input_tokens: int | None = Field(default=None, ge=0)
    output_tokens: int | None = Field(default=None, ge=0)
    total_tokens: int | None = Field(default=None, ge=0)
    estimated_cost_usd: Decimal | None = Field(default=None, ge=0)
    status: ModelInvocationStatus
    started_at_utc: datetime
    completed_at_utc: datetime
    duration_ms: int = Field(ge=0)
    input_artifact_path: Path | None = None
    output_artifact_path: Path | None = None
    error_message: str | None = None

    @classmethod
    def succeeded_from_request_response(
        cls,
        *,
        request: ModelRequest,
        response: ModelResponse,
        started_at_utc: datetime,
        completed_at_utc: datetime,
        input_artifact_path: Path | None = None,
        output_artifact_path: Path | None = None,
    ) -> "ModelInvocationRecord":
        """Create a succeeded invocation record from safe request/response metadata."""
        return cls(
            invocation_id=uuid4(),
            run_id=request.run_id,
            step_id=request.step_id,
            agent_name=request.agent_name,
            provider=response.provider,
            model_name=response.model_name,
            prompt_name=request.prompt_name,
            prompt_version=request.prompt_version,
            input_tokens=response.input_tokens,
            output_tokens=response.output_tokens,
            total_tokens=response.total_tokens,
            estimated_cost_usd=response.estimated_cost_usd,
            status=ModelInvocationStatus.SUCCEEDED,
            started_at_utc=started_at_utc,
            completed_at_utc=completed_at_utc,
            duration_ms=calculate_duration_ms(started_at_utc, completed_at_utc),
            input_artifact_path=input_artifact_path or request.input_artifact_path,
            output_artifact_path=output_artifact_path or response.output_artifact_path,
        )

    @classmethod
    def failed_from_request(
        cls,
        *,
        request: ModelRequest,
        error_message: str,
        started_at_utc: datetime,
        completed_at_utc: datetime,
        input_artifact_path: Path | None = None,
    ) -> "ModelInvocationRecord":
        """Create a failed invocation record with caller-provided safe error text."""
        return cls(
            invocation_id=uuid4(),
            run_id=request.run_id,
            step_id=request.step_id,
            agent_name=request.agent_name,
            provider=request.provider,
            model_name=request.model_name,
            prompt_name=request.prompt_name,
            prompt_version=request.prompt_version,
            status=ModelInvocationStatus.FAILED,
            started_at_utc=started_at_utc,
            completed_at_utc=completed_at_utc,
            duration_ms=calculate_duration_ms(started_at_utc, completed_at_utc),
            input_artifact_path=input_artifact_path or request.input_artifact_path,
            output_artifact_path=request.output_artifact_path,
            error_message=error_message,
        )
