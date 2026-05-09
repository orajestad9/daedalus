"""Settings for the future local Ollama model client."""

import os
from collections.abc import Mapping
from typing import Self

from pydantic import BaseModel, Field, field_validator


class OllamaModelClientSettings(BaseModel):
    """Configuration for a future OllamaModelClient.

    These settings are local-first and fail closed by default. They do not carry
    API keys or secrets, and they do not perform any network calls.
    """

    enabled: bool = False
    base_url: str = "http://localhost:11434"
    model_name: str = "llama3.1"
    request_timeout_seconds: float = Field(default=30.0, gt=0)

    @field_validator("base_url")
    @classmethod
    def _validate_base_url(cls, value: str) -> str:
        stripped_value = value.strip()
        if not stripped_value:
            msg = "base_url must not be empty"
            raise ValueError(msg)
        if not (stripped_value.startswith("http://") or stripped_value.startswith("https://")):
            msg = "base_url must start with http:// or https://"
            raise ValueError(msg)

        return stripped_value

    @field_validator("model_name")
    @classmethod
    def _validate_model_name(cls, value: str) -> str:
        stripped_value = value.strip()
        if not stripped_value:
            msg = "model_name must not be empty"
            raise ValueError(msg)

        return stripped_value

    @classmethod
    def from_env(
        cls,
        environ: Mapping[str, str] | None = None,
    ) -> Self:
        """Build settings from non-secret Ollama environment variables."""
        values = os.environ if environ is None else environ
        enabled = False
        base_url = "http://localhost:11434"
        model_name = "llama3.1"
        request_timeout_seconds = 30.0

        if "DAEDALUS_OLLAMA_ENABLED" in values:
            enabled = _parse_bool(values["DAEDALUS_OLLAMA_ENABLED"])
        if "DAEDALUS_OLLAMA_BASE_URL" in values:
            base_url = values["DAEDALUS_OLLAMA_BASE_URL"]
        if "DAEDALUS_OLLAMA_MODEL" in values:
            model_name = values["DAEDALUS_OLLAMA_MODEL"]
        if "DAEDALUS_OLLAMA_TIMEOUT_SECONDS" in values:
            request_timeout_seconds = float(values["DAEDALUS_OLLAMA_TIMEOUT_SECONDS"])

        return cls(
            enabled=enabled,
            base_url=base_url,
            model_name=model_name,
            request_timeout_seconds=request_timeout_seconds,
        )


def _parse_bool(value: str) -> bool:
    normalized_value = value.strip().lower()
    if normalized_value in {"1", "true", "yes", "on"}:
        return True
    if normalized_value in {"0", "false", "no", "off"}:
        return False

    msg = f"Invalid Ollama enabled value: {value!r}"
    raise ValueError(msg)
