"""Typed models for future ReadySetRentables review theme summary agents."""

from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

from daedalus.model_clients.types import ModelBudget, ModelProvider


DEFAULT_REVIEW_THEME_PROMPT_NAME = "readysetrentables/review_theme_summary"
DEFAULT_REVIEW_THEME_PROMPT_VERSION = "v0"


class ReviewThemeSummaryInput(BaseModel):
    """Compact, model-ready input metadata for future review theme summarization."""

    run_id: UUID
    review_count: int = Field(ge=0)
    average_rating: float | None = Field(default=None, ge=0, le=5)
    representative_reviews: list[str] = Field(default_factory=list)
    rating_distribution: dict[str, int] = Field(default_factory=dict)
    prompt_name: str = DEFAULT_REVIEW_THEME_PROMPT_NAME
    prompt_version: str = DEFAULT_REVIEW_THEME_PROMPT_VERSION
    budget: ModelBudget | None = None

    @field_validator("rating_distribution")
    @classmethod
    def _rating_distribution_counts_must_be_non_negative(
        cls,
        value: dict[str, int],
    ) -> dict[str, int]:
        if any(count < 0 for count in value.values()):
            msg = "rating_distribution counts cannot be negative"
            raise ValueError(msg)
        return value


class ReviewThemeSummaryTheme(BaseModel):
    """One theme identified in a future review theme summary output."""

    name: str
    description: str
    sentiment: str
    supporting_review_count: int | None = Field(default=None, ge=0)


class ReviewThemeSummaryResult(BaseModel):
    """Structured result metadata for a future review theme summary artifact."""

    run_id: UUID
    summary_text: str
    themes: list[ReviewThemeSummaryTheme] = Field(default_factory=list)
    prompt_name: str
    prompt_version: str
    model_provider: ModelProvider
    model_name: str
    input_tokens: int | None = Field(default=None, ge=0)
    output_tokens: int | None = Field(default=None, ge=0)
    total_tokens: int | None = Field(default=None, ge=0)
    estimated_cost_usd: Decimal | None = Field(default=None, ge=0)
