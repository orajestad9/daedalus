"""Generic workflow artifact records for persistence.

Artifact records describe files produced by a workflow run without knowing the
domain-specific content inside those files. This mirrors the Phase 1
`workflow_artifacts` table and gives future repositories a stable model to save
normalized data, metadata, summaries, validation reports, and agent outputs.
"""

from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID, uuid4

from pydantic import BaseModel

from daedalus.orchestrator.artifact_type import ArtifactType


class ArtifactRecord(BaseModel):
    """Machine-readable record of one workflow artifact."""

    artifact_id: UUID
    run_id: UUID
    artifact_type: ArtifactType
    artifact_path: Path
    created_at_utc: datetime

    @classmethod
    def create(
        cls,
        *,
        run_id: UUID,
        artifact_type: ArtifactType,
        artifact_path: Path,
    ) -> "ArtifactRecord":
        """Create an artifact record with generated identity and UTC timestamp."""
        return cls(
            artifact_id=uuid4(),
            run_id=run_id,
            artifact_type=artifact_type,
            artifact_path=artifact_path,
            created_at_utc=datetime.now(UTC),
        )
