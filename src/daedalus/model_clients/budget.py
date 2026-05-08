"""Budget validation helpers for model responses."""

from decimal import Decimal

from daedalus.model_clients.types import ModelRequest, ModelResponse


class ModelBudgetExceededError(ValueError):
    """Raised when a model response exceeds a configured request budget."""


def validate_model_budget(
    *,
    request: ModelRequest,
    response: ModelResponse,
) -> None:
    """Validate response token and cost usage against the request budget."""
    budget = request.budget
    if budget is None:
        return

    _raise_if_int_exceeded(
        field_name="max_input_tokens",
        limit=budget.max_input_tokens,
        actual=response.input_tokens,
    )
    _raise_if_int_exceeded(
        field_name="max_output_tokens",
        limit=budget.max_output_tokens,
        actual=response.output_tokens,
    )
    _raise_if_int_exceeded(
        field_name="max_total_tokens",
        limit=budget.max_total_tokens,
        actual=response.total_tokens,
    )
    _raise_if_decimal_exceeded(
        field_name="max_estimated_cost_usd",
        limit=budget.max_estimated_cost_usd,
        actual=response.estimated_cost_usd,
    )


def _raise_if_int_exceeded(
    *,
    field_name: str,
    limit: int | None,
    actual: int | None,
) -> None:
    if limit is None or actual is None or actual <= limit:
        return

    msg = f"Model budget exceeded: {field_name} limit={limit} actual={actual}"
    raise ModelBudgetExceededError(msg)


def _raise_if_decimal_exceeded(
    *,
    field_name: str,
    limit: Decimal | None,
    actual: Decimal | None,
) -> None:
    if limit is None or actual is None or actual <= limit:
        return

    msg = f"Model budget exceeded: {field_name} limit={limit} actual={actual}"
    raise ModelBudgetExceededError(msg)
