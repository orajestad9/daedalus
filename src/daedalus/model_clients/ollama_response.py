"""Pure Ollama response parsing helpers.

These helpers convert already-received local Ollama payloads into Daedalus
model-client types. They do not perform HTTP requests or provider work.
"""

from decimal import Decimal
from uuid import uuid4

from daedalus.model_clients.types import (
    ModelInvocationStatus,
    ModelProvider,
    ModelResponse,
)


def model_response_from_ollama_generate_payload(
    *,
    payload: dict[str, object],
    fallback_model_name: str,
) -> ModelResponse:
    """Convert an Ollama generate response payload into a ModelResponse."""
    output_text = _required_response_text(payload)
    model_name = _model_name_from_payload(
        payload=payload,
        fallback_model_name=fallback_model_name,
    )
    input_tokens = _optional_token_count(payload, "prompt_eval_count")
    output_tokens = _optional_token_count(payload, "eval_count")
    total_tokens = None
    if input_tokens is not None and output_tokens is not None:
        total_tokens = input_tokens + output_tokens

    return ModelResponse(
        invocation_id=uuid4(),
        status=ModelInvocationStatus.COMPLETED,
        provider=ModelProvider.OLLAMA,
        model_name=model_name,
        output_text=output_text,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        total_tokens=total_tokens,
        estimated_cost_usd=Decimal("0"),
    )


def _required_response_text(payload: dict[str, object]) -> str:
    response = payload.get("response")
    if not isinstance(response, str):
        msg = "Ollama generate payload must include a string response field."
        raise ValueError(msg)

    return response


def _model_name_from_payload(
    *,
    payload: dict[str, object],
    fallback_model_name: str,
) -> str:
    model_name = payload.get("model")
    if isinstance(model_name, str) and model_name.strip():
        return model_name

    return fallback_model_name


def _optional_token_count(payload: dict[str, object], field_name: str) -> int | None:
    value = payload.get(field_name)
    if value is None:
        return None
    if isinstance(value, int):
        return value

    msg = f"Ollama generate payload field {field_name} must be an integer when present."
    raise ValueError(msg)
