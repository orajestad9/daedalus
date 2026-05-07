"""Persistence repository for workflow step records."""

from collections.abc import Sequence
from datetime import datetime
from typing import Any
from uuid import UUID

import psycopg

from daedalus.orchestrator.status import WorkflowStatus
from daedalus.orchestrator.step_record import WorkflowStepRecord


class WorkflowStepRepository:
    """Save and list workflow step records using parameterized SQL."""

    def __init__(self, connection: psycopg.Connection[Any]) -> None:
        self._connection = connection

    def save(self, record: WorkflowStepRecord) -> None:
        """Insert one workflow step record without committing the transaction."""
        self._connection.execute(
            """
            INSERT INTO workflow_steps (
                step_id,
                run_id,
                step_name,
                status,
                started_at_utc,
                completed_at_utc,
                duration_ms,
                error_message
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """,
            _params_from_record(record),
        )

    def list_for_run(self, run_id: UUID) -> list[WorkflowStepRecord]:
        """List step records for a workflow run ordered by start time."""
        cursor = self._connection.execute(
            """
            SELECT
                step_id,
                run_id,
                step_name,
                status,
                started_at_utc,
                completed_at_utc,
                duration_ms,
                error_message
            FROM workflow_steps
            WHERE run_id = %s
            ORDER BY started_at_utc ASC
            """,
            (run_id,),
        )
        return [_record_from_row(row) for row in cursor.fetchall()]


def _params_from_record(record: WorkflowStepRecord) -> tuple[object, ...]:
    return (
        record.step_id,
        record.run_id,
        record.step_name,
        record.status.value,
        record.started_at_utc,
        record.completed_at_utc,
        record.duration_ms,
        record.error_message,
    )


def _record_from_row(row: Sequence[Any]) -> WorkflowStepRecord:
    return WorkflowStepRecord(
        step_id=_uuid_from_value(row[0]),
        run_id=_uuid_from_value(row[1]),
        step_name=str(row[2]),
        status=WorkflowStatus(str(row[3])),
        started_at_utc=_datetime_from_value(row[4], "started_at_utc"),
        completed_at_utc=_optional_datetime_from_value(row[5], "completed_at_utc"),
        duration_ms=_optional_int_from_value(row[6]),
        error_message=None if row[7] is None else str(row[7]),
    )


def _uuid_from_value(value: object) -> UUID:
    if isinstance(value, UUID):
        return value
    return UUID(str(value))


def _datetime_from_value(value: object, name: str) -> datetime:
    if isinstance(value, datetime):
        return value

    msg = f"Workflow step {name} column must be returned as a datetime"
    raise TypeError(msg)


def _optional_datetime_from_value(value: object, name: str) -> datetime | None:
    if value is None:
        return None
    return _datetime_from_value(value, name)


def _optional_int_from_value(value: object) -> int | None:
    if value is None:
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        return int(value)

    msg = "Workflow step duration_ms column must be returned as an integer"
    raise TypeError(msg)
