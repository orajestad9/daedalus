from decimal import Decimal

import pytest

from daedalus.model_clients.ollama_response import (
    model_response_from_ollama_generate_payload,
)
from daedalus.model_clients.types import ModelProvider


def test_ollama_generate_payload_parses_response_text() -> None:
    response = model_response_from_ollama_generate_payload(
        payload={"response": "safe local output", "model": "llama3.1"},
        fallback_model_name="fallback-model",
    )

    assert response.output_text == "safe local output"
    assert response.provider == ModelProvider.OLLAMA


def test_ollama_generate_payload_uses_payload_model_when_present() -> None:
    response = model_response_from_ollama_generate_payload(
        payload={"response": "safe local output", "model": "llama3.1"},
        fallback_model_name="fallback-model",
    )

    assert response.model_name == "llama3.1"


def test_ollama_generate_payload_uses_fallback_model_when_payload_model_missing() -> None:
    response = model_response_from_ollama_generate_payload(
        payload={"response": "safe local output"},
        fallback_model_name="fallback-model",
    )

    assert response.model_name == "fallback-model"


def test_ollama_generate_payload_maps_token_counts() -> None:
    response = model_response_from_ollama_generate_payload(
        payload={
            "response": "safe local output",
            "prompt_eval_count": 10,
            "eval_count": 4,
        },
        fallback_model_name="fallback-model",
    )

    assert response.input_tokens == 10
    assert response.output_tokens == 4
    assert response.total_tokens == 14


def test_ollama_generate_payload_sets_zero_estimated_cost() -> None:
    response = model_response_from_ollama_generate_payload(
        payload={"response": "safe local output"},
        fallback_model_name="fallback-model",
    )

    assert response.estimated_cost_usd == Decimal("0")


def test_ollama_generate_payload_leaves_missing_token_counts_as_none() -> None:
    response = model_response_from_ollama_generate_payload(
        payload={"response": "safe local output"},
        fallback_model_name="fallback-model",
    )

    assert response.input_tokens is None
    assert response.output_tokens is None
    assert response.total_tokens is None


def test_ollama_generate_payload_missing_response_raises_safe_error() -> None:
    with pytest.raises(ValueError, match="string response field") as exc_info:
        model_response_from_ollama_generate_payload(
            payload={},
            fallback_model_name="fallback-model",
        )

    assert "safe local output" not in str(exc_info.value)


def test_ollama_generate_payload_non_string_response_raises_safe_error() -> None:
    raw_response_text = "raw output should stay out of errors"

    with pytest.raises(ValueError, match="string response field") as exc_info:
        model_response_from_ollama_generate_payload(
            payload={"response": {"text": raw_response_text}},
            fallback_model_name="fallback-model",
        )

    assert raw_response_text not in str(exc_info.value)


@pytest.mark.parametrize("field_name", ["prompt_eval_count", "eval_count"])
def test_ollama_generate_payload_non_integer_token_count_raises_safe_error(
    field_name: str,
) -> None:
    with pytest.raises(ValueError, match=field_name) as exc_info:
        model_response_from_ollama_generate_payload(
            payload={"response": "safe local output", field_name: "10"},
            fallback_model_name="fallback-model",
        )

    assert "safe local output" not in str(exc_info.value)
