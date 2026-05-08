"""Shared model-client protocol for future Daedalus model execution.

All model calls should pass through this abstraction. Provider SDKs belong
behind concrete implementations, while agents and LangGraph nodes should depend
on this protocol so budgets, artifacts, logging, and invocation records can stay
consistent across providers.
"""

from typing import Protocol, runtime_checkable

from daedalus.model_clients.types import ModelRequest, ModelResponse


@runtime_checkable
class ModelClient(Protocol):
    """Protocol implemented by future fake, local, and cloud model clients."""

    def complete(self, request: ModelRequest) -> ModelResponse:
        """Complete one structured model request and return a structured response."""
        ...
