from pathlib import Path
from uuid import uuid4

from daedalus.model_clients import ModelClient
from daedalus.model_clients.types import (
    ModelInvocationStatus,
    ModelProvider,
    ModelRequest,
    ModelResponse,
)


class InTestModelClient:
    def complete(self, request: ModelRequest) -> ModelResponse:
        return ModelResponse(
            invocation_id=uuid4(),
            status=ModelInvocationStatus.COMPLETED,
            provider=request.provider,
            model_name=request.model_name,
            output_artifact_path=request.output_artifact_path,
            structured_output={"ok": True},
        )


class MissingComplete:
    pass


def test_class_implementing_complete_satisfies_model_client_protocol() -> None:
    client = InTestModelClient()

    assert isinstance(client, ModelClient)


def test_model_client_complete_accepts_request_and_returns_response() -> None:
    client: ModelClient = InTestModelClient()
    request = _model_request()

    response = client.complete(request)

    assert response.status == ModelInvocationStatus.COMPLETED
    assert response.provider == request.provider
    assert response.model_name == request.model_name
    assert response.output_artifact_path == request.output_artifact_path
    assert response.structured_output == {"ok": True}


def test_class_without_complete_does_not_satisfy_model_client_protocol() -> None:
    client = MissingComplete()

    assert not isinstance(client, ModelClient)


def _model_request() -> ModelRequest:
    return ModelRequest(
        run_id=uuid4(),
        agent_name="review_summarizer",
        provider=ModelProvider.FAKE,
        model_name="fake-local-model",
        prompt_name="summarize_reviews",
        prompt_version="v1",
        input_artifact_path=Path("artifacts/input.json"),
        output_artifact_path=Path("artifacts/output.json"),
    )
