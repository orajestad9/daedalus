import json
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any, cast
from uuid import UUID, uuid4

import pytest
from pydantic import ValidationError

from daedalus.model_clients.types import (
    ModelBudget,
    ModelInvocationRecord,
    ModelInvocationStatus,
    ModelProvider,
    ModelRequest,
    ModelResponse,
)


def test_model_budget_defaults_to_local_first() -> None:
    budget = ModelBudget()

    assert budget.allow_cloud_models is False
    assert budget.allowed_providers == ()
    assert budget.max_total_tokens is None
    assert budget.max_estimated_cost_usd is None


def test_model_budget_rejects_negative_values() -> None:
    with pytest.raises(ValidationError):
        ModelBudget(max_total_tokens=-1)


def test_model_request_preserves_workflow_context_and_artifact_paths() -> None:
    run_id = uuid4()
    step_id = uuid4()

    request = _model_request(run_id=run_id, step_id=step_id)

    assert request.run_id == run_id
    assert request.step_id == step_id
    assert request.agent_name == "review_summarizer"
    assert request.provider == ModelProvider.FAKE
    assert request.model_name == "fake-local-model"
    assert request.prompt_name == "summarize_reviews"
    assert request.prompt_version == "v1"
    assert request.input_artifact_path == Path("artifacts/input.json")
    assert request.output_artifact_path == Path("artifacts/output.json")
    assert request.budget.allow_cloud_models is False


def test_model_invocation_record_start_generates_running_record() -> None:
    request = _model_request()

    record = ModelInvocationRecord.start(request)

    assert isinstance(record.invocation_id, UUID)
    assert record.run_id == request.run_id
    assert record.step_id == request.step_id
    assert record.agent_name == request.agent_name
    assert record.provider == request.provider
    assert record.model_name == request.model_name
    assert record.prompt_name == request.prompt_name
    assert record.prompt_version == request.prompt_version
    assert record.status == ModelInvocationStatus.RUNNING
    assert record.started_at_utc.tzinfo is not None
    assert record.started_at_utc.utcoffset() is not None
    assert record.completed_at_utc is None
    assert record.duration_ms is None
    assert record.input_artifact_path == request.input_artifact_path


def test_model_invocation_record_complete_preserves_original_record() -> None:
    record = ModelInvocationRecord.start(_model_request())
    response = ModelResponse(
        invocation_id=record.invocation_id,
        status=ModelInvocationStatus.COMPLETED,
        provider=record.provider,
        model_name=record.model_name,
        output_artifact_path=Path("artifacts/output.json"),
        input_tokens=10,
        output_tokens=5,
        total_tokens=15,
        estimated_cost_usd=Decimal("0.001"),
    )

    completed_record = record.complete(response)

    assert completed_record.invocation_id == record.invocation_id
    assert completed_record.status == ModelInvocationStatus.COMPLETED
    assert completed_record.completed_at_utc is not None
    assert completed_record.duration_ms is not None
    assert completed_record.duration_ms >= 0
    assert completed_record.input_tokens == 10
    assert completed_record.output_tokens == 5
    assert completed_record.total_tokens == 15
    assert completed_record.estimated_cost_usd == Decimal("0.001")
    assert completed_record.output_artifact_path == Path("artifacts/output.json")
    assert record.status == ModelInvocationStatus.RUNNING


def test_model_invocation_record_fail_preserves_original_record() -> None:
    record = ModelInvocationRecord.start(_model_request())

    failed_record = record.fail("model call failed")

    assert failed_record.invocation_id == record.invocation_id
    assert failed_record.status == ModelInvocationStatus.FAILED
    assert failed_record.completed_at_utc is not None
    assert failed_record.duration_ms is not None
    assert failed_record.duration_ms >= 0
    assert failed_record.error_message == "model call failed"
    assert record.status == ModelInvocationStatus.RUNNING


def test_model_types_json_serialize_enum_and_path_values() -> None:
    record = ModelInvocationRecord(
        invocation_id=uuid4(),
        run_id=uuid4(),
        agent_name="review_summarizer",
        provider=ModelProvider.OLLAMA,
        model_name="llama-local",
        prompt_name="summarize_reviews",
        prompt_version="v1",
        status=ModelInvocationStatus.COMPLETED,
        started_at_utc=datetime(2026, 5, 8, 10, 0, tzinfo=UTC),
        completed_at_utc=datetime(2026, 5, 8, 10, 1, tzinfo=UTC),
        duration_ms=60_000,
        input_artifact_path=Path("artifacts/input.json"),
        output_artifact_path=Path("artifacts/output.json"),
    )

    data = cast(dict[str, Any], json.loads(record.model_dump_json()))

    assert data["provider"] == "ollama"
    assert data["status"] == "completed"
    assert data["input_artifact_path"] == "artifacts/input.json"
    assert data["output_artifact_path"] == "artifacts/output.json"


def _model_request(
    *,
    run_id: UUID | None = None,
    step_id: UUID | None = None,
) -> ModelRequest:
    return ModelRequest(
        run_id=run_id or uuid4(),
        step_id=step_id,
        agent_name="review_summarizer",
        provider=ModelProvider.FAKE,
        model_name="fake-local-model",
        prompt_name="summarize_reviews",
        prompt_version="v1",
        input_artifact_path=Path("artifacts/input.json"),
        output_artifact_path=Path("artifacts/output.json"),
    )
