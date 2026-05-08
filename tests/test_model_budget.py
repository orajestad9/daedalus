from decimal import Decimal
from pathlib import Path
from uuid import uuid4

import pytest

from daedalus.model_clients.budget import (
    ModelBudgetExceededError,
    validate_model_budget,
)
from daedalus.model_clients.types import (
    ModelBudget,
    ModelInvocationStatus,
    ModelProvider,
    ModelRequest,
    ModelResponse,
)


def test_no_budget_returns_without_error() -> None:
    request = _model_request(budget=None)
    response = _model_response(input_tokens=100, output_tokens=100, total_tokens=200)

    validate_model_budget(request=request, response=response)


def test_within_budget_response_returns_without_error() -> None:
    request = _model_request(
        budget=ModelBudget(
            max_input_tokens=10,
            max_output_tokens=10,
            max_total_tokens=20,
            max_estimated_cost_usd=Decimal("0.01"),
        )
    )
    response = _model_response(
        input_tokens=5,
        output_tokens=5,
        total_tokens=10,
        estimated_cost_usd=Decimal("0.001"),
    )

    validate_model_budget(request=request, response=response)


def test_exceeding_input_token_budget_raises() -> None:
    request = _model_request(budget=ModelBudget(max_input_tokens=4))
    response = _model_response(input_tokens=5)

    with pytest.raises(ModelBudgetExceededError, match="max_input_tokens"):
        validate_model_budget(request=request, response=response)


def test_exceeding_output_token_budget_raises() -> None:
    request = _model_request(budget=ModelBudget(max_output_tokens=4))
    response = _model_response(output_tokens=5)

    with pytest.raises(ModelBudgetExceededError, match="max_output_tokens"):
        validate_model_budget(request=request, response=response)


def test_exceeding_total_token_budget_raises() -> None:
    request = _model_request(budget=ModelBudget(max_total_tokens=9))
    response = _model_response(total_tokens=10)

    with pytest.raises(ModelBudgetExceededError, match="max_total_tokens"):
        validate_model_budget(request=request, response=response)


def test_exceeding_estimated_cost_budget_raises() -> None:
    request = _model_request(budget=ModelBudget(max_estimated_cost_usd=Decimal("0.01")))
    response = _model_response(estimated_cost_usd=Decimal("0.02"))

    with pytest.raises(ModelBudgetExceededError, match="max_estimated_cost_usd"):
        validate_model_budget(request=request, response=response)


def test_none_response_usage_fields_do_not_raise() -> None:
    request = _model_request(
        budget=ModelBudget(
            max_input_tokens=1,
            max_output_tokens=1,
            max_total_tokens=1,
            max_estimated_cost_usd=Decimal("0.01"),
        )
    )
    response = _model_response(
        input_tokens=None,
        output_tokens=None,
        total_tokens=None,
        estimated_cost_usd=None,
    )

    validate_model_budget(request=request, response=response)


def test_budget_error_messages_do_not_include_request_input_text() -> None:
    request = _model_request(
        budget=ModelBudget(max_input_tokens=1),
        input_text="sensitive prompt text",
    )
    response = _model_response(input_tokens=2)

    with pytest.raises(ModelBudgetExceededError) as exc_info:
        validate_model_budget(request=request, response=response)

    assert "sensitive prompt text" not in str(exc_info.value)


def test_budget_error_messages_do_not_include_response_output_text() -> None:
    request = _model_request(budget=ModelBudget(max_output_tokens=1))
    response = _model_response(output_tokens=2, output_text="sensitive response text")

    with pytest.raises(ModelBudgetExceededError) as exc_info:
        validate_model_budget(request=request, response=response)

    assert "sensitive response text" not in str(exc_info.value)


def _model_request(
    *,
    budget: ModelBudget | None = None,
    input_text: str = "sample prompt text",
) -> ModelRequest:
    return ModelRequest(
        run_id=uuid4(),
        agent_name="review_summarizer",
        provider=ModelProvider.FAKE,
        model_name="fake-local-model",
        prompt_name="summarize_reviews",
        prompt_version="v1",
        input_text=input_text,
        input_artifact_path=Path("artifacts/input.json"),
        output_artifact_path=Path("artifacts/output.json"),
        budget=budget,
    )


def _model_response(
    *,
    input_tokens: int | None = 5,
    output_tokens: int | None = 5,
    total_tokens: int | None = 10,
    estimated_cost_usd: Decimal | None = Decimal("0"),
    output_text: str = "sample response text",
) -> ModelResponse:
    return ModelResponse(
        invocation_id=uuid4(),
        status=ModelInvocationStatus.COMPLETED,
        provider=ModelProvider.FAKE,
        model_name="fake-local-model",
        output_text=output_text,
        output_artifact_path=Path("artifacts/output.json"),
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        total_tokens=total_tokens,
        estimated_cost_usd=estimated_cost_usd,
    )
