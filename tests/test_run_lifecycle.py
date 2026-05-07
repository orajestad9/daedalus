from datetime import UTC, datetime, timedelta

import pytest

from daedalus.orchestrator.run_lifecycle import calculate_duration_ms, utc_now


def test_utc_now_returns_timezone_aware_utc_datetime() -> None:
    timestamp = utc_now()

    assert timestamp.tzinfo is not None
    assert timestamp.utcoffset() == timedelta(0)


def test_calculate_duration_ms_returns_expected_milliseconds() -> None:
    started_at = datetime(2026, 5, 7, 10, 0, 0, 100_000, tzinfo=UTC)
    completed_at = datetime(2026, 5, 7, 10, 0, 1, 350_000, tzinfo=UTC)

    assert calculate_duration_ms(started_at, completed_at) == 1_250


def test_calculate_duration_ms_returns_zero_for_equal_timestamps() -> None:
    timestamp = datetime(2026, 5, 7, 10, 0, tzinfo=UTC)

    assert calculate_duration_ms(timestamp, timestamp) == 0


def test_calculate_duration_ms_rejects_completed_before_started() -> None:
    started_at = datetime(2026, 5, 7, 10, 0, 1, tzinfo=UTC)
    completed_at = datetime(2026, 5, 7, 10, 0, tzinfo=UTC)

    with pytest.raises(ValueError, match="completed_at_utc"):
        calculate_duration_ms(started_at, completed_at)


def test_calculate_duration_ms_rejects_naive_datetimes() -> None:
    started_at = datetime(2026, 5, 7, 10, 0)
    completed_at = datetime(2026, 5, 7, 10, 0, 1, tzinfo=UTC)

    with pytest.raises(ValueError, match="started_at_utc"):
        calculate_duration_ms(started_at, completed_at)
