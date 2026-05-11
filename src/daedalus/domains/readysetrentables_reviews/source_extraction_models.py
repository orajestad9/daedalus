"""Typed models for the ReadySetRentables read-only source extraction boundary."""

from datetime import datetime
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, field_validator


class RsrSourceExtractionRequest(BaseModel):
    """Compact input describing what to extract from the RSR source database."""

    request_id: UUID = Field(default_factory=uuid4)
    market_name: str
    neighborhood_name: str | None = None
    property_type: str | None = None
    max_reviews: int | None = None
    include_listing_context: bool = True
    include_neighborhood_context: bool = True

    @field_validator("market_name")
    @classmethod
    def _market_name_cannot_be_blank(cls, value: str) -> str:
        if not value.strip():
            msg = "market_name cannot be blank"
            raise ValueError(msg)
        return value

    @field_validator("neighborhood_name", "property_type")
    @classmethod
    def _optional_string_cannot_be_blank(cls, value: str | None) -> str | None:
        if value is not None and not value.strip():
            msg = "field cannot be blank when provided"
            raise ValueError(msg)
        return value

    @field_validator("max_reviews")
    @classmethod
    def _max_reviews_must_be_positive(cls, value: int | None) -> int | None:
        if value is not None and value <= 0:
            msg = f"max_reviews must be greater than 0 when provided, got {value}"
            raise ValueError(msg)
        return value


class RsrSourceReviewRecord(BaseModel):
    """Sanitized review record extracted from the RSR source database."""

    review_id: str
    listing_id: str | None = None
    rating: float | None = None
    review_text: str
    created_at: datetime | None = None
    metadata: dict[str, str] = Field(default_factory=dict)

    @field_validator("review_id", "review_text")
    @classmethod
    def _required_string_cannot_be_blank(cls, value: str) -> str:
        if not value.strip():
            msg = "field cannot be blank"
            raise ValueError(msg)
        return value

    @field_validator("listing_id")
    @classmethod
    def _optional_string_cannot_be_blank(cls, value: str | None) -> str | None:
        if value is not None and not value.strip():
            msg = "field cannot be blank when provided"
            raise ValueError(msg)
        return value

    @field_validator("rating")
    @classmethod
    def _rating_must_be_in_range(cls, value: float | None) -> float | None:
        if value is not None and (value < 0 or value > 5):
            msg = f"rating must be between 0 and 5 inclusive when provided, got {value}"
            raise ValueError(msg)
        return value

    @field_validator("metadata")
    @classmethod
    def _metadata_keys_and_values_cannot_be_blank(cls, value: dict[str, str]) -> dict[str, str]:
        for key, val in value.items():
            if not key.strip():
                msg = "metadata keys cannot be blank"
                raise ValueError(msg)
            if not val.strip():
                msg = "metadata values cannot be blank"
                raise ValueError(msg)
        return value


class RsrSourceListingContext(BaseModel):
    """Sanitized listing context extracted from the RSR source database."""

    listing_id: str
    listing_name: str | None = None
    property_type: str | None = None
    bedrooms: int | None = None
    bathrooms: float | None = None
    accommodates: int | None = None
    average_rating: float | None = None
    metadata: dict[str, str] = Field(default_factory=dict)

    @field_validator("listing_id")
    @classmethod
    def _listing_id_cannot_be_blank(cls, value: str) -> str:
        if not value.strip():
            msg = "listing_id cannot be blank"
            raise ValueError(msg)
        return value

    @field_validator("listing_name", "property_type")
    @classmethod
    def _optional_string_cannot_be_blank(cls, value: str | None) -> str | None:
        if value is not None and not value.strip():
            msg = "field cannot be blank when provided"
            raise ValueError(msg)
        return value

    @field_validator("bedrooms", "accommodates")
    @classmethod
    def _optional_int_must_be_non_negative(cls, value: int | None) -> int | None:
        if value is not None and value < 0:
            msg = "field must be non-negative when provided"
            raise ValueError(msg)
        return value

    @field_validator("bathrooms")
    @classmethod
    def _bathrooms_must_be_non_negative(cls, value: float | None) -> float | None:
        if value is not None and value < 0:
            msg = "bathrooms must be non-negative when provided"
            raise ValueError(msg)
        return value

    @field_validator("average_rating")
    @classmethod
    def _average_rating_must_be_in_range(cls, value: float | None) -> float | None:
        if value is not None and (value < 0 or value > 5):
            msg = f"average_rating must be between 0 and 5 inclusive when provided, got {value}"
            raise ValueError(msg)
        return value

    @field_validator("metadata")
    @classmethod
    def _metadata_keys_and_values_cannot_be_blank(cls, value: dict[str, str]) -> dict[str, str]:
        for key, val in value.items():
            if not key.strip():
                msg = "metadata keys cannot be blank"
                raise ValueError(msg)
            if not val.strip():
                msg = "metadata values cannot be blank"
                raise ValueError(msg)
        return value


class RsrSourceNeighborhoodContext(BaseModel):
    """Sanitized neighborhood context extracted from the RSR source database."""

    market_name: str
    neighborhood_name: str
    city: str | None = None
    state: str | None = None
    country: str | None = None
    metadata: dict[str, str] = Field(default_factory=dict)

    @field_validator("market_name", "neighborhood_name")
    @classmethod
    def _required_string_cannot_be_blank(cls, value: str) -> str:
        if not value.strip():
            msg = "field cannot be blank"
            raise ValueError(msg)
        return value

    @field_validator("city", "state", "country")
    @classmethod
    def _optional_string_cannot_be_blank(cls, value: str | None) -> str | None:
        if value is not None and not value.strip():
            msg = "field cannot be blank when provided"
            raise ValueError(msg)
        return value

    @field_validator("metadata")
    @classmethod
    def _metadata_keys_and_values_cannot_be_blank(cls, value: dict[str, str]) -> dict[str, str]:
        for key, val in value.items():
            if not key.strip():
                msg = "metadata keys cannot be blank"
                raise ValueError(msg)
            if not val.strip():
                msg = "metadata values cannot be blank"
                raise ValueError(msg)
        return value


class RsrSourceExtractionResult(BaseModel):
    """Aggregated sanitized result from one RSR source extraction pass."""

    request: RsrSourceExtractionRequest
    extracted_at_utc: datetime
    reviews: list[RsrSourceReviewRecord] = Field(default_factory=list)
    listings: list[RsrSourceListingContext] = Field(default_factory=list)
    neighborhood: RsrSourceNeighborhoodContext | None = None
    source_name: str = "readysetrentables"
    source_version: str = "v0"
    metadata: dict[str, str] = Field(default_factory=dict)

    @field_validator("extracted_at_utc")
    @classmethod
    def _extracted_at_utc_must_be_timezone_aware(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            msg = "extracted_at_utc must be timezone-aware"
            raise ValueError(msg)
        return value

    @field_validator("source_name", "source_version")
    @classmethod
    def _required_string_cannot_be_blank(cls, value: str) -> str:
        if not value.strip():
            msg = "field cannot be blank"
            raise ValueError(msg)
        return value

    @field_validator("metadata")
    @classmethod
    def _metadata_keys_and_values_cannot_be_blank(cls, value: dict[str, str]) -> dict[str, str]:
        for key, val in value.items():
            if not key.strip():
                msg = "metadata keys cannot be blank"
                raise ValueError(msg)
            if not val.strip():
                msg = "metadata values cannot be blank"
                raise ValueError(msg)
        return value
