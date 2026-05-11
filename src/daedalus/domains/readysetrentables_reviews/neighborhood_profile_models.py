"""Typed models for ReadySetRentables neighborhood profile generation."""

from decimal import Decimal
from pathlib import Path
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

from daedalus.domains.readysetrentables_reviews.review_insight_models import (
    ReviewInsightExtractionResult,
)
from daedalus.model_clients.types import ModelProvider


DEFAULT_NEIGHBORHOOD_PROFILE_PROMPT_NAME = "readysetrentables_neighborhood_profile"
DEFAULT_NEIGHBORHOOD_PROFILE_PROMPT_VERSION = "v0"


class NeighborhoodProfileInput(BaseModel):
    """Compact, model-ready input for future neighborhood profile generation."""

    run_id: UUID
    market_name: str
    neighborhood_name: str
    property_type: str | None = None
    review_insights: ReviewInsightExtractionResult
    source_artifact_path: Path | None = None
    prompt_name: str = DEFAULT_NEIGHBORHOOD_PROFILE_PROMPT_NAME
    prompt_version: str = DEFAULT_NEIGHBORHOOD_PROFILE_PROMPT_VERSION

    @field_validator("market_name", "neighborhood_name", "prompt_name", "prompt_version")
    @classmethod
    def _required_string_cannot_be_blank(cls, value: str) -> str:
        if not value.strip():
            msg = "field cannot be blank"
            raise ValueError(msg)
        return value

    @field_validator("property_type")
    @classmethod
    def _optional_string_cannot_be_blank(cls, value: str | None) -> str | None:
        if value is not None and not value.strip():
            msg = "field cannot be blank when provided"
            raise ValueError(msg)
        return value


class NeighborhoodProfileSection(BaseModel):
    """One section in a neighborhood profile result."""

    heading: str
    body: str

    @field_validator("heading", "body")
    @classmethod
    def _string_cannot_be_blank(cls, value: str) -> str:
        if not value.strip():
            msg = "field cannot be blank"
            raise ValueError(msg)
        return value


class NeighborhoodProfileResult(BaseModel):
    """Structured result for a neighborhood profile generation model call."""

    run_id: UUID
    provider: ModelProvider
    model_name: str
    prompt_name: str
    prompt_version: str
    market_name: str
    neighborhood_name: str
    profile_title: str
    summary: str
    sections: list[NeighborhoodProfileSection] = Field(default_factory=list)
    investment_highlights: list[str] = Field(default_factory=list)
    guest_experience_notes: list[str] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)
    markdown: str
    input_tokens: int | None = Field(default=None, ge=0)
    output_tokens: int | None = Field(default=None, ge=0)
    total_tokens: int | None = Field(default=None, ge=0)
    estimated_cost_usd: Decimal | None = Field(default=None, ge=0)

    @field_validator(
        "model_name",
        "prompt_name",
        "prompt_version",
        "market_name",
        "neighborhood_name",
        "profile_title",
        "summary",
        "markdown",
    )
    @classmethod
    def _required_string_cannot_be_blank(cls, value: str) -> str:
        if not value.strip():
            msg = "field cannot be blank"
            raise ValueError(msg)
        return value

    @field_validator("investment_highlights", "guest_experience_notes", "risks")
    @classmethod
    def _string_list_cannot_contain_blank_entries(
        cls,
        value: list[str],
    ) -> list[str]:
        if any(not entry.strip() for entry in value):
            msg = "list entries cannot be blank"
            raise ValueError(msg)
        return value
