"""Persistence repository for model invocation records.

Model invocation rows store provider/model metadata, token and cost fields, and
artifact paths for future observability. Raw prompt text and raw response text
are intentionally not part of this repository contract.
"""

from collections.abc import Sequence
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from typing import Any
from uuid import UUID

import psycopg

from daedalus.model_clients.invocation_record import (
    ModelInvocationRecord,
    ModelInvocationStatus,
)
from daedalus.model_clients.types import ModelProvider


class ModelInvocationRepository:
    """Save and list model invocation records using parameterized SQL."""

    def __init__(self, connection: psycopg.Connection[Any]) -> None:
        self._connection = connection

    def save(self, record: ModelInvocationRecord) -> None:
        """Insert one model invocation record without committing the transaction."""
        self._connection.execute(
            """
            INSERT INTO model_invocations (
                invocation_id,
                run_id,
                step_id,
                agent_name,
                provider,
                model_name,
                prompt_name,
                prompt_version,
                input_tokens,
                output_tokens,
                total_tokens,
                estimated_cost_usd,
                status,
                started_at_utc,
                completed_at_utc,
                duration_ms,
                input_artifact_path,
                output_artifact_path,
                error_message
            )
            VALUES (
                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                %s, %s, %s, %s, %s, %s, %s, %s, %s
            )
            """,
            _params_from_record(record),
        )

    def list_for_run(self, run_id: UUID) -> list[ModelInvocationRecord]:
        """List model invocations for a workflow run ordered by start time."""
        cursor = self._connection.execute(
            """
            SELECT
                invocation_id,
                run_id,
                step_id,
                agent_name,
                provider,
                model_name,
                prompt_name,
                prompt_version,
                input_tokens,
                output_tokens,
                total_tokens,
                estimated_cost_usd,
                status,
                started_at_utc,
                completed_at_utc,
                duration_ms,
                input_artifact_path,
                output_artifact_path,
                error_message
            FROM model_invocations
            WHERE run_id = %s
            ORDER BY started_at_utc ASC
            """,
            (run_id,),
        )
        return [_record_from_row(row) for row in cursor.fetchall()]

    def list_for_step(self, step_id: UUID) -> list[ModelInvocationRecord]:
        """List model invocations for a workflow step ordered by start time."""
        cursor = self._connection.execute(
            """
            SELECT
                invocation_id,
                run_id,
                step_id,
                agent_name,
                provider,
                model_name,
                prompt_name,
                prompt_version,
                input_tokens,
                output_tokens,
                total_tokens,
                estimated_cost_usd,
                status,
                started_at_utc,
                completed_at_utc,
                duration_ms,
                input_artifact_path,
                output_artifact_path,
                error_message
            FROM model_invocations
            WHERE step_id = %s
            ORDER BY started_at_utc ASC
            """,
            (step_id,),
        )
        return [_record_from_row(row) for row in cursor.fetchall()]


def _params_from_record(record: ModelInvocationRecord) -> tuple[object, ...]:
    return (
        record.invocation_id,
        record.run_id,
        record.step_id,
        record.agent_name,
        record.provider.value,
        record.model_name,
        record.prompt_name,
        record.prompt_version,
        record.input_tokens,
        record.output_tokens,
        record.total_tokens,
        record.estimated_cost_usd,
        record.status.value,
        record.started_at_utc,
        record.completed_at_utc,
        record.duration_ms,
        None if record.input_artifact_path is None else str(record.input_artifact_path),
        None if record.output_artifact_path is None else str(record.output_artifact_path),
        record.error_message,
    )


def _record_from_row(row: Sequence[Any]) -> ModelInvocationRecord:
    return ModelInvocationRecord(
        invocation_id=_uuid_from_value(row[0]),
        run_id=_uuid_from_value(row[1]),
        step_id=_optional_uuid_from_value(row[2]),
        agent_name=None if row[3] is None else str(row[3]),
        provider=ModelProvider(str(row[4])),
        model_name=str(row[5]),
        prompt_name=str(row[6]),
        prompt_version=str(row[7]),
        input_tokens=_optional_int_from_value(row[8]),
        output_tokens=_optional_int_from_value(row[9]),
        total_tokens=_optional_int_from_value(row[10]),
        estimated_cost_usd=_optional_decimal_from_value(row[11]),
        status=ModelInvocationStatus(str(row[12])),
        started_at_utc=_datetime_from_value(row[13], "started_at_utc"),
        completed_at_utc=_datetime_from_value(row[14], "completed_at_utc"),
        duration_ms=int(row[15]),
        input_artifact_path=_optional_path_from_value(row[16]),
        output_artifact_path=_optional_path_from_value(row[17]),
        error_message=None if row[18] is None else str(row[18]),
    )


def _uuid_from_value(value: object) -> UUID:
    if isinstance(value, UUID):
        return value
    return UUID(str(value))


def _optional_uuid_from_value(value: object) -> UUID | None:
    if value is None:
        return None
    return _uuid_from_value(value)


def _datetime_from_value(value: object, name: str) -> datetime:
    if isinstance(value, datetime):
        return value

    msg = f"Model invocation {name} column must be returned as a datetime"
    raise TypeError(msg)


def _optional_int_from_value(value: object) -> int | None:
    if value is None:
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        return int(value)

    msg = "Model invocation token columns must be returned as integers"
    raise TypeError(msg)


def _optional_decimal_from_value(value: object) -> Decimal | None:
    if value is None:
        return None
    if isinstance(value, Decimal):
        return value
    return Decimal(str(value))


def _optional_path_from_value(value: object) -> Path | None:
    if value is None:
        return None
    return Path(str(value))
