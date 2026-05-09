from pathlib import Path
from uuid import uuid4

import pytest

from daedalus.model_clients import (
    ModelClient,
    OllamaModelClient,
    OllamaModelClientError,
)
from daedalus.model_clients.ollama_settings import OllamaModelClientSettings
from daedalus.model_clients.types import (
    ModelInvocationStatus,
    ModelProvider,
    ModelRequest,
    ModelResponse,
)


class CapturingTransport:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, object], float]] = []

    def __call__(
        self,
        url: str,
        payload: dict[str, object],
        timeout_seconds: float,
    ) -> dict[str, object]:
        self.calls.append((url, payload, timeout_seconds))
        return {
            "response": "safe local ollama response",
            "model": "llama3.1",
            "prompt_eval_count": 8,
            "eval_count": 5,
        }


def test_ollama_model_client_satisfies_model_client_protocol() -> None:
    client = OllamaModelClient(
        settings=_settings(enabled=True),
        transport=CapturingTransport(),
    )

    assert isinstance(client, ModelClient)


def test_ollama_model_client_disabled_settings_raise() -> None:
    client = OllamaModelClient(
        settings=_settings(enabled=False),
        transport=CapturingTransport(),
    )

    with pytest.raises(OllamaModelClientError, match="disabled"):
        client.complete(_model_request(input_text="compact safe input"))


def test_ollama_model_client_rejects_non_ollama_provider() -> None:
    raw_input_text = "compact safe input should not be in errors"
    client = OllamaModelClient(
        settings=_settings(enabled=True),
        transport=CapturingTransport(),
    )

    with pytest.raises(OllamaModelClientError, match="provider ollama") as exc_info:
        client.complete(
            _model_request(
                provider=ModelProvider.FAKE,
                input_text=raw_input_text,
            )
        )

    assert raw_input_text not in str(exc_info.value)


def test_ollama_model_client_complete_uses_injected_transport() -> None:
    transport = CapturingTransport()
    client = OllamaModelClient(settings=_settings(enabled=True), transport=transport)

    client.complete(_model_request(input_text="compact safe input"))

    assert len(transport.calls) == 1


def test_ollama_model_client_posts_to_api_generate() -> None:
    transport = CapturingTransport()
    client = OllamaModelClient(settings=_settings(enabled=True), transport=transport)

    client.complete(_model_request(input_text="compact safe input"))

    url, _, _ = transport.calls[0]
    assert url == "http://localhost:11434/api/generate"


def test_ollama_model_client_passes_timeout_to_transport() -> None:
    transport = CapturingTransport()
    client = OllamaModelClient(
        settings=_settings(enabled=True, request_timeout_seconds=7.5),
        transport=transport,
    )

    client.complete(_model_request(input_text="compact safe input"))

    _, _, timeout_seconds = transport.calls[0]
    assert timeout_seconds == 7.5


def test_ollama_model_client_complete_returns_ollama_model_response() -> None:
    client = OllamaModelClient(
        settings=_settings(enabled=True),
        transport=CapturingTransport(),
    )

    response = client.complete(_model_request(input_text="compact safe input"))

    assert isinstance(response, ModelResponse)
    assert response.status == ModelInvocationStatus.COMPLETED
    assert response.provider == ModelProvider.OLLAMA
    assert response.model_name == "llama3.1"


def test_ollama_model_client_maps_response_text_and_token_counts() -> None:
    client = OllamaModelClient(
        settings=_settings(enabled=True),
        transport=CapturingTransport(),
    )

    response = client.complete(_model_request(input_text="compact safe input"))

    assert response.output_text == "safe local ollama response"
    assert response.input_tokens == 8
    assert response.output_tokens == 5
    assert response.total_tokens == 13


def test_ollama_model_client_transport_receives_generate_payload() -> None:
    transport = CapturingTransport()
    client = OllamaModelClient(settings=_settings(enabled=True), transport=transport)

    client.complete(_model_request(input_text="compact safe input"))

    _, payload, _ = transport.calls[0]
    assert payload["model"] == "llama3.1"
    assert payload["prompt"] == "compact safe input"
    assert payload["stream"] is False


def test_ollama_model_client_transport_payload_omits_daedalus_context() -> None:
    transport = CapturingTransport()
    client = OllamaModelClient(settings=_settings(enabled=True), transport=transport)

    client.complete(_model_request(input_text="compact safe input"))

    _, payload, _ = transport.calls[0]
    assert "run_id" not in payload
    assert "prompt_name" not in payload
    assert "prompt_version" not in payload


def test_ollama_model_client_error_messages_do_not_include_raw_input_text() -> None:
    raw_input_text = "raw prompt text should stay out of errors"
    client = OllamaModelClient(
        settings=_settings(enabled=True),
        transport=CapturingTransport(),
    )

    with pytest.raises(OllamaModelClientError) as exc_info:
        client.complete(_model_request(model_name="", input_text=raw_input_text))

    assert raw_input_text not in str(exc_info.value)


def _settings(
    *,
    enabled: bool,
    request_timeout_seconds: float = 30.0,
) -> OllamaModelClientSettings:
    return OllamaModelClientSettings(
        enabled=enabled,
        base_url="http://localhost:11434",
        model_name="llama3.1",
        request_timeout_seconds=request_timeout_seconds,
    )


def _model_request(
    *,
    input_text: str,
    provider: ModelProvider = ModelProvider.OLLAMA,
    model_name: str = "llama3.1",
) -> ModelRequest:
    return ModelRequest(
        run_id=uuid4(),
        agent_name="review_theme_summary_agent",
        provider=provider,
        model_name=model_name,
        prompt_name="readysetrentables/review_theme_summary",
        prompt_version="v0",
        input_text=input_text,
        input_artifact_path=Path("artifacts/input.json"),
        output_artifact_path=Path("artifacts/output.md"),
    )
