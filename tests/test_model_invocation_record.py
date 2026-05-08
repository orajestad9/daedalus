import json
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any, cast
from uuid import UUID, uuid4

import pytest
from pydantic import ValidationError

from daedalus.model_clients.invocation_record import (
    ModelInvocationRecord,
    ModelInvocationStatus,
)
from daedalus.model_clients.types import (
    ModelInvocationStatus as ModelResponseStatus,
    ModelProvider,
    ModelRequest,
    ModelResponse,
)


STARTED_AT = datetime(2026, 5, 8, 10, 0, tzinfo=UTC)
COMPLETED_AT = datetime(2026, 5, 8, 10, 0, 1, tzinfo=UTC)


def test_succeeded_from_request_response_creates_succeeded_record() -> None:
    request = _model_request()
    response = _model_response()

    record = ModelInvocationRecord.succeeded_from_request_response(
        request=request,
        response=response,
        started_at_utc=STARTED_AT,
        completed_at_utc=COMPLETED_AT,
    )

    assert isinstance(record.invocation_id, UUID)
    assert record.status == ModelInvocationStatus.SUCCEEDED
    assert record.error_message is None


def test_failed_from_request_creates_failed_record() -> None:
    request = _model_request()

    record = ModelInvocationRecord.failed_from_request(
        request=request,
        error_message="model call failed",
        started_at_utc=STARTED_AT,
        completed_at_utc=COMPLETED_AT,
    )

    assert isinstance(record.invocation_id, UUID)
    assert record.status == ModelInvocationStatus.FAILED
    assert record.error_message == "model call failed"


def test_succeeded_record_preserves_workflow_and_model_identity() -> None:
    run_id = uuid4()
    step_id = uuid4()
    request = _model_request(run_id=run_id, step_id=step_id)
    response = _model_response(provider=ModelProvider.FAKE, model_name="fake-review-model")

    record = ModelInvocationRecord.succeeded_from_request_response(
        request=request,
        response=response,
        started_at_utc=STARTED_AT,
        completed_at_utc=COMPLETED_AT,
    )

    assert record.run_id == run_id
    assert record.step_id == step_id
    assert record.agent_name == "review_summarizer"
    assert record.provider == ModelProvider.FAKE
    assert record.model_name == "fake-review-model"
    assert record.prompt_name == "summarize_reviews"
    assert record.prompt_version == "v1"


def test_succeeded_record_copies_token_and_cost_fields() -> None:
    response = _model_response(
        input_tokens=12,
        output_tokens=8,
        total_tokens=20,
        estimated_cost_usd=Decimal("0.002"),
    )

    record = ModelInvocationRecord.succeeded_from_request_response(
        request=_model_request(),
        response=response,
        started_at_utc=STARTED_AT,
        completed_at_utc=COMPLETED_AT,
    )

    assert record.input_tokens == 12
    assert record.output_tokens == 8
    assert record.total_tokens == 20
    assert record.estimated_cost_usd == Decimal("0.002")


def test_duration_ms_is_non_negative() -> None:
    record = ModelInvocationRecord.succeeded_from_request_response(
        request=_model_request(),
        response=_model_response(),
        started_at_utc=STARTED_AT,
        completed_at_utc=COMPLETED_AT,
    )

    assert record.duration_ms == 1000
    assert record.duration_ms >= 0


def test_input_and_output_artifact_paths_can_be_set() -> None:
    record = ModelInvocationRecord.succeeded_from_request_response(
        request=_model_request(),
        response=_model_response(),
        started_at_utc=STARTED_AT,
        completed_at_utc=COMPLETED_AT,
        input_artifact_path=Path("artifacts/custom-input.json"),
        output_artifact_path=Path("artifacts/custom-output.json"),
    )

    assert record.input_artifact_path == Path("artifacts/custom-input.json")
    assert record.output_artifact_path == Path("artifacts/custom-output.json")


def test_raw_prompt_and_response_text_are_not_serialized() -> None:
    request = _model_request(input_text="sensitive prompt text")
    response = _model_response(output_text="sensitive response text")

    record = ModelInvocationRecord.succeeded_from_request_response(
        request=request,
        response=response,
        started_at_utc=STARTED_AT,
        completed_at_utc=COMPLETED_AT,
    )

    data = cast(dict[str, Any], json.loads(record.model_dump_json()))

    assert "input_text" not in data
    assert "output_text" not in data
    assert "sensitive prompt text" not in record.model_dump_json()
    assert "sensitive response text" not in record.model_dump_json()


def test_negative_token_cost_and_duration_values_are_rejected() -> None:
    base_kwargs = {
        "invocation_id": uuid4(),
        "run_id": uuid4(),
        "provider": ModelProvider.FAKE,
        "model_name": "fake-local-model",
        "prompt_name": "summarize_reviews",
        "prompt_version": "v1",
        "status": ModelInvocationStatus.SUCCEEDED,
        "started_at_utc": STARTED_AT,
        "completed_at_utc": COMPLETED_AT,
        "duration_ms": 0,
    }

    with pytest.raises(ValidationError):
        ModelInvocationRecord.model_validate({**base_kwargs, "input_tokens": -1})
    with pytest.raises(ValidationError):
        ModelInvocationRecord.model_validate({**base_kwargs, "output_tokens": -1})
    with pytest.raises(ValidationError):
        ModelInvocationRecord.model_validate({**base_kwargs, "total_tokens": -1})
    with pytest.raises(ValidationError):
        ModelInvocationRecord.model_validate(
            {**base_kwargs, "estimated_cost_usd": Decimal("-0.01")}
        )
    with pytest.raises(ValidationError):
        ModelInvocationRecord.model_validate({**base_kwargs, "duration_ms": -1})


def test_json_serialization_uses_provider_and_status_values() -> None:
    record = ModelInvocationRecord.succeeded_from_request_response(
        request=_model_request(),
        response=_model_response(),
        started_at_utc=STARTED_AT,
        completed_at_utc=COMPLETED_AT,
    )

    data = cast(dict[str, Any], json.loads(record.model_dump_json()))

    assert data["provider"] == "fake"
    assert data["status"] == "succeeded"


def _model_request(
    *,
    run_id: UUID | None = None,
    step_id: UUID | None = None,
    input_text: str = "sample prompt text",
) -> ModelRequest:
    return ModelRequest(
        run_id=run_id or uuid4(),
        step_id=step_id,
        agent_name="review_summarizer",
        provider=ModelProvider.FAKE,
        model_name="fake-local-model",
        prompt_name="summarize_reviews",
        prompt_version="v1",
        input_text=input_text,
        input_artifact_path=Path("artifacts/input.json"),
        output_artifact_path=Path("artifacts/output.json"),
    )


def _model_response(
    *,
    provider: ModelProvider = ModelProvider.FAKE,
    model_name: str = "fake-local-model",
    output_text: str = "sample response text",
    input_tokens: int = 10,
    output_tokens: int = 5,
    total_tokens: int = 15,
    estimated_cost_usd: Decimal = Decimal("0"),
) -> ModelResponse:
    return ModelResponse(
        invocation_id=uuid4(),
        status=ModelResponseStatus.COMPLETED,
        provider=provider,
        model_name=model_name,
        output_text=output_text,
        output_artifact_path=Path("artifacts/output.json"),
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        total_tokens=total_tokens,
        estimated_cost_usd=estimated_cost_usd,
    )
