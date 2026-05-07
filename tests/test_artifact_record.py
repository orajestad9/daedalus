import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast
from uuid import UUID, uuid4

from daedalus.orchestrator.artifact_record import ArtifactRecord
from daedalus.orchestrator.artifact_type import ArtifactType


def test_creates_artifact_record_directly() -> None:
    artifact_id = uuid4()
    run_id = uuid4()
    created_at = datetime(2026, 5, 7, 10, 0, tzinfo=UTC)

    record = ArtifactRecord(
        artifact_id=artifact_id,
        run_id=run_id,
        artifact_type=ArtifactType.NORMALIZED_REVIEWS,
        artifact_path=Path("artifacts/readysetrentables/normalized_reviews.json"),
        created_at_utc=created_at,
    )

    assert record.artifact_id == artifact_id
    assert record.run_id == run_id
    assert record.artifact_type == ArtifactType.NORMALIZED_REVIEWS
    assert record.artifact_path == Path("artifacts/readysetrentables/normalized_reviews.json")
    assert record.created_at_utc == created_at


def test_artifact_record_create_generates_identity_and_timestamp() -> None:
    run_id = uuid4()

    record = ArtifactRecord.create(
        run_id=run_id,
        artifact_type=ArtifactType.WORKFLOW_SUMMARY,
        artifact_path=Path("artifacts/readysetrentables/normalized_reviews.summary.md"),
    )

    assert isinstance(record.artifact_id, UUID)
    assert record.run_id == run_id
    assert record.artifact_type == ArtifactType.WORKFLOW_SUMMARY
    assert record.artifact_path == Path("artifacts/readysetrentables/normalized_reviews.summary.md")
    assert record.created_at_utc.tzinfo is not None
    assert record.created_at_utc.utcoffset() is not None


def test_artifact_record_json_serializes_artifact_type_value() -> None:
    record = ArtifactRecord(
        artifact_id=uuid4(),
        run_id=uuid4(),
        artifact_type=ArtifactType.WORKFLOW_RUN_RECORD,
        artifact_path=Path("artifacts/readysetrentables/normalized_reviews.run.json"),
        created_at_utc=datetime(2026, 5, 7, 10, 0, tzinfo=UTC),
    )

    data = cast(dict[str, Any], json.loads(record.model_dump_json()))

    assert data["artifact_type"] == "workflow_run_record"
    assert data["artifact_path"] == "artifacts/readysetrentables/normalized_reviews.run.json"
