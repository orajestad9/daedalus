"""Typed models for ReadySetRentables review insight extraction."""

from decimal import Decimal
from pathlib import Path
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

from daedalus.model_clients.types import ModelProvider


DEFAULT_REVIEW_INSIGHT_PROMPT_NAME = "readysetrentables_review_insight_extraction"
DEFAULT_REVIEW_INSIGHT_PROMPT_VERSION = "v0"


class ReviewInsightExtractionInput(BaseModel):
    """Compact, model-ready input for local review insight extraction."""

    run_id: UUID
    review_count: int = Field(ge=0)
    market_name: str | None = None
    neighborhood_name: str | None = None
    property_type: str | None = None
    average_rating: float | None = None
    rating_categories: dict[str, float] = Field(default_factory=dict)
    representative_reviews: list[str] = Field(default_factory=list)
    source_artifact_path: Path | None = None
    prompt_name: str = DEFAULT_REVIEW_INSIGHT_PROMPT_NAME
    prompt_version: str = DEFAULT_REVIEW_INSIGHT_PROMPT_VERSION

    @field_validator("market_name", "neighborhood_name", "property_type")
    @classmethod
    def _optional_string_cannot_be_blank(cls, value: str | None) -> str | None:
        if value is not None and not value.strip():
            msg = "field cannot be blank when provided"
            raise ValueError(msg)
        return value

    @field_validator("rating_categories")
    @classmethod
    def _rating_categories_must_have_valid_keys_and_values(
        cls,
        value: dict[str, float],
    ) -> dict[str, float]:
        for key, rating in value.items():
            if not key.strip():
                msg = "rating_categories keys cannot be blank"
                raise ValueError(msg)
            if rating < 0 or rating > 5:
                msg = f"rating_categories value must be between 0 and 5 inclusive, got {rating}"
                raise ValueError(msg)
        return value

    @field_validator("representative_reviews")
    @classmethod
    def _representative_reviews_cannot_contain_blank_entries(
        cls,
        value: list[str],
    ) -> list[str]:
        if any(not entry.strip() for entry in value):
            msg = "representative_reviews entries cannot be blank"
            raise ValueError(msg)
        return value


class ReviewInsightTheme(BaseModel):
    """One theme identified in a review insight extraction result."""

    name: str
    sentiment: str
    evidence_count: int = Field(ge=0)
    summary: str

    @field_validator("name", "sentiment", "summary")
    @classmethod
    def _string_cannot_be_blank(cls, value: str) -> str:
        if not value.strip():
            msg = "field cannot be blank"
            raise ValueError(msg)
        return value


class ReviewInsightExtractionResult(BaseModel):
    """Structured result for a review insight extraction model call."""

    run_id: UUID
    provider: ModelProvider
    model_name: str
    prompt_name: str
    prompt_version: str
    themes: list[ReviewInsightTheme] = Field(default_factory=list)
    strengths: list[str] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)
    guest_expectations: list[str] = Field(default_factory=list)
    raw_insight_summary: str
    input_tokens: int | None = Field(default=None, ge=0)
    output_tokens: int | None = Field(default=None, ge=0)
    total_tokens: int | None = Field(default=None, ge=0)
    estimated_cost_usd: Decimal | None = Field(default=None, ge=0)

    @field_validator("model_name", "prompt_name", "prompt_version", "raw_insight_summary")
    @classmethod
    def _required_string_cannot_be_blank(cls, value: str) -> str:
        if not value.strip():
            msg = "field cannot be blank"
            raise ValueError(msg)
        return value

    @field_validator("strengths", "risks", "guest_expectations")
    @classmethod
    def _string_list_cannot_contain_blank_entries(
        cls,
        value: list[str],
    ) -> list[str]:
        if any(not entry.strip() for entry in value):
            msg = "list entries cannot be blank"
            raise ValueError(msg)
        return value
