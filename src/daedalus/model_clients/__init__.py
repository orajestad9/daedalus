"""Model-client boundary types and protocols."""

from daedalus.model_clients.client import ModelClient
from daedalus.model_clients.fake import FakeModelClient

__all__ = ["FakeModelClient", "ModelClient"]
