from decimal import Decimal
import inspect
import json
from uuid import UUID, uuid4

import pytest

import daedalus.domains.readysetrentables_reviews.review_insight_output_parser as parser_module
from daedalus.domains.readysetrentables_reviews.review_insight_output_parser import (
    parse_review_insight_extraction_result,
)
from daedalus.domains.readysetrentables_reviews.review_insight_models import (
    ReviewInsightExtractionResult,
)
from daedalus.model_clients.types import ModelProvider


def test_parse_review_insight_extraction_result_parses_raw_json_output() -> None:
    run_id = uuid4()

    result = parse_review_insight_extraction_result(
        output_text=json.dumps(_model_output_payload()),
        run_id=run_id,
        provider=ModelProvider.OLLAMA,
        model_name="llama3.1",
        prompt_name="review-insights",
        prompt_version="v1",
    )

    assert result.run_id == run_id
    assert result.provider == ModelProvider.OLLAMA
    assert result.model_name == "llama3.1"
    assert result.prompt_name == "review-insights"
    assert result.prompt_version == "v1"
    assert result.themes[0].name == "arrival clarity"
    assert result.themes[0].sentiment == "positive"
    assert result.themes[0].evidence_count == 3
    assert result.themes[0].summary == "Guests value clear synthetic arrival guidance."
    assert result.strengths == ["Clear arrival details", "Responsive synthetic host"]
    assert result.risks == ["Occasional synthetic street noise"]
    assert result.guest_expectations == ["Send arrival notes before check-in"]
    assert result.raw_insight_summary == "Synthetic guests mostly praise arrival clarity."


def test_parse_review_insight_extraction_result_parses_json_fenced_code_block() -> None:
    result = parse_review_insight_extraction_result(
        output_text=f"```json\n{json.dumps(_model_output_payload())}\n```",
        run_id=uuid4(),
        provider=ModelProvider.OLLAMA,
        model_name="llama3.1",
        prompt_name="review-insights",
        prompt_version="v1",
    )

    assert result.raw_insight_summary == "Synthetic guests mostly praise arrival clarity."


def test_parse_review_insight_extraction_result_parses_json_surrounded_by_text() -> None:
    output_text = (
        f"Here is the structured result:\n\n{json.dumps(_model_output_payload())}\n\nDone."
    )

    result = parse_review_insight_extraction_result(
        output_text=output_text,
        run_id=uuid4(),
        provider=ModelProvider.OLLAMA,
        model_name="llama3.1",
        prompt_name="review-insights",
        prompt_version="v1",
    )

    assert result.themes[0].name == "arrival clarity"


def test_parse_review_insight_extraction_result_rejects_blank_output() -> None:
    with pytest.raises(ValueError, match="cannot be blank"):
        parse_review_insight_extraction_result(
            output_text="   ",
            run_id=uuid4(),
            provider=ModelProvider.OLLAMA,
            model_name="llama3.1",
            prompt_name="review-insights",
            prompt_version="v1",
        )


def test_parse_review_insight_extraction_result_rejects_invalid_json() -> None:
    with pytest.raises(ValueError, match="valid JSON object"):
        parse_review_insight_extraction_result(
            output_text='{"themes": [}',
            run_id=uuid4(),
            provider=ModelProvider.OLLAMA,
            model_name="llama3.1",
            prompt_name="review-insights",
            prompt_version="v1",
        )


def test_parse_review_insight_extraction_result_rejects_missing_raw_insight_summary() -> None:
    payload = _model_output_payload()
    del payload["raw_insight_summary"]

    with pytest.raises(ValueError, match="expected schema"):
        parse_review_insight_extraction_result(
            output_text=json.dumps(payload),
            run_id=uuid4(),
            provider=ModelProvider.OLLAMA,
            model_name="llama3.1",
            prompt_name="review-insights",
            prompt_version="v1",
        )


def test_parse_review_insight_extraction_result_rejects_invalid_theme_shape() -> None:
    payload = _model_output_payload()
    payload["themes"] = [{"name": "arrival clarity", "sentiment": "positive"}]

    with pytest.raises(ValueError, match="expected schema"):
        parse_review_insight_extraction_result(
            output_text=json.dumps(payload),
            run_id=uuid4(),
            provider=ModelProvider.OLLAMA,
            model_name="llama3.1",
            prompt_name="review-insights",
            prompt_version="v1",
        )


def test_parse_review_insight_extraction_result_uses_supplied_run_id() -> None:
    run_id = UUID("00000000-0000-0000-0000-000000000011")

    result = _parse_with_metadata(run_id=run_id)

    assert result.run_id == run_id


def test_parse_review_insight_extraction_result_uses_supplied_provider() -> None:
    result = _parse_with_metadata(provider=ModelProvider.FAKE)

    assert result.provider == ModelProvider.FAKE


def test_parse_review_insight_extraction_result_uses_supplied_model_name() -> None:
    result = _parse_with_metadata(model_name="supplied-model")

    assert result.model_name == "supplied-model"


def test_parse_review_insight_extraction_result_uses_supplied_prompt_identity() -> None:
    result = _parse_with_metadata(prompt_name="supplied-prompt", prompt_version="v9")

    assert result.prompt_name == "supplied-prompt"
    assert result.prompt_version == "v9"


def test_parse_review_insight_extraction_result_ignores_model_supplied_metadata() -> None:
    payload = _model_output_payload()
    payload.update(
        {
            "run_id": "00000000-0000-0000-0000-000000000099",
            "provider": "anthropic",
            "model_name": "model-from-output",
            "prompt_name": "prompt-from-output",
            "prompt_version": "v-output",
            "input_tokens": 999,
        }
    )
    supplied_run_id = UUID("00000000-0000-0000-0000-000000000012")

    result = parse_review_insight_extraction_result(
        output_text=json.dumps(payload),
        run_id=supplied_run_id,
        provider=ModelProvider.OLLAMA,
        model_name="supplied-model",
        prompt_name="supplied-prompt",
        prompt_version="v1",
    )

    assert result.run_id == supplied_run_id
    assert result.provider == ModelProvider.OLLAMA
    assert result.model_name == "supplied-model"
    assert result.prompt_name == "supplied-prompt"
    assert result.prompt_version == "v1"
    assert result.input_tokens is None


def test_parse_review_insight_extraction_result_preserves_token_metadata() -> None:
    result = parse_review_insight_extraction_result(
        output_text=json.dumps(_model_output_payload()),
        run_id=uuid4(),
        provider=ModelProvider.OLLAMA,
        model_name="llama3.1",
        prompt_name="review-insights",
        prompt_version="v1",
        input_tokens=120,
        output_tokens=80,
        total_tokens=200,
    )

    assert result.input_tokens == 120
    assert result.output_tokens == 80
    assert result.total_tokens == 200


def test_parse_review_insight_extraction_result_preserves_estimated_cost() -> None:
    result = parse_review_insight_extraction_result(
        output_text=json.dumps(_model_output_payload()),
        run_id=uuid4(),
        provider=ModelProvider.OLLAMA,
        model_name="llama3.1",
        prompt_name="review-insights",
        prompt_version="v1",
        estimated_cost_usd=Decimal("0.0004"),
    )

    assert result.estimated_cost_usd == Decimal("0.0004")


def test_parser_error_messages_do_not_include_raw_model_output() -> None:
    raw_output = (
        '{"themes":[{"name":"arrival clarity","sentiment":"positive"}],'
        '"raw_insight_summary":"Synthetic private model output"}'
    )

    with pytest.raises(ValueError) as exc_info:
        parse_review_insight_extraction_result(
            output_text=raw_output,
            run_id=uuid4(),
            provider=ModelProvider.OLLAMA,
            model_name="llama3.1",
            prompt_name="review-insights",
            prompt_version="v1",
        )

    error_message = str(exc_info.value)
    assert raw_output not in error_message
    assert "Synthetic private model output" not in error_message


def test_parser_does_not_call_model_providers() -> None:
    source = inspect.getsource(parser_module)

    assert "ModelClient" not in source
    assert "ModelRequest" not in source
    assert "ModelResponse" not in source
    assert "ollama" not in source.lower()


def test_parse_review_insight_extraction_result_json_serializes_enum_values() -> None:
    result = _parse_with_metadata(provider=ModelProvider.OLLAMA)

    serialized = result.model_dump_json()

    assert '"provider":"ollama"' in serialized


def _parse_with_metadata(
    *,
    run_id: UUID | None = None,
    provider: ModelProvider = ModelProvider.OLLAMA,
    model_name: str = "llama3.1",
    prompt_name: str = "review-insights",
    prompt_version: str = "v1",
) -> ReviewInsightExtractionResult:
    return parse_review_insight_extraction_result(
        output_text=json.dumps(_model_output_payload()),
        run_id=uuid4() if run_id is None else run_id,
        provider=provider,
        model_name=model_name,
        prompt_name=prompt_name,
        prompt_version=prompt_version,
    )


def _model_output_payload() -> dict[str, object]:
    return {
        "themes": [
            {
                "name": "arrival clarity",
                "sentiment": "positive",
                "evidence_count": 3,
                "summary": "Guests value clear synthetic arrival guidance.",
            }
        ],
        "strengths": ["Clear arrival details", "Responsive synthetic host"],
        "risks": ["Occasional synthetic street noise"],
        "guest_expectations": ["Send arrival notes before check-in"],
        "raw_insight_summary": "Synthetic guests mostly praise arrival clarity.",
    }
