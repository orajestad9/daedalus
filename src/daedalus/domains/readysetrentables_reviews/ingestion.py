import csv
from collections.abc import Sequence
from datetime import date
from pathlib import Path

from daedalus.domains.readysetrentables_reviews.models import (
    NormalizedReview,
    RawReviewRecord,
    ReviewBatch,
)


REQUIRED_COLUMNS = frozenset({"review_id", "review_text"})


def load_airbnb_reviews_csv(csv_path: Path) -> ReviewBatch:
    """Load Airbnb review CSV data into a normalized review batch."""
    if not csv_path.exists():
        raise FileNotFoundError(csv_path)

    with csv_path.open(newline="", encoding="utf-8") as csv_file:
        reader = csv.DictReader(csv_file)
        _validate_required_columns(reader.fieldnames)

        reviews = [
            _row_to_normalized_review(row=row, row_number=row_number)
            for row_number, row in enumerate(reader, start=2)
        ]

    return ReviewBatch(reviews=reviews)


def _validate_required_columns(fieldnames: Sequence[str] | None) -> None:
    if fieldnames is None:
        required_columns = ", ".join(sorted(REQUIRED_COLUMNS))
        msg = f"CSV is missing a header row with required columns: {required_columns}"
        raise ValueError(msg)

    missing_columns = REQUIRED_COLUMNS.difference(fieldnames)
    if missing_columns:
        missing = ", ".join(sorted(missing_columns))
        msg = f"CSV is missing required column(s): {missing}"
        raise ValueError(msg)


def _row_to_normalized_review(
    *,
    row: dict[str, str | None],
    row_number: int,
) -> NormalizedReview:
    raw_record = RawReviewRecord(source_data=dict(row))

    return NormalizedReview(
        review_id=_required_text(row, "review_id", row_number),
        property_id=_optional_text(row, "property_id"),
        reviewer_name=_optional_text(row, "reviewer_name"),
        review_text=_required_text(row, "review_text", row_number),
        review_date=_optional_date(row.get("review_date"), row_number),
        rating=_optional_rating(row.get("rating"), row_number),
        language=_optional_text(row, "language"),
        country=_optional_text(row, "country"),
        raw_record=raw_record,
    )


def _required_text(row: dict[str, str | None], column_name: str, row_number: int) -> str:
    value = row.get(column_name)
    if value is None or not value.strip():
        msg = f"Row {row_number} has empty required field: {column_name}"
        raise ValueError(msg)

    return value.strip()


def _optional_text(row: dict[str, str | None], column_name: str) -> str | None:
    value = row.get(column_name)
    if value is None or not value.strip():
        return None

    return value.strip()


def _optional_rating(value: str | None, row_number: int) -> float | None:
    if value is None or not value.strip():
        return None

    try:
        rating = float(value)
    except ValueError as exc:
        msg = f"Row {row_number} has invalid rating: {value!r}"
        raise ValueError(msg) from exc

    if rating < 0 or rating > 5:
        msg = f"Row {row_number} has invalid rating outside 0-5 range: {value!r}"
        raise ValueError(msg)

    return rating


def _optional_date(value: str | None, row_number: int) -> date | None:
    if value is None or not value.strip():
        return None

    try:
        return date.fromisoformat(value.strip())
    except ValueError as exc:
        msg = f"Row {row_number} has invalid review_date, expected YYYY-MM-DD: {value!r}"
        raise ValueError(msg) from exc
