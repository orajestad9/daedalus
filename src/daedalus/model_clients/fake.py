"""Deterministic fake model client for local tests and future agent development."""

from decimal import Decimal
from uuid import uuid4

from daedalus.model_clients.types import (
    ModelInvocationStatus,
    ModelProvider,
    ModelRequest,
    ModelResponse,
)


class FakeModelClient:
    """ModelClient implementation that performs no network or provider work."""

    def __init__(
        self,
        *,
        output_text: str = "fake model response",
        input_tokens: int | None = None,
        output_tokens: int | None = None,
        estimated_cost_usd: Decimal | None = Decimal("0"),
    ) -> None:
        self.output_text = output_text
        self.input_tokens = input_tokens
        self.output_tokens = output_tokens
        self.estimated_cost_usd = estimated_cost_usd

    def complete(self, request: ModelRequest) -> ModelResponse:
        """Return a deterministic response without logging or external calls."""
        input_tokens = self.input_tokens
        if input_tokens is None:
            input_tokens = _count_whitespace_tokens(request.input_text)

        output_tokens = self.output_tokens
        if output_tokens is None:
            output_tokens = _count_whitespace_tokens(self.output_text)

        return ModelResponse(
            invocation_id=uuid4(),
            status=ModelInvocationStatus.COMPLETED,
            provider=ModelProvider.FAKE,
            model_name=request.model_name,
            output_text=self.output_text,
            output_artifact_path=request.output_artifact_path,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=input_tokens + output_tokens,
            estimated_cost_usd=self.estimated_cost_usd,
        )


def _count_whitespace_tokens(value: str) -> int:
    return len(value.split())
