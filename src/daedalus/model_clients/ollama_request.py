"""Pure Ollama request payload helpers.

These helpers convert Daedalus model-client requests into local Ollama payloads.
They do not perform HTTP requests, log payloads, or call provider SDKs.
"""

from daedalus.model_clients.types import ModelRequest


def ollama_generate_payload_from_model_request(
    request: ModelRequest,
) -> dict[str, object]:
    """Build an Ollama /api/generate payload from a ModelRequest."""
    model_name = request.model_name.strip()
    if not model_name:
        msg = "Ollama generate payload requires a non-empty model_name."
        raise ValueError(msg)

    input_text = request.input_text.strip()
    if not input_text:
        msg = "Ollama generate payload requires non-empty input_text."
        raise ValueError(msg)

    payload: dict[str, object] = {
        "model": model_name,
        "prompt": request.input_text,
        "stream": False,
    }
    if request.system_prompt is not None:
        payload["system"] = request.system_prompt

    return payload
