import json
from pathlib import Path
from typing import Any, cast
from uuid import UUID, uuid4

import pytest

from daedalus.model_clients import FakeModelClient, ModelClient, RecordingModelClient
from daedalus.model_clients.invocation_record import (
    ModelInvocationRecord,
    ModelInvocationStatus,
)
from daedalus.model_clients.invocation_recorder import ModelInvocationRecorder
from daedalus.model_clients.types import ModelProvider, ModelRequest, ModelResponse


def test_recording_model_client_satisfies_model_client_protocol() -> None:
    client = _recording_client()

    assert isinstance(client, ModelClient)


def test_recording_model_client_complete_returns_inner_response() -> None:
    client = _recording_client(inner_client=FakeModelClient(output_text="inner response"))

    response = client.complete(_model_request())

    assert response.output_text == "inner response"


def test_successful_call_records_one_succeeded_invocation() -> None:
    repository = FakeModelInvocationRepository()
    client = _recording_client(repository=repository)

    client.complete(_model_request())

    assert len(repository.saved_records) == 1
    assert repository.saved_records[0].status == ModelInvocationStatus.SUCCEEDED


def test_recorded_success_preserves_identity() -> None:
    run_id = uuid4()
    repository = FakeModelInvocationRepository()
    request = _model_request(run_id=run_id, model_name="fake-review-model")
    client = _recording_client(repository=repository)

    client.complete(request)

    record = repository.saved_records[0]
    assert record.run_id == run_id
    assert record.provider == ModelProvider.FAKE
    assert record.model_name == "fake-review-model"
    assert record.prompt_name == "summarize_reviews"
    assert record.prompt_version == "v1"


def test_recorded_success_includes_context_overrides() -> None:
    step_id = uuid4()
    repository = FakeModelInvocationRepository()
    client = _recording_client(
        repository=repository,
        step_id=step_id,
        agent_name="override_agent",
        input_artifact_path=Path("artifacts/custom-input.json"),
        output_artifact_path=Path("artifacts/custom-output.json"),
    )

    client.complete(_model_request())

    record = repository.saved_records[0]
    assert record.step_id == step_id
    assert record.agent_name == "override_agent"
    assert record.input_artifact_path == Path("artifacts/custom-input.json")
    assert record.output_artifact_path == Path("artifacts/custom-output.json")


def test_failed_inner_client_records_one_failed_invocation() -> None:
    repository = FakeModelInvocationRepository()
    client = _recording_client(
        inner_client=FailingModelClient(),
        repository=repository,
    )

    with pytest.raises(RuntimeError, match="inner model failed"):
        client.complete(_model_request())

    assert len(repository.saved_records) == 1
    assert repository.saved_records[0].status == ModelInvocationStatus.FAILED
    assert repository.saved_records[0].error_message == "inner model failed"


def test_failed_inner_client_reraises_original_exception() -> None:
    client = _recording_client(inner_client=FailingModelClient())

    with pytest.raises(RuntimeError) as exc_info:
        client.complete(_model_request())

    assert str(exc_info.value) == "inner model failed"


def test_raw_request_input_text_is_not_in_serialized_record() -> None:
    repository = FakeModelInvocationRepository()
    client = _recording_client(repository=repository)

    client.complete(_model_request(input_text="sensitive prompt text"))

    serialized_record = repository.saved_records[0].model_dump_json()
    data = cast(dict[str, Any], json.loads(serialized_record))
    assert "input_text" not in data
    assert "sensitive prompt text" not in serialized_record


def test_raw_response_output_text_is_not_in_serialized_record() -> None:
    repository = FakeModelInvocationRepository()
    client = _recording_client(
        inner_client=FakeModelClient(output_text="sensitive response text"),
        repository=repository,
    )

    client.complete(_model_request())

    serialized_record = repository.saved_records[0].model_dump_json()
    data = cast(dict[str, Any], json.loads(serialized_record))
    assert "output_text" not in data
    assert "sensitive response text" not in serialized_record


class FailingModelClient:
    def complete(self, request: ModelRequest) -> ModelResponse:
        raise RuntimeError("inner model failed")


class FakeModelInvocationRepository:
    def __init__(self) -> None:
        self.saved_records: list[ModelInvocationRecord] = []

    def save(self, record: ModelInvocationRecord) -> None:
        self.saved_records.append(record)


def _recording_client(
    *,
    inner_client: ModelClient | None = None,
    repository: FakeModelInvocationRepository | None = None,
    step_id: UUID | None = None,
    agent_name: str | None = None,
    input_artifact_path: Path | None = None,
    output_artifact_path: Path | None = None,
) -> RecordingModelClient:
    recorder = ModelInvocationRecorder(cast(Any, repository or FakeModelInvocationRepository()))
    return RecordingModelClient(
        inner_client=inner_client or FakeModelClient(),
        recorder=recorder,
        step_id=step_id,
        agent_name=agent_name,
        input_artifact_path=input_artifact_path,
        output_artifact_path=output_artifact_path,
    )


def _model_request(
    *,
    run_id: UUID | None = None,
    input_text: str = "sample prompt text",
    model_name: str = "fake-local-model",
) -> ModelRequest:
    return ModelRequest(
        run_id=run_id or uuid4(),
        agent_name="review_summarizer",
        provider=ModelProvider.FAKE,
        model_name=model_name,
        prompt_name="summarize_reviews",
        prompt_version="v1",
        input_text=input_text,
        input_artifact_path=Path("artifacts/input.json"),
        output_artifact_path=Path("artifacts/output.json"),
    )
