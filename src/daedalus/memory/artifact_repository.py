"""Persistence repository for workflow artifact records.

Artifact rows are deliberately stored separately from workflow run rows so
future workflows can emit any number of machine-readable or human-readable
artifacts without changing the run table shape. Like the workflow run
repository, this class accepts an existing connection and leaves commits to the
caller.
"""

from collections.abc import Sequence
from datetime import datetime
from pathlib import Path
from typing import Any
from uuid import UUID

import psycopg

from daedalus.orchestrator.artifact_record import ArtifactRecord
from daedalus.orchestrator.artifact_type import ArtifactType


class ArtifactRepository:
    """Save and list workflow artifact records using parameterized SQL."""

    def __init__(self, connection: psycopg.Connection[Any]) -> None:
        self._connection = connection

    def save(self, record: ArtifactRecord) -> None:
        """Insert one artifact record without committing the transaction."""
        self._connection.execute(
            """
            INSERT INTO workflow_artifacts (
                artifact_id,
                run_id,
                artifact_type,
                artifact_path,
                created_at_utc
            )
            VALUES (%s, %s, %s, %s, %s)
            """,
            _params_from_record(record),
        )

    def list_for_run(self, run_id: UUID) -> list[ArtifactRecord]:
        """List artifacts for a workflow run ordered by creation time."""
        cursor = self._connection.execute(
            """
            SELECT
                artifact_id,
                run_id,
                artifact_type,
                artifact_path,
                created_at_utc
            FROM workflow_artifacts
            WHERE run_id = %s
            ORDER BY created_at_utc ASC
            """,
            (run_id,),
        )
        return [_record_from_row(row) for row in cursor.fetchall()]


def _params_from_record(record: ArtifactRecord) -> tuple[object, ...]:
    return (
        record.artifact_id,
        record.run_id,
        record.artifact_type.value,
        str(record.artifact_path),
        record.created_at_utc,
    )


def _record_from_row(row: Sequence[Any]) -> ArtifactRecord:
    return ArtifactRecord(
        artifact_id=_uuid_from_value(row[0]),
        run_id=_uuid_from_value(row[1]),
        artifact_type=ArtifactType(str(row[2])),
        artifact_path=Path(str(row[3])),
        created_at_utc=_datetime_from_value(row[4]),
    )


def _uuid_from_value(value: object) -> UUID:
    if isinstance(value, UUID):
        return value
    return UUID(str(value))


def _datetime_from_value(value: object) -> datetime:
    if isinstance(value, datetime):
        return value

    msg = "Artifact timestamp columns must be returned as datetimes"
    raise TypeError(msg)
