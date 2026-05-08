import json
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any, cast
from uuid import UUID, uuid4

from daedalus.model_clients.invocation_record import (
    ModelInvocationRecord,
    ModelInvocationStatus,
)
from daedalus.model_clients.invocation_recorder import ModelInvocationRecorder
from daedalus.model_clients.types import (
    ModelInvocationStatus as ModelResponseStatus,
    ModelProvider,
    ModelRequest,
    ModelResponse,
)


STARTED_AT = datetime(2026, 5, 8, 10, 0, tzinfo=UTC)
COMPLETED_AT = datetime(2026, 5, 8, 10, 0, 1, tzinfo=UTC)


def test_record_success_saves_one_record() -> None:
    repository = FakeModelInvocationRepository()
    recorder = ModelInvocationRecorder(cast(Any, repository))

    recorder.record_success(
        request=_model_request(),
        response=_model_response(),
        started_at_utc=STARTED_AT,
        completed_at_utc=COMPLETED_AT,
    )

    assert len(repository.saved_records) == 1


def test_record_success_returns_saved_record() -> None:
    repository = FakeModelInvocationRepository()
    recorder = ModelInvocationRecorder(cast(Any, repository))

    record = recorder.record_success(
        request=_model_request(),
        response=_model_response(),
        started_at_utc=STARTED_AT,
        completed_at_utc=COMPLETED_AT,
    )

    assert repository.saved_records == [record]


def test_record_success_preserves_identity_and_status() -> None:
    run_id = uuid4()
    request = _model_request(run_id=run_id)
    response = _model_response(provider=ModelProvider.FAKE, model_name="fake-review-model")
    recorder = ModelInvocationRecorder(cast(Any, FakeModelInvocationRepository()))

    record = recorder.record_success(
        request=request,
        response=response,
        started_at_utc=STARTED_AT,
        completed_at_utc=COMPLETED_AT,
    )

    assert record.status == ModelInvocationStatus.SUCCEEDED
    assert record.run_id == run_id
    assert record.provider == ModelProvider.FAKE
    assert record.model_name == "fake-review-model"
    assert record.prompt_name == "summarize_reviews"
    assert record.prompt_version == "v1"


def test_record_success_copies_token_and_cost_fields() -> None:
    response = _model_response(
        input_tokens=12,
        output_tokens=8,
        total_tokens=20,
        estimated_cost_usd=Decimal("0.002"),
    )
    recorder = ModelInvocationRecorder(cast(Any, FakeModelInvocationRepository()))

    record = recorder.record_success(
        request=_model_request(),
        response=response,
        started_at_utc=STARTED_AT,
        completed_at_utc=COMPLETED_AT,
    )

    assert record.input_tokens == 12
    assert record.output_tokens == 8
    assert record.total_tokens == 20
    assert record.estimated_cost_usd == Decimal("0.002")


def test_record_success_includes_optional_context_overrides() -> None:
    step_id = uuid4()
    recorder = ModelInvocationRecorder(cast(Any, FakeModelInvocationRepository()))

    record = recorder.record_success(
        request=_model_request(),
        response=_model_response(),
        started_at_utc=STARTED_AT,
        completed_at_utc=COMPLETED_AT,
        step_id=step_id,
        agent_name="override_agent",
        input_artifact_path=Path("artifacts/custom-input.json"),
        output_artifact_path=Path("artifacts/custom-output.json"),
    )

    assert record.step_id == step_id
    assert record.agent_name == "override_agent"
    assert record.input_artifact_path == Path("artifacts/custom-input.json")
    assert record.output_artifact_path == Path("artifacts/custom-output.json")


def test_record_failure_saves_one_record_and_sets_failure_fields() -> None:
    repository = FakeModelInvocationRepository()
    recorder = ModelInvocationRecorder(cast(Any, repository))

    record = recorder.record_failure(
        request=_model_request(),
        error_message="model call failed",
        started_at_utc=STARTED_AT,
        completed_at_utc=COMPLETED_AT,
    )

    assert repository.saved_records == [record]
    assert record.status == ModelInvocationStatus.FAILED
    assert record.error_message == "model call failed"


def test_record_failure_includes_optional_context_overrides() -> None:
    step_id = uuid4()
    recorder = ModelInvocationRecorder(cast(Any, FakeModelInvocationRepository()))

    record = recorder.record_failure(
        request=_model_request(),
        error_message="model call failed",
        started_at_utc=STARTED_AT,
        completed_at_utc=COMPLETED_AT,
        step_id=step_id,
        agent_name="override_agent",
        input_artifact_path=Path("artifacts/custom-input.json"),
        output_artifact_path=Path("artifacts/custom-output.json"),
    )

    assert record.step_id == step_id
    assert record.agent_name == "override_agent"
    assert record.input_artifact_path == Path("artifacts/custom-input.json")
    assert record.output_artifact_path == Path("artifacts/custom-output.json")


def test_raw_request_input_text_is_not_in_serialized_failure_record() -> None:
    recorder = ModelInvocationRecorder(cast(Any, FakeModelInvocationRepository()))

    record = recorder.record_failure(
        request=_model_request(input_text="sensitive prompt text"),
        error_message="model call failed",
        started_at_utc=STARTED_AT,
        completed_at_utc=COMPLETED_AT,
    )

    data = cast(dict[str, Any], json.loads(record.model_dump_json()))

    assert "input_text" not in data
    assert "sensitive prompt text" not in record.model_dump_json()


def test_raw_response_output_text_is_not_in_serialized_success_record() -> None:
    recorder = ModelInvocationRecorder(cast(Any, FakeModelInvocationRepository()))

    record = recorder.record_success(
        request=_model_request(),
        response=_model_response(output_text="sensitive response text"),
        started_at_utc=STARTED_AT,
        completed_at_utc=COMPLETED_AT,
    )

    data = cast(dict[str, Any], json.loads(record.model_dump_json()))

    assert "output_text" not in data
    assert "sensitive response text" not in record.model_dump_json()


class FakeModelInvocationRepository:
    def __init__(self) -> None:
        self.saved_records: list[ModelInvocationRecord] = []

    def save(self, record: ModelInvocationRecord) -> None:
        self.saved_records.append(record)


def _model_request(
    *,
    run_id: UUID | None = None,
    input_text: str = "sample prompt text",
) -> ModelRequest:
    return ModelRequest(
        run_id=run_id or uuid4(),
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
