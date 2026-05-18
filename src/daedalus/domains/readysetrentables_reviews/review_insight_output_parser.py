"""Parse local model output into review insight extraction results."""

from decimal import Decimal
import json
from typing import Any, cast
from uuid import UUID

from pydantic import ValidationError

from daedalus.domains.readysetrentables_reviews.review_insight_models import (
    ReviewInsightExtractionResult,
)
from daedalus.model_clients.types import ModelProvider


def parse_review_insight_extraction_result(
    *,
    output_text: str,
    run_id: UUID,
    provider: ModelProvider,
    model_name: str,
    prompt_name: str,
    prompt_version: str,
    input_tokens: int | None = None,
    output_tokens: int | None = None,
    total_tokens: int | None = None,
    estimated_cost_usd: Decimal | None = None,
) -> ReviewInsightExtractionResult:
    """Parse JSON model output into a validated review insight result."""
    parsed_output = _load_model_output_json(output_text)

    result_payload = {
        "run_id": run_id,
        "provider": provider,
        "model_name": model_name,
        "prompt_name": prompt_name,
        "prompt_version": prompt_version,
        "themes": parsed_output.get("themes", []),
        "strengths": parsed_output.get("strengths", []),
        "risks": parsed_output.get("risks", []),
        "guest_expectations": parsed_output.get("guest_expectations", []),
        "raw_insight_summary": parsed_output.get("raw_insight_summary"),
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "total_tokens": total_tokens,
        "estimated_cost_usd": estimated_cost_usd,
    }

    try:
        return ReviewInsightExtractionResult.model_validate(result_payload)
    except ValidationError:
        msg = "Review insight model output does not match the expected schema."
        raise ValueError(msg) from None


def _load_model_output_json(output_text: str) -> dict[str, Any]:
    json_object_text = _extract_json_object(output_text)

    try:
        parsed = json.loads(json_object_text)
    except json.JSONDecodeError:
        msg = "Review insight model output did not contain valid JSON."
        raise ValueError(msg) from None

    if not isinstance(parsed, dict):
        msg = "Review insight model output JSON must be an object."
        raise ValueError(msg)

    return cast(dict[str, Any], parsed)


def _extract_json_object(output_text: str) -> str:
    stripped_output = output_text.strip()
    if not stripped_output:
        msg = "Review insight model output cannot be blank."
        raise ValueError(msg)

    start_positions = [index for index, char in enumerate(stripped_output) if char == "{"]
    for start_index in start_positions:
        maybe_object = _balanced_json_object_at(stripped_output, start_index)
        if maybe_object is None:
            continue
        try:
            parsed = json.loads(maybe_object)
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, dict):
            return maybe_object

    msg = "Review insight model output did not contain a valid JSON object."
    raise ValueError(msg)


def _balanced_json_object_at(text: str, start_index: int) -> str | None:
    depth = 0
    in_string = False
    escaped = False

    for index in range(start_index, len(text)):
        char = text[index]

        if in_string:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
            continue

        if char == '"':
            in_string = True
        elif char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return text[start_index : index + 1]

    return None
