from decimal import Decimal
from pathlib import Path
from uuid import uuid4

from daedalus.model_clients import FakeModelClient, ModelClient
from daedalus.model_clients.types import (
    ModelInvocationStatus,
    ModelProvider,
    ModelRequest,
    ModelResponse,
)


def test_fake_model_client_satisfies_model_client_protocol() -> None:
    client = FakeModelClient()

    assert isinstance(client, ModelClient)


def test_fake_model_client_complete_returns_model_response() -> None:
    client = FakeModelClient()

    response = client.complete(_model_request())

    assert isinstance(response, ModelResponse)
    assert response.status == ModelInvocationStatus.COMPLETED


def test_fake_model_client_response_uses_fake_provider_and_preserves_model_name() -> None:
    request = _model_request(model_name="fake-review-model")
    client = FakeModelClient()

    response = client.complete(request)

    assert response.provider == ModelProvider.FAKE
    assert response.model_name == "fake-review-model"


def test_fake_model_client_output_text_is_deterministic() -> None:
    client = FakeModelClient()
    request = _model_request()

    first_response = client.complete(request)
    second_response = client.complete(request)

    assert first_response.output_text == "fake model response"
    assert second_response.output_text == "fake model response"


def test_fake_model_client_populates_token_counts() -> None:
    client = FakeModelClient()

    response = client.complete(_model_request(input_text="one two three"))

    assert response.input_tokens == 3
    assert response.output_tokens == 3
    assert response.total_tokens == 6


def test_fake_model_client_total_tokens_equals_input_plus_output_tokens() -> None:
    client = FakeModelClient(input_tokens=11, output_tokens=7)

    response = client.complete(_model_request())

    assert response.input_tokens == 11
    assert response.output_tokens == 7
    assert response.total_tokens == 18


def test_fake_model_client_estimated_cost_defaults_to_zero() -> None:
    client = FakeModelClient()

    response = client.complete(_model_request())

    assert response.estimated_cost_usd == Decimal("0")


def test_fake_model_client_uses_custom_output_text() -> None:
    client = FakeModelClient(output_text="custom deterministic response")

    response = client.complete(_model_request())

    assert response.output_text == "custom deterministic response"
    assert response.output_tokens == 3


def _model_request(
    *,
    input_text: str = "sample model input",
    model_name: str = "fake-local-model",
) -> ModelRequest:
    return ModelRequest(
        run_id=uuid4(),
        agent_name="review_summarizer",
        provider=ModelProvider.FAKE,
        model_name=model_name,
        prompt_name="summarize_reviews",
        prompt_version="v1",
        input_text=input_text,
        input_artifact_path=Path("artifacts/input.json"),
        output_artifact_path=Path("artifacts/output.json"),
    )
