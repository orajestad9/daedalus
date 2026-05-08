"""Model-client boundary types and protocols."""

from typing import TYPE_CHECKING

from daedalus.model_clients.client import ModelClient
from daedalus.model_clients.fake import FakeModelClient
from daedalus.model_clients.invocation_record import (
    ModelInvocationRecord,
    ModelInvocationStatus,
)

if TYPE_CHECKING:
    from daedalus.model_clients.invocation_recorder import ModelInvocationRecorder
    from daedalus.model_clients.recording import RecordingModelClient

__all__ = [
    "FakeModelClient",
    "ModelClient",
    "ModelInvocationRecord",
    "ModelInvocationRecorder",
    "ModelInvocationStatus",
    "RecordingModelClient",
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
