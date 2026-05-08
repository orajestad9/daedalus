"""Workflow persistence coordination for completed Daedalus runs.

Repositories own SQL, while this service owns the small transaction-neutral
sequence of saving a run record and its artifact records. The connection helper
below is opt-in and used by CLI persistence only, keeping normal workflow runs
file-only unless the caller explicitly asks for Postgres persistence.
"""

import logging
from collections.abc import Sequence
from uuid import UUID

from pydantic import BaseModel, Field

from daedalus.config import load_postgres_settings
from daedalus.domains.readysetrentables_reviews.workflow import (
    ReviewNormalizationWorkflowResult,
)
from daedalus.memory.artifact_repository import ArtifactRepository
from daedalus.memory.model_invocation_repository import ModelInvocationRepository
from daedalus.memory.postgres import connect_postgres
from daedalus.memory.workflow_run_repository import WorkflowRunRepository
from daedalus.memory.workflow_step_repository import WorkflowStepRepository
from daedalus.model_clients.invocation_record import ModelInvocationRecord
from daedalus.orchestrator.artifact_record import ArtifactRecord
from daedalus.orchestrator.artifact_type import ArtifactType
from daedalus.orchestrator.run_record import WorkflowRunRecord
from daedalus.orchestrator.step_record import WorkflowStepRecord


logger = logging.getLogger(__name__)


class WorkflowPersistenceError(RuntimeError):
    """Raised when an explicit workflow persistence attempt fails."""


class WorkflowRunNotFoundError(LookupError):
    """Raised when a persisted workflow run cannot be found."""


class WorkflowRunDetails(BaseModel):
    """Read model for a persisted workflow run and related inspection records."""

    run_record: WorkflowRunRecord
    artifact_records: list[ArtifactRecord]
    step_records: list[WorkflowStepRecord]
    model_invocation_records: list[ModelInvocationRecord] = Field(default_factory=list)


class WorkflowPersistenceService:
    """Persist completed workflow run and artifact records."""

    def __init__(
        self,
        workflow_run_repository: WorkflowRunRepository,
        artifact_repository: ArtifactRepository,
        workflow_step_repository: WorkflowStepRepository | None = None,
    ) -> None:
        self._workflow_run_repository = workflow_run_repository
        self._artifact_repository = artifact_repository
        self._workflow_step_repository = workflow_step_repository

    def persist_completed_workflow(
        self,
        *,
        run_record: WorkflowRunRecord,
        artifact_records: Sequence[ArtifactRecord],
    ) -> int:
        """Save a completed workflow run and return the number of artifacts saved."""
        self._workflow_run_repository.save(run_record)
        for artifact_record in artifact_records:
            self._artifact_repository.save(artifact_record)

        return len(artifact_records)

    def save_review_normalization_run(
        self,
        record: WorkflowRunRecord,
        steps: list[WorkflowStepRecord] | None = None,
    ) -> list[ArtifactRecord]:
        """Save a review normalization run, optional steps, and artifact records."""
        if steps and self._workflow_step_repository is None:
            msg = "Step persistence requires WorkflowStepRepository"
            raise ValueError(msg)

        self._workflow_run_repository.save(record)
        for step in steps or []:
            if self._workflow_step_repository is not None:
                self._workflow_step_repository.save(step)

        artifact_records = _artifact_records_from_run_record(record)
        for artifact_record in artifact_records:
            self._artifact_repository.save(artifact_record)

        return artifact_records


def persist_review_normalization_workflow_result(
    result: ReviewNormalizationWorkflowResult,
) -> int:
    """Persist a completed review normalization workflow result to Postgres.

    This is the opt-in boundary that loads local DB settings. It never builds or
    logs password-bearing DSNs, and it leaves the default workflow execution path
    free from any database requirement.
    """
    logger.info("Persistence requested run_id=%s", result.run_id)
    settings = load_postgres_settings()
    connection = connect_postgres(settings)

    try:
        service = WorkflowPersistenceService(
            workflow_run_repository=WorkflowRunRepository(connection),
            artifact_repository=ArtifactRepository(connection),
            workflow_step_repository=WorkflowStepRepository(connection),
        )
        artifact_records = service.save_review_normalization_run(
            record=_run_record_from_result(result),
            steps=result.steps,
        )
        connection.commit()
        logger.info(
            "Persistence completed run_id=%s artifact_count=%s step_count=%s",
            result.run_id,
            len(artifact_records),
            len(result.steps),
        )
    except Exception as exc:
        connection.rollback()
        msg = "Failed to persist workflow run"
        raise WorkflowPersistenceError(msg) from exc
    finally:
        connection.close()

    return len(artifact_records)


def load_workflow_run_details(run_id: UUID) -> WorkflowRunDetails:
    """Load a persisted workflow run and its artifacts from Postgres."""
    settings = load_postgres_settings()
    connection = connect_postgres(settings)

    try:
        workflow_run_repository = WorkflowRunRepository(connection)
        artifact_repository = ArtifactRepository(connection)
        workflow_step_repository = WorkflowStepRepository(connection)
        model_invocation_repository = ModelInvocationRepository(connection)
        run_record = workflow_run_repository.get_by_run_id(run_id)
        if run_record is None:
            msg = f"Workflow run not found: run_id={run_id}"
            raise WorkflowRunNotFoundError(msg)

        return WorkflowRunDetails(
            run_record=run_record,
            artifact_records=artifact_repository.list_for_run(run_id),
            step_records=workflow_step_repository.list_for_run(run_id),
            model_invocation_records=model_invocation_repository.list_for_run(run_id),
        )
    except WorkflowRunNotFoundError:
        raise
    except Exception as exc:
        msg = "Failed to load workflow run"
        raise WorkflowPersistenceError(msg) from exc
    finally:
        connection.close()


def load_recent_workflow_runs(
    *,
    limit: int = 10,
    domain: str | None = None,
    status: str | None = None,
) -> list[WorkflowRunRecord]:
    """Load recent persisted workflow runs from Postgres."""
    settings = load_postgres_settings()
    connection = connect_postgres(settings)

    try:
        return WorkflowRunRepository(connection).list_recent(
            limit=limit,
            domain=domain,
            status=status,
        )
    except ValueError:
        raise
    except Exception as exc:
        msg = "Failed to list workflow runs"
        raise WorkflowPersistenceError(msg) from exc
    finally:
        connection.close()


def _run_record_from_result(result: ReviewNormalizationWorkflowResult) -> WorkflowRunRecord:
    return WorkflowRunRecord.model_validate_json(
        result.run_record_json_path.read_text(encoding="utf-8")
    )


def _artifact_records_from_result(
    result: ReviewNormalizationWorkflowResult,
) -> list[ArtifactRecord]:
    return [
        ArtifactRecord.create(
            run_id=result.run_id,
            artifact_type=ArtifactType.NORMALIZED_REVIEWS,
            artifact_path=result.output_json_path,
        ),
        ArtifactRecord.create(
            run_id=result.run_id,
            artifact_type=ArtifactType.REVIEW_METADATA,
            artifact_path=result.metadata_json_path,
        ),
        ArtifactRecord.create(
            run_id=result.run_id,
            artifact_type=ArtifactType.WORKFLOW_SUMMARY,
            artifact_path=result.summary_markdown_path,
        ),
        ArtifactRecord.create(
            run_id=result.run_id,
            artifact_type=ArtifactType.WORKFLOW_RUN_RECORD,
            artifact_path=result.run_record_json_path,
        ),
    ]


def _artifact_records_from_run_record(record: WorkflowRunRecord) -> list[ArtifactRecord]:
    return [
        ArtifactRecord.create(
            run_id=record.run_id,
            artifact_type=ArtifactType.NORMALIZED_REVIEWS,
            artifact_path=record.output_artifact_path,
        ),
        ArtifactRecord.create(
            run_id=record.run_id,
            artifact_type=ArtifactType.REVIEW_METADATA,
            artifact_path=record.metadata_artifact_path,
        ),
        ArtifactRecord.create(
            run_id=record.run_id,
            artifact_type=ArtifactType.WORKFLOW_SUMMARY,
            artifact_path=record.summary_artifact_path,
        ),
        ArtifactRecord.create(
            run_id=record.run_id,
            artifact_type=ArtifactType.WORKFLOW_RUN_RECORD,
            artifact_path=record.run_record_artifact_path,
        ),
    ]
