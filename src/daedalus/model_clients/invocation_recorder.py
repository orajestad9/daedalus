"""Service for creating and saving model invocation records."""

from datetime import datetime
from pathlib import Path
from uuid import UUID

from daedalus.memory.model_invocation_repository import ModelInvocationRepository
from daedalus.model_clients.invocation_record import ModelInvocationRecord
from daedalus.model_clients.types import ModelRequest, ModelResponse


class ModelInvocationRecorder:
    """Create safe model invocation records and persist them through a repository."""

    def __init__(self, repository: ModelInvocationRepository) -> None:
        self._repository = repository

    def record_success(
        self,
        *,
        request: ModelRequest,
        response: ModelResponse,
        started_at_utc: datetime,
        completed_at_utc: datetime,
        step_id: UUID | None = None,
        agent_name: str | None = None,
        input_artifact_path: Path | None = None,
        output_artifact_path: Path | None = None,
    ) -> ModelInvocationRecord:
        """Create, save, and return a succeeded model invocation record."""
        record = ModelInvocationRecord.succeeded_from_request_response(
            request=request,
            response=response,
            started_at_utc=started_at_utc,
            completed_at_utc=completed_at_utc,
            input_artifact_path=input_artifact_path,
            output_artifact_path=output_artifact_path,
        )
        record = _apply_context_overrides(record, step_id=step_id, agent_name=agent_name)
        self._repository.save(record)
        return record

    def record_failure(
        self,
        *,
        request: ModelRequest,
        error_message: str,
        started_at_utc: datetime,
        completed_at_utc: datetime,
        step_id: UUID | None = None,
        agent_name: str | None = None,
        input_artifact_path: Path | None = None,
        output_artifact_path: Path | None = None,
    ) -> ModelInvocationRecord:
        """Create, save, and return a failed model invocation record."""
        record = ModelInvocationRecord.failed_from_request(
            request=request,
            error_message=error_message,
            started_at_utc=started_at_utc,
            completed_at_utc=completed_at_utc,
            input_artifact_path=input_artifact_path,
        )
        record = _apply_context_overrides(record, step_id=step_id, agent_name=agent_name)
        if output_artifact_path is not None:
            record = record.model_copy(update={"output_artifact_path": output_artifact_path})

        self._repository.save(record)
        return record


def _apply_context_overrides(
    record: ModelInvocationRecord,
    *,
    step_id: UUID | None,
    agent_name: str | None,
) -> ModelInvocationRecord:
    updates: dict[str, object] = {}
    if step_id is not None:
        updates["step_id"] = step_id
    if agent_name is not None:
        updates["agent_name"] = agent_name
    if not updates:
        return record

    return record.model_copy(update=updates)
