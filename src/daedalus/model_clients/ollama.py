"""Local Ollama ModelClient implementation.

The client keeps provider-specific HTTP details behind the shared ModelClient
protocol. It is disabled unless configured, uses injectable transport for
tests, and avoids logging or surfacing raw prompt/model payload contents.
"""

import json
import urllib.error
import urllib.request
from collections.abc import Callable
from typing import Any

from daedalus.model_clients.ollama_request import (
    ollama_generate_payload_from_model_request,
)
from daedalus.model_clients.ollama_response import (
    model_response_from_ollama_generate_payload,
)
from daedalus.model_clients.ollama_settings import OllamaModelClientSettings
from daedalus.model_clients.types import ModelProvider, ModelRequest, ModelResponse

OllamaTransport = Callable[[str, dict[str, object], float], dict[str, object]]


OLLAMA_REQUEST_TIMEOUT_MESSAGE = "Ollama generate request timed out."


class OllamaModelClientError(RuntimeError):
    """Raised for safe Ollama client configuration, transport, or parsing errors."""


class OllamaModelClient:
    """ModelClient adapter for a local Ollama `/api/generate` endpoint."""

    def __init__(
        self,
        *,
        settings: OllamaModelClientSettings,
        transport: OllamaTransport | None = None,
    ) -> None:
        self._settings = settings
        self._transport = transport or _default_ollama_generate_transport

    def complete(self, request: ModelRequest) -> ModelResponse:
        """Complete one Ollama model request using local `/api/generate`."""
        if not self._settings.enabled:
            msg = "OllamaModelClient is disabled by configuration."
            raise OllamaModelClientError(msg)
        if request.provider != ModelProvider.OLLAMA:
            msg = "OllamaModelClient only accepts requests for provider ollama."
            raise OllamaModelClientError(msg)

        try:
            payload = ollama_generate_payload_from_model_request(request)
        except ValueError as exc:
            msg = "OllamaModelClient request validation failed."
            raise OllamaModelClientError(msg) from exc

        response_payload = self._post_generate_payload(payload)
        return model_response_from_ollama_generate_payload(
            payload=response_payload,
            fallback_model_name=request.model_name,
        )

    def _post_generate_payload(self, payload: dict[str, object]) -> dict[str, object]:
        url = f"{self._settings.base_url.rstrip('/')}/api/generate"
        try:
            return self._transport(
                url,
                payload,
                self._settings.request_timeout_seconds,
            )
        except OllamaModelClientError:
            raise
        except ValueError as exc:
            msg = "OllamaModelClient received an invalid response payload."
            raise OllamaModelClientError(msg) from exc
        except Exception as exc:
            msg = "OllamaModelClient transport failed."
            raise OllamaModelClientError(msg) from exc


def _default_ollama_generate_transport(
    url: str,
    payload: dict[str, object],
    timeout_seconds: float,
) -> dict[str, object]:
    request_body = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=request_body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
            response_body = response.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        msg = f"Ollama generate request failed with HTTP status {exc.code}."
        raise OllamaModelClientError(msg) from exc
    except urllib.error.URLError as exc:
        msg = "Ollama generate request failed due to a network error."
        raise OllamaModelClientError(msg) from exc
    except TimeoutError as exc:
        raise OllamaModelClientError(OLLAMA_REQUEST_TIMEOUT_MESSAGE) from exc

    try:
        decoded_payload: Any = json.loads(response_body)
    except json.JSONDecodeError as exc:
        msg = "Ollama generate response was not valid JSON."
        raise OllamaModelClientError(msg) from exc

    if not isinstance(decoded_payload, dict):
        msg = "Ollama generate response JSON must be an object."
        raise OllamaModelClientError(msg)

    return decoded_payload
