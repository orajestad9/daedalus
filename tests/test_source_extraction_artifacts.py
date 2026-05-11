import json
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from daedalus.domains.readysetrentables_reviews.source_extraction_artifacts import (
    write_rsr_source_extract_json,
)
from daedalus.domains.readysetrentables_reviews.source_extraction_models import (
    RsrSourceExtractionRequest,
    RsrSourceExtractionResult,
    RsrSourceListingContext,
    RsrSourceNeighborhoodContext,
    RsrSourceReviewRecord,
)


def _valid_request() -> RsrSourceExtractionRequest:
    return RsrSourceExtractionRequest(market_name="Austin")


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _minimal_result(**kwargs: object) -> RsrSourceExtractionResult:
    defaults: dict[str, object] = {
        "request": _valid_request(),
        "extracted_at_utc": _utc_now(),
    }
    defaults.update(kwargs)
    return RsrSourceExtractionResult(**defaults)  # type: ignore[arg-type]


def test_writer_creates_rsr_source_extract_json(tmp_path: Path) -> None:
    output_path = tmp_path / "rsr_source_extract.json"

    write_rsr_source_extract_json(result=_minimal_result(), output_path=output_path)

    assert output_path.exists()


def test_writer_creates_parent_directory(tmp_path: Path) -> None:
    output_path = tmp_path / "nested" / "subdir" / "rsr_source_extract.json"

    write_rsr_source_extract_json(result=_minimal_result(), output_path=output_path)

    assert output_path.exists()


def test_writer_returns_output_path(tmp_path: Path) -> None:
    output_path = tmp_path / "rsr_source_extract.json"

    returned = write_rsr_source_extract_json(result=_minimal_result(), output_path=output_path)

    assert returned == output_path


def test_writer_produces_parseable_json(tmp_path: Path) -> None:
    output_path = tmp_path / "rsr_source_extract.json"

    write_rsr_source_extract_json(result=_minimal_result(), output_path=output_path)
    data = json.loads(output_path.read_text(encoding="utf-8"))

    assert isinstance(data, dict)


def test_writer_includes_request(tmp_path: Path) -> None:
    output_path = tmp_path / "rsr_source_extract.json"
    req = _valid_request()

    write_rsr_source_extract_json(result=_minimal_result(request=req), output_path=output_path)
    data = json.loads(output_path.read_text(encoding="utf-8"))

    assert "request" in data
    assert data["request"]["market_name"] == "Austin"


def test_writer_includes_extracted_at_utc(tmp_path: Path) -> None:
    output_path = tmp_path / "rsr_source_extract.json"
    dt = datetime(2024, 6, 1, 12, 0, tzinfo=timezone.utc)

    write_rsr_source_extract_json(
        result=_minimal_result(extracted_at_utc=dt), output_path=output_path
    )
    data = json.loads(output_path.read_text(encoding="utf-8"))

    assert "extracted_at_utc" in data
    assert isinstance(data["extracted_at_utc"], str)


def test_writer_includes_source_name_and_version(tmp_path: Path) -> None:
    output_path = tmp_path / "rsr_source_extract.json"

    write_rsr_source_extract_json(result=_minimal_result(), output_path=output_path)
    data = json.loads(output_path.read_text(encoding="utf-8"))

    assert data["source_name"] == "readysetrentables"
    assert data["source_version"] == "v0"


def test_writer_includes_reviews(tmp_path: Path) -> None:
    output_path = tmp_path / "rsr_source_extract.json"
    reviews = [
        RsrSourceReviewRecord(review_id="r1", review_text="Great location."),
        RsrSourceReviewRecord(review_id="r2", review_text="Very clean."),
    ]

    write_rsr_source_extract_json(result=_minimal_result(reviews=reviews), output_path=output_path)
    data = json.loads(output_path.read_text(encoding="utf-8"))

    assert len(data["reviews"]) == 2
    assert data["reviews"][0]["review_id"] == "r1"
    assert data["reviews"][1]["review_id"] == "r2"


def test_writer_includes_listings(tmp_path: Path) -> None:
    output_path = tmp_path / "rsr_source_extract.json"
    listings = [RsrSourceListingContext(listing_id="l1", bedrooms=2)]

    write_rsr_source_extract_json(
        result=_minimal_result(listings=listings), output_path=output_path
    )
    data = json.loads(output_path.read_text(encoding="utf-8"))

    assert len(data["listings"]) == 1
    assert data["listings"][0]["listing_id"] == "l1"


def test_writer_includes_neighborhood_when_present(tmp_path: Path) -> None:
    output_path = tmp_path / "rsr_source_extract.json"
    neighborhood = RsrSourceNeighborhoodContext(market_name="Austin", neighborhood_name="East Side")

    write_rsr_source_extract_json(
        result=_minimal_result(neighborhood=neighborhood), output_path=output_path
    )
    data = json.loads(output_path.read_text(encoding="utf-8"))

    assert data["neighborhood"] is not None
    assert data["neighborhood"]["neighborhood_name"] == "East Side"


def test_writer_includes_neighborhood_as_null_when_none(tmp_path: Path) -> None:
    output_path = tmp_path / "rsr_source_extract.json"

    write_rsr_source_extract_json(
        result=_minimal_result(neighborhood=None), output_path=output_path
    )
    data = json.loads(output_path.read_text(encoding="utf-8"))

    assert data["neighborhood"] is None


def test_writer_includes_metadata(tmp_path: Path) -> None:
    output_path = tmp_path / "rsr_source_extract.json"

    write_rsr_source_extract_json(
        result=_minimal_result(metadata={"extraction_mode": "full"}), output_path=output_path
    )
    data = json.loads(output_path.read_text(encoding="utf-8"))

    assert data["metadata"] == {"extraction_mode": "full"}


def test_writer_handles_empty_reviews_and_listings(tmp_path: Path) -> None:
    output_path = tmp_path / "rsr_source_extract.json"

    write_rsr_source_extract_json(result=_minimal_result(), output_path=output_path)
    data = json.loads(output_path.read_text(encoding="utf-8"))

    assert data["reviews"] == []
    assert data["listings"] == []


def test_writer_serializes_extracted_at_utc_as_string(tmp_path: Path) -> None:
    output_path = tmp_path / "rsr_source_extract.json"
    dt = datetime(2024, 1, 15, 8, 30, tzinfo=timezone.utc)

    write_rsr_source_extract_json(
        result=_minimal_result(extracted_at_utc=dt), output_path=output_path
    )
    data = json.loads(output_path.read_text(encoding="utf-8"))

    assert isinstance(data["extracted_at_utc"], str)
    assert "2024" in data["extracted_at_utc"]


def test_writer_produces_indented_json(tmp_path: Path) -> None:
    output_path = tmp_path / "rsr_source_extract.json"

    write_rsr_source_extract_json(result=_minimal_result(), output_path=output_path)
    raw = output_path.read_text(encoding="utf-8")

    assert "\n" in raw


def test_writer_request_id_is_serialized(tmp_path: Path) -> None:
    output_path = tmp_path / "rsr_source_extract.json"
    rid = uuid4()
    req = RsrSourceExtractionRequest(request_id=rid, market_name="Austin")

    write_rsr_source_extract_json(result=_minimal_result(request=req), output_path=output_path)
    data = json.loads(output_path.read_text(encoding="utf-8"))

    assert data["request"]["request_id"] == str(rid)
