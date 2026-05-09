from pathlib import Path
from uuid import uuid4

import pytest

from daedalus.model_clients import ollama_generate_payload_from_model_request
from daedalus.model_clients.types import (
    ModelBudget,
    ModelProvider,
    ModelRequest,
)


def test_ollama_generate_payload_builds_model_prompt_and_stream_false() -> None:
    request = _model_request(input_text="Summarize these compact reviews.")

    payload = ollama_generate_payload_from_model_request(request)

    assert payload["model"] == "llama3.1"
    assert payload["prompt"] == "Summarize these compact reviews."
    assert payload["stream"] is False


def test_ollama_generate_payload_includes_system_when_present() -> None:
    request = _model_request(
        input_text="Summarize these compact reviews.",
        system_prompt="You are a concise local summarizer.",
    )

    payload = ollama_generate_payload_from_model_request(request)

    assert payload["system"] == "You are a concise local summarizer."


def test_ollama_generate_payload_omits_system_when_none() -> None:
    request = _model_request(input_text="Summarize these compact reviews.")

    payload = ollama_generate_payload_from_model_request(request)

    assert "system" not in payload


def test_ollama_generate_payload_omits_daedalus_context_fields() -> None:
    request = _model_request(
        input_text="Summarize these compact reviews.",
        metadata={"review_count": "8"},
        budget=ModelBudget(max_total_tokens=100),
    )

    payload = ollama_generate_payload_from_model_request(request)

    assert "run_id" not in payload
    assert "prompt_name" not in payload
    assert "prompt_version" not in payload
    assert "budget" not in payload
    assert "metadata" not in payload


@pytest.mark.parametrize("model_name", ["", "   "])
def test_ollama_generate_payload_rejects_empty_model_name(model_name: str) -> None:
    request = _model_request(
        model_name=model_name,
        input_text="Summarize these compact reviews.",
    )

    with pytest.raises(ValueError, match="model_name") as exc_info:
        ollama_generate_payload_from_model_request(request)

    assert "Summarize these compact reviews" not in str(exc_info.value)


@pytest.mark.parametrize("input_text", ["", "   "])
def test_ollama_generate_payload_rejects_empty_input_text(input_text: str) -> None:
    raw_input_text = "raw prompt text should not appear"
    request = _model_request(input_text=input_text)

    with pytest.raises(ValueError, match="input_text") as exc_info:
        ollama_generate_payload_from_model_request(request)

    assert raw_input_text not in str(exc_info.value)


def _model_request(
    *,
    model_name: str = "llama3.1",
    input_text: str,
    system_prompt: str | None = None,
    metadata: dict[str, str] | None = None,
    budget: ModelBudget | None = None,
) -> ModelRequest:
    return ModelRequest(
        run_id=uuid4(),
        agent_name="review_theme_summary_agent",
        provider=ModelProvider.OLLAMA,
        model_name=model_name,
        prompt_name="readysetrentables/review_theme_summary",
        prompt_version="v0",
        input_text=input_text,
        system_prompt=system_prompt,
        input_artifact_path=Path("artifacts/input.json"),
        output_artifact_path=Path("artifacts/output.md"),
        budget=budget,
        metadata=metadata or {},
    )
