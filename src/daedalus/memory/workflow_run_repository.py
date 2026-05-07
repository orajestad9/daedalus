"""Persistence repository for workflow run records.

This module maps the generic file-backed `WorkflowRunRecord` into the Phase 1
Postgres `workflow_runs` table. It deliberately accepts an existing connection
and does not commit, so callers can decide transaction boundaries when workflow
persistence is wired into orchestration later.
"""

from collections.abc import Sequence
from datetime import datetime
from pathlib import Path
from typing import Any
from uuid import UUID

import psycopg

from daedalus.orchestrator.run_record import WorkflowRunRecord
from daedalus.orchestrator.status import WorkflowStatus


MAX_LIST_RECENT_LIMIT = 100
MIN_LIST_RECENT_LIMIT = 1


class WorkflowRunRepository:
    """Save and retrieve workflow run records using parameterized SQL."""

    def __init__(self, connection: psycopg.Connection[Any]) -> None:
        self._connection = connection

    def save(self, record: WorkflowRunRecord) -> None:
        """Insert one workflow run record without committing the transaction."""
        self._connection.execute(
            """
            INSERT INTO workflow_runs (
                run_id,
                workflow_name,
                domain,
                status,
                started_at_utc,
                completed_at_utc,
                source_input_path,
                output_artifact_path,
                metadata_artifact_path,
                summary_artifact_path,
                run_record_artifact_path,
                review_count,
                approval_required,
                approved
            )
            VALUES (
                %s, %s, %s, %s, %s, %s, %s,
                %s, %s, %s, %s, %s, %s, %s
            )
            """,
            _params_from_record(record),
        )

    def get_by_run_id(self, run_id: UUID) -> WorkflowRunRecord | None:
        """Return a workflow run record by ID, or None when it does not exist."""
        cursor = self._connection.execute(
            """
            SELECT
                run_id,
                workflow_name,
                domain,
                status,
                started_at_utc,
                completed_at_utc,
                source_input_path,
                output_artifact_path,
                metadata_artifact_path,
                summary_artifact_path,
                run_record_artifact_path,
                review_count,
                approval_required,
                approved
            FROM workflow_runs
            WHERE run_id = %s
            """,
            (run_id,),
        )
        row = cursor.fetchone()
        if row is None:
            return None

        return _record_from_row(row)

    def list_recent(
        self,
        limit: int = 10,
        domain: str | None = None,
        status: str | None = None,
    ) -> list[WorkflowRunRecord]:
        """List recent workflow runs, optionally filtered by domain and status."""
        validated_limit = _validate_limit(limit)
        conditions: list[str] = []
        params: list[object] = []

        if domain is not None:
            conditions.append("domain = %s")
            params.append(domain)
        if status is not None:
            conditions.append("status = %s")
            params.append(status)

        where_clause = ""
        if conditions:
            where_clause = f"WHERE {' AND '.join(conditions)}"

        params.append(validated_limit)
        cursor = self._connection.execute(
            f"""
            SELECT
                run_id,
                workflow_name,
                domain,
                status,
                started_at_utc,
                completed_at_utc,
                source_input_path,
                output_artifact_path,
                metadata_artifact_path,
                summary_artifact_path,
                run_record_artifact_path,
                review_count,
                approval_required,
                approved
            FROM workflow_runs
            {where_clause}
            ORDER BY created_at_utc DESC
            LIMIT %s
            """,
            tuple(params),
        )
        return [_record_from_row(row) for row in cursor.fetchall()]


def _params_from_record(record: WorkflowRunRecord) -> tuple[object, ...]:
    return (
        record.run_id,
        str(record.workflow_name),
        str(record.domain),
        record.status.value,
        record.started_at_utc,
        record.completed_at_utc,
        str(record.source_input_path),
        str(record.output_artifact_path),
        str(record.metadata_artifact_path),
        str(record.summary_artifact_path),
        str(record.run_record_artifact_path),
        record.review_count,
        record.approval_required,
        record.approved,
    )


def _record_from_row(row: Sequence[Any]) -> WorkflowRunRecord:
    return WorkflowRunRecord(
        run_id=_uuid_from_value(row[0]),
        workflow_name=str(row[1]),
        domain=str(row[2]),
        status=WorkflowStatus(str(row[3])),
        started_at_utc=_datetime_from_value(row[4]),
        completed_at_utc=_datetime_from_value(row[5]),
        source_input_path=Path(str(row[6])),
        output_artifact_path=Path(str(row[7])),
        metadata_artifact_path=Path(str(row[8])),
        summary_artifact_path=Path(str(row[9])),
        run_record_artifact_path=Path(str(row[10])),
        review_count=int(row[11]),
        approval_required=bool(row[12]),
        approved=bool(row[13]),
    )


def _validate_limit(limit: int) -> int:
    if limit < MIN_LIST_RECENT_LIMIT or limit > MAX_LIST_RECENT_LIMIT:
        msg = (
            "Workflow run list limit must be between "
            f"{MIN_LIST_RECENT_LIMIT} and {MAX_LIST_RECENT_LIMIT}"
        )
        raise ValueError(msg)

    return limit


def _uuid_from_value(value: object) -> UUID:
    if isinstance(value, UUID):
        return value
    return UUID(str(value))


def _datetime_from_value(value: object) -> datetime:
    if isinstance(value, datetime):
        return value

    msg = "Workflow run timestamp columns must be returned as datetimes"
    raise TypeError(msg)
