"""Shared lifecycle timing helpers for workflow runs."""

from datetime import UTC, datetime


def utc_now() -> datetime:
    """Return a timezone-aware UTC timestamp."""
    return datetime.now(UTC)


def calculate_duration_ms(started_at_utc: datetime, completed_at_utc: datetime) -> int:
    """Calculate non-negative elapsed milliseconds between two UTC timestamps."""
    _require_timezone_aware(started_at_utc, "started_at_utc")
    _require_timezone_aware(completed_at_utc, "completed_at_utc")

    elapsed = completed_at_utc - started_at_utc
    if elapsed.total_seconds() < 0:
        msg = "completed_at_utc must not be earlier than started_at_utc"
        raise ValueError(msg)

    return int(elapsed.total_seconds() * 1000)


def _require_timezone_aware(value: datetime, name: str) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        msg = f"{name} must be timezone-aware"
        raise ValueError(msg)
