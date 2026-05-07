"""Workflow persistence coordination for completed Daedalus runs.

Repositories own SQL, while this service owns the small transaction-neutral
sequence of saving a run record and its artifact records. The connection helper
below is opt-in and used by CLI persistence only, keeping normal workflow runs
file-only unless the caller explicitly asks for Postgres persistence.
"""

from collections.abc import Sequence
from uuid import UUID

from pydantic import BaseModel

from daedalus.config import load_postgres_settings
from daedalus.domains.readysetrentables_reviews.workflow import (
    ReviewNormalizationWorkflowResult,
)
from daedalus.memory.artifact_repository import ArtifactRepository
from daedalus.memory.postgres import connect_postgres
from daedalus.memory.workflow_run_repository import WorkflowRunRepository
from daedalus.orchestrator.artifact_record import ArtifactRecord
from daedalus.orchestrator.artifact_type import ArtifactType
from daedalus.orchestrator.run_record import WorkflowRunRecord


class WorkflowPersistenceError(RuntimeError):
    """Raised when an explicit workflow persistence attempt fails."""


class WorkflowRunNotFoundError(LookupError):
    """Raised when a persisted workflow run cannot be found."""


class WorkflowRunDetails(BaseModel):
    """Read model for a persisted workflow run and its artifact records."""

    run_record: WorkflowRunRecord
    artifact_records: list[ArtifactRecord]


class WorkflowPersistenceService:
    """Persist completed workflow run and artifact records."""

    def __init__(
        self,
        workflow_run_repository: WorkflowRunRepository,
        artifact_repository: ArtifactRepository,
    ) -> None:
        self._workflow_run_repository = workflow_run_repository
        self._artifact_repository = artifact_repository

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


def persist_review_normalization_workflow_result(
    result: ReviewNormalizationWorkflowResult,
) -> int:
    """Persist a completed review normalization workflow result to Postgres.

    This is the opt-in boundary that loads local DB settings. It never builds or
    logs password-bearing DSNs, and it leaves the default workflow execution path
    free from any database requirement.
    """
    settings = load_postgres_settings()
    connection = connect_postgres(settings)

    try:
        service = WorkflowPersistenceService(
            workflow_run_repository=WorkflowRunRepository(connection),
            artifact_repository=ArtifactRepository(connection),
        )
        artifact_count = service.persist_completed_workflow(
            run_record=_run_record_from_result(result),
            artifact_records=_artifact_records_from_result(result),
        )
        connection.commit()
    except Exception as exc:
        connection.rollback()
        msg = "Failed to persist workflow run"
        raise WorkflowPersistenceError(msg) from exc
    finally:
        connection.close()

    return artifact_count


def load_workflow_run_details(run_id: UUID) -> WorkflowRunDetails:
    """Load a persisted workflow run and its artifacts from Postgres."""
    settings = load_postgres_settings()
    connection = connect_postgres(settings)

    try:
        workflow_run_repository = WorkflowRunRepository(connection)
        artifact_repository = ArtifactRepository(connection)
        run_record = workflow_run_repository.get_by_run_id(run_id)
        if run_record is None:
            msg = f"Workflow run not found: run_id={run_id}"
            raise WorkflowRunNotFoundError(msg)

        return WorkflowRunDetails(
            run_record=run_record,
            artifact_records=artifact_repository.list_for_run(run_id),
        )
    except WorkflowRunNotFoundError:
        raise
    except Exception as exc:
        msg = "Failed to load workflow run"
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
