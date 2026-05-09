"""Model-client boundary types and protocols."""

from typing import TYPE_CHECKING

from daedalus.model_clients.client import ModelClient
from daedalus.model_clients.fake import FakeModelClient
from daedalus.model_clients.invocation_record import (
    ModelInvocationRecord,
    ModelInvocationStatus,
)
from daedalus.model_clients.ollama_response import model_response_from_ollama_generate_payload
from daedalus.model_clients.ollama_settings import OllamaModelClientSettings

if TYPE_CHECKING:
    from daedalus.model_clients.invocation_recorder import ModelInvocationRecorder
    from daedalus.model_clients.recording import RecordingModelClient

__all__ = [
    "FakeModelClient",
    "ModelClient",
    "ModelInvocationRecord",
    "ModelInvocationRecorder",
    "ModelInvocationStatus",
    "OllamaModelClientSettings",
    "RecordingModelClient",
    "model_response_from_ollama_generate_payload",
]


def __getattr__(name: str) -> object:
    if name == "ModelInvocationRecorder":
        from daedalus.model_clients.invocation_recorder import ModelInvocationRecorder

        return ModelInvocationRecorder
    if name == "RecordingModelClient":
        from daedalus.model_clients.recording import RecordingModelClient

        return RecordingModelClient

    msg = f"module {__name__!r} has no attribute {name!r}"
    raise AttributeError(msg)
