from datetime import datetime, timezone
from uuid import UUID, uuid4

import pytest
from pydantic import ValidationError

from daedalus.domains.readysetrentables_reviews.source_extraction_models import (
    RsrSourceExtractionRequest,
    RsrSourceExtractionResult,
    RsrSourceListingContext,
    RsrSourceNeighborhoodContext,
    RsrSourceReviewRecord,
)


# --- RsrSourceExtractionRequest ---


def test_extraction_request_requires_market_name() -> None:
    req = RsrSourceExtractionRequest(market_name="Austin")
    assert req.market_name == "Austin"


def test_extraction_request_generates_request_id_by_default() -> None:
    req = RsrSourceExtractionRequest(market_name="Austin")
    assert isinstance(req.request_id, UUID)


def test_extraction_request_accepts_explicit_request_id() -> None:
    rid = uuid4()
    req = RsrSourceExtractionRequest(request_id=rid, market_name="Austin")
    assert req.request_id == rid


def test_extraction_request_defaults_are_correct() -> None:
    req = RsrSourceExtractionRequest(market_name="Austin")
    assert req.neighborhood_name is None
    assert req.property_type is None
    assert req.max_reviews is None
    assert req.include_listing_context is True
    assert req.include_neighborhood_context is True


def test_extraction_request_rejects_blank_market_name() -> None:
    with pytest.raises(ValidationError):
        RsrSourceExtractionRequest(market_name="   ")


def test_extraction_request_rejects_empty_market_name() -> None:
    with pytest.raises(ValidationError):
        RsrSourceExtractionRequest(market_name="")


@pytest.mark.parametrize("field_name", ["neighborhood_name", "property_type"])
def test_extraction_request_rejects_blank_optional_string(field_name: str) -> None:
    with pytest.raises(ValidationError):
        if field_name == "neighborhood_name":
            RsrSourceExtractionRequest(market_name="Austin", neighborhood_name="   ")
        else:
            RsrSourceExtractionRequest(market_name="Austin", property_type="   ")


@pytest.mark.parametrize("field_name", ["neighborhood_name", "property_type"])
def test_extraction_request_accepts_none_optional_string(field_name: str) -> None:
    if field_name == "neighborhood_name":
        req = RsrSourceExtractionRequest(market_name="Austin", neighborhood_name=None)
        assert req.neighborhood_name is None
    else:
        req = RsrSourceExtractionRequest(market_name="Austin", property_type=None)
        assert req.property_type is None


def test_extraction_request_accepts_positive_max_reviews() -> None:
    req = RsrSourceExtractionRequest(market_name="Austin", max_reviews=50)
    assert req.max_reviews == 50


def test_extraction_request_rejects_zero_max_reviews() -> None:
    with pytest.raises(ValidationError):
        RsrSourceExtractionRequest(market_name="Austin", max_reviews=0)


def test_extraction_request_rejects_negative_max_reviews() -> None:
    with pytest.raises(ValidationError):
        RsrSourceExtractionRequest(market_name="Austin", max_reviews=-1)


def test_extraction_request_accepts_none_max_reviews() -> None:
    req = RsrSourceExtractionRequest(market_name="Austin", max_reviews=None)
    assert req.max_reviews is None


def test_extraction_request_accepts_false_include_flags() -> None:
    req = RsrSourceExtractionRequest(
        market_name="Austin",
        include_listing_context=False,
        include_neighborhood_context=False,
    )
    assert req.include_listing_context is False
    assert req.include_neighborhood_context is False


# --- RsrSourceReviewRecord ---


def _valid_review(**kwargs: object) -> RsrSourceReviewRecord:
    defaults: dict[str, object] = {
        "review_id": "rev-001",
        "review_text": "Great place to stay.",
    }
    defaults.update(kwargs)
    return RsrSourceReviewRecord(**defaults)  # type: ignore[arg-type]


def test_review_record_accepts_valid_minimal_record() -> None:
    review = _valid_review()
    assert review.review_id == "rev-001"
    assert review.review_text == "Great place to stay."


def test_review_record_defaults_are_correct() -> None:
    review = _valid_review()
    assert review.listing_id is None
    assert review.rating is None
    assert review.created_at is None
    assert review.metadata == {}


@pytest.mark.parametrize("field_name", ["review_id", "review_text"])
def test_review_record_rejects_blank_required_string(field_name: str) -> None:
    with pytest.raises(ValidationError):
        if field_name == "review_id":
            _valid_review(review_id="   ")
        else:
            _valid_review(review_text="   ")


def test_review_record_rejects_blank_listing_id() -> None:
    with pytest.raises(ValidationError):
        _valid_review(listing_id="   ")


def test_review_record_accepts_none_listing_id() -> None:
    review = _valid_review(listing_id=None)
    assert review.listing_id is None


def test_review_record_accepts_valid_rating() -> None:
    review = _valid_review(rating=4.5)
    assert review.rating == 4.5


def test_review_record_accepts_boundary_ratings() -> None:
    assert _valid_review(rating=0.0).rating == 0.0
    assert _valid_review(rating=5.0).rating == 5.0


def test_review_record_rejects_rating_above_5() -> None:
    with pytest.raises(ValidationError):
        _valid_review(rating=5.1)


def test_review_record_rejects_negative_rating() -> None:
    with pytest.raises(ValidationError):
        _valid_review(rating=-0.1)


def test_review_record_accepts_none_rating() -> None:
    review = _valid_review(rating=None)
    assert review.rating is None


def test_review_record_accepts_timezone_aware_created_at() -> None:
    dt = datetime(2024, 1, 1, tzinfo=timezone.utc)
    review = _valid_review(created_at=dt)
    assert review.created_at == dt


def test_review_record_accepts_none_created_at() -> None:
    review = _valid_review(created_at=None)
    assert review.created_at is None


def test_review_record_accepts_valid_metadata() -> None:
    review = _valid_review(metadata={"source": "airbnb"})
    assert review.metadata == {"source": "airbnb"}


def test_review_record_rejects_blank_metadata_key() -> None:
    with pytest.raises(ValidationError):
        _valid_review(metadata={"   ": "airbnb"})


def test_review_record_rejects_blank_metadata_value() -> None:
    with pytest.raises(ValidationError):
        _valid_review(metadata={"source": "   "})


# --- RsrSourceListingContext ---


def _valid_listing(**kwargs: object) -> RsrSourceListingContext:
    defaults: dict[str, object] = {"listing_id": "listing-001"}
    defaults.update(kwargs)
    return RsrSourceListingContext(**defaults)  # type: ignore[arg-type]


def test_listing_context_accepts_valid_minimal_record() -> None:
    listing = _valid_listing()
    assert listing.listing_id == "listing-001"


def test_listing_context_defaults_are_correct() -> None:
    listing = _valid_listing()
    assert listing.listing_name is None
    assert listing.property_type is None
    assert listing.bedrooms is None
    assert listing.bathrooms is None
    assert listing.accommodates is None
    assert listing.average_rating is None
    assert listing.metadata == {}


def test_listing_context_rejects_blank_listing_id() -> None:
    with pytest.raises(ValidationError):
        _valid_listing(listing_id="   ")


@pytest.mark.parametrize("field_name", ["listing_name", "property_type"])
def test_listing_context_rejects_blank_optional_string(field_name: str) -> None:
    with pytest.raises(ValidationError):
        if field_name == "listing_name":
            _valid_listing(listing_name="   ")
        else:
            _valid_listing(property_type="   ")


def test_listing_context_accepts_non_negative_bedrooms() -> None:
    assert _valid_listing(bedrooms=0).bedrooms == 0
    assert _valid_listing(bedrooms=3).bedrooms == 3


def test_listing_context_rejects_negative_bedrooms() -> None:
    with pytest.raises(ValidationError):
        _valid_listing(bedrooms=-1)


def test_listing_context_accepts_non_negative_accommodates() -> None:
    assert _valid_listing(accommodates=0).accommodates == 0
    assert _valid_listing(accommodates=6).accommodates == 6


def test_listing_context_rejects_negative_accommodates() -> None:
    with pytest.raises(ValidationError):
        _valid_listing(accommodates=-1)


def test_listing_context_accepts_non_negative_bathrooms() -> None:
    assert _valid_listing(bathrooms=0.0).bathrooms == 0.0
    assert _valid_listing(bathrooms=1.5).bathrooms == 1.5


def test_listing_context_rejects_negative_bathrooms() -> None:
    with pytest.raises(ValidationError):
        _valid_listing(bathrooms=-0.5)


def test_listing_context_accepts_valid_average_rating() -> None:
    assert _valid_listing(average_rating=4.8).average_rating == 4.8


def test_listing_context_accepts_boundary_average_ratings() -> None:
    assert _valid_listing(average_rating=0.0).average_rating == 0.0
    assert _valid_listing(average_rating=5.0).average_rating == 5.0


def test_listing_context_rejects_average_rating_above_5() -> None:
    with pytest.raises(ValidationError):
        _valid_listing(average_rating=5.1)


def test_listing_context_rejects_negative_average_rating() -> None:
    with pytest.raises(ValidationError):
        _valid_listing(average_rating=-0.1)


def test_listing_context_accepts_valid_metadata() -> None:
    listing = _valid_listing(metadata={"platform": "airbnb"})
    assert listing.metadata == {"platform": "airbnb"}


def test_listing_context_rejects_blank_metadata_key() -> None:
    with pytest.raises(ValidationError):
        _valid_listing(metadata={"   ": "airbnb"})


def test_listing_context_rejects_blank_metadata_value() -> None:
    with pytest.raises(ValidationError):
        _valid_listing(metadata={"platform": "   "})


# --- RsrSourceNeighborhoodContext ---


def _valid_neighborhood(**kwargs: object) -> RsrSourceNeighborhoodContext:
    defaults: dict[str, object] = {
        "market_name": "Austin",
        "neighborhood_name": "East Side",
    }
    defaults.update(kwargs)
    return RsrSourceNeighborhoodContext(**defaults)  # type: ignore[arg-type]


def test_neighborhood_context_accepts_valid_minimal_record() -> None:
    n = _valid_neighborhood()
    assert n.market_name == "Austin"
    assert n.neighborhood_name == "East Side"


def test_neighborhood_context_defaults_are_correct() -> None:
    n = _valid_neighborhood()
    assert n.city is None
    assert n.state is None
    assert n.country is None
    assert n.metadata == {}


@pytest.mark.parametrize("field_name", ["market_name", "neighborhood_name"])
def test_neighborhood_context_rejects_blank_required_string(field_name: str) -> None:
    with pytest.raises(ValidationError):
        if field_name == "market_name":
            _valid_neighborhood(market_name="   ")
        else:
            _valid_neighborhood(neighborhood_name="   ")


@pytest.mark.parametrize("field_name", ["city", "state", "country"])
def test_neighborhood_context_rejects_blank_optional_string(field_name: str) -> None:
    with pytest.raises(ValidationError):
        if field_name == "city":
            _valid_neighborhood(city="   ")
        elif field_name == "state":
            _valid_neighborhood(state="   ")
        else:
            _valid_neighborhood(country="   ")


@pytest.mark.parametrize("field_name", ["city", "state", "country"])
def test_neighborhood_context_accepts_none_optional_string(field_name: str) -> None:
    if field_name == "city":
        n = _valid_neighborhood(city=None)
        assert n.city is None
    elif field_name == "state":
        n = _valid_neighborhood(state=None)
        assert n.state is None
    else:
        n = _valid_neighborhood(country=None)
        assert n.country is None


def test_neighborhood_context_accepts_all_optional_fields() -> None:
    n = _valid_neighborhood(city="Austin", state="TX", country="US")
    assert n.city == "Austin"
    assert n.state == "TX"
    assert n.country == "US"


def test_neighborhood_context_accepts_valid_metadata() -> None:
    n = _valid_neighborhood(metadata={"region": "central"})
    assert n.metadata == {"region": "central"}


def test_neighborhood_context_rejects_blank_metadata_key() -> None:
    with pytest.raises(ValidationError):
        _valid_neighborhood(metadata={"   ": "central"})


def test_neighborhood_context_rejects_blank_metadata_value() -> None:
    with pytest.raises(ValidationError):
        _valid_neighborhood(metadata={"region": "   "})


# --- RsrSourceExtractionResult ---


def _valid_request() -> RsrSourceExtractionRequest:
    return RsrSourceExtractionRequest(market_name="Austin")


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _valid_result(**kwargs: object) -> RsrSourceExtractionResult:
    defaults: dict[str, object] = {
        "request": _valid_request(),
        "extracted_at_utc": _utc_now(),
    }
    defaults.update(kwargs)
    return RsrSourceExtractionResult(**defaults)  # type: ignore[arg-type]


def test_extraction_result_accepts_valid_minimal_record() -> None:
    result = _valid_result()
    assert result.source_name == "readysetrentables"
    assert result.source_version == "v0"


def test_extraction_result_defaults_are_correct() -> None:
    result = _valid_result()
    assert result.reviews == []
    assert result.listings == []
    assert result.neighborhood is None
    assert result.metadata == {}


def test_extraction_result_rejects_naive_extracted_at_utc() -> None:
    with pytest.raises(ValidationError):
        _valid_result(extracted_at_utc=datetime(2024, 1, 1))


def test_extraction_result_accepts_timezone_aware_extracted_at_utc() -> None:
    dt = datetime(2024, 6, 1, 12, 0, tzinfo=timezone.utc)
    result = _valid_result(extracted_at_utc=dt)
    assert result.extracted_at_utc == dt


@pytest.mark.parametrize("field_name", ["source_name", "source_version"])
def test_extraction_result_rejects_blank_required_string(field_name: str) -> None:
    with pytest.raises(ValidationError):
        if field_name == "source_name":
            _valid_result(source_name="   ")
        else:
            _valid_result(source_version="   ")


def test_extraction_result_accepts_reviews_list() -> None:
    reviews = [
        RsrSourceReviewRecord(review_id="r1", review_text="Excellent."),
        RsrSourceReviewRecord(review_id="r2", review_text="Very clean."),
    ]
    result = _valid_result(reviews=reviews)
    assert len(result.reviews) == 2


def test_extraction_result_accepts_listings_list() -> None:
    listings = [RsrSourceListingContext(listing_id="l1")]
    result = _valid_result(listings=listings)
    assert len(result.listings) == 1


def test_extraction_result_accepts_neighborhood_context() -> None:
    n = RsrSourceNeighborhoodContext(market_name="Austin", neighborhood_name="East Side")
    result = _valid_result(neighborhood=n)
    assert result.neighborhood is not None
    assert result.neighborhood.neighborhood_name == "East Side"


def test_extraction_result_accepts_none_neighborhood() -> None:
    result = _valid_result(neighborhood=None)
    assert result.neighborhood is None


def test_extraction_result_accepts_valid_metadata() -> None:
    result = _valid_result(metadata={"extraction_mode": "full"})
    assert result.metadata == {"extraction_mode": "full"}


def test_extraction_result_rejects_blank_metadata_key() -> None:
    with pytest.raises(ValidationError):
        _valid_result(metadata={"   ": "full"})


def test_extraction_result_rejects_blank_metadata_value() -> None:
    with pytest.raises(ValidationError):
        _valid_result(metadata={"extraction_mode": "   "})


def test_extraction_result_preserves_request() -> None:
    req = _valid_request()
    result = _valid_result(request=req)
    assert result.request.market_name == "Austin"
