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


def test_artifact_record_can_represent_review_theme_summary_artifact() -> None:
    run_id = uuid4()

    record = ArtifactRecord.create(
        run_id=run_id,
        artifact_type=ArtifactType.REVIEW_THEME_SUMMARY,
        artifact_path=Path("artifacts/readysetrentables/review_theme_summary.md"),
    )

    assert record.run_id == run_id
    assert record.artifact_type == ArtifactType.REVIEW_THEME_SUMMARY
    assert record.artifact_path == Path("artifacts/readysetrentables/review_theme_summary.md")


def test_artifact_record_can_represent_evaluation_report_artifact() -> None:
    run_id = uuid4()

    record = ArtifactRecord.create(
        run_id=run_id,
        artifact_type=ArtifactType.EVALUATION_REPORT,
        artifact_path=Path("artifacts/evaluations/review_theme_summary.evaluation.json"),
    )

    assert record.run_id == run_id
    assert record.artifact_type == ArtifactType.EVALUATION_REPORT
    assert record.artifact_path == Path(
        "artifacts/evaluations/review_theme_summary.evaluation.json"
    )


def test_artifact_record_can_represent_evaluation_comparison_report_artifact() -> None:
    run_id = uuid4()

    record = ArtifactRecord.create(
        run_id=run_id,
        artifact_type=ArtifactType.EVALUATION_COMPARISON_REPORT,
        artifact_path=Path("artifacts/evaluations/review_theme_summary.comparison.json"),
    )

    assert record.run_id == run_id
    assert record.artifact_type == ArtifactType.EVALUATION_COMPARISON_REPORT
    assert record.artifact_path == Path(
        "artifacts/evaluations/review_theme_summary.comparison.json"
    )


def test_artifact_type_includes_evaluation_comparison_report() -> None:
    assert ArtifactType("evaluation_comparison_report") == ArtifactType.EVALUATION_COMPARISON_REPORT
    assert ArtifactType.EVALUATION_COMPARISON_REPORT.value == "evaluation_comparison_report"


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


def test_review_theme_summary_artifact_json_serializes_artifact_type_value() -> None:
    record = ArtifactRecord(
        artifact_id=uuid4(),
        run_id=uuid4(),
        artifact_type=ArtifactType.REVIEW_THEME_SUMMARY,
        artifact_path=Path("artifacts/readysetrentables/review_theme_summary.md"),
        created_at_utc=datetime(2026, 5, 7, 10, 0, tzinfo=UTC),
    )

    data = cast(dict[str, Any], json.loads(record.model_dump_json()))

    assert data["artifact_type"] == "review_theme_summary"
    assert data["artifact_path"] == "artifacts/readysetrentables/review_theme_summary.md"


def test_evaluation_report_artifact_json_serializes_artifact_type_value() -> None:
    record = ArtifactRecord(
        artifact_id=uuid4(),
        run_id=uuid4(),
        artifact_type=ArtifactType.EVALUATION_REPORT,
        artifact_path=Path("artifacts/evaluations/review_theme_summary.evaluation.json"),
        created_at_utc=datetime(2026, 5, 7, 10, 0, tzinfo=UTC),
    )

    data = cast(dict[str, Any], json.loads(record.model_dump_json()))

    assert data["artifact_type"] == "evaluation_report"
    assert data["artifact_path"] == ("artifacts/evaluations/review_theme_summary.evaluation.json")


def test_evaluation_comparison_report_artifact_json_serializes_artifact_type_value() -> None:
    record = ArtifactRecord(
        artifact_id=uuid4(),
        run_id=uuid4(),
        artifact_type=ArtifactType.EVALUATION_COMPARISON_REPORT,
        artifact_path=Path("artifacts/evaluations/review_theme_summary.comparison.json"),
        created_at_utc=datetime(2026, 5, 7, 10, 0, tzinfo=UTC),
    )

    data = cast(dict[str, Any], json.loads(record.model_dump_json()))

    assert data["artifact_type"] == "evaluation_comparison_report"
    assert data["artifact_path"] == ("artifacts/evaluations/review_theme_summary.comparison.json")


def test_artifact_record_can_represent_review_insights_artifact() -> None:
    run_id = uuid4()

    record = ArtifactRecord.create(
        run_id=run_id,
        artifact_type=ArtifactType.REVIEW_INSIGHTS,
        artifact_path=Path("artifacts/readysetrentables/review_insights.json"),
    )

    assert record.run_id == run_id
    assert record.artifact_type == ArtifactType.REVIEW_INSIGHTS
    assert record.artifact_path == Path("artifacts/readysetrentables/review_insights.json")


def test_artifact_type_includes_review_insights() -> None:
    assert ArtifactType("review_insights") == ArtifactType.REVIEW_INSIGHTS
    assert ArtifactType.REVIEW_INSIGHTS.value == "review_insights"


def test_review_insights_artifact_json_serializes_artifact_type_value() -> None:
    record = ArtifactRecord(
        artifact_id=uuid4(),
        run_id=uuid4(),
        artifact_type=ArtifactType.REVIEW_INSIGHTS,
        artifact_path=Path("artifacts/readysetrentables/review_insights.json"),
        created_at_utc=datetime(2026, 5, 7, 10, 0, tzinfo=UTC),
    )

    data = cast(dict[str, Any], json.loads(record.model_dump_json()))

    assert data["artifact_type"] == "review_insights"
    assert data["artifact_path"] == "artifacts/readysetrentables/review_insights.json"


def test_artifact_record_can_represent_neighborhood_profile_markdown_artifact() -> None:
    run_id = uuid4()

    record = ArtifactRecord.create(
        run_id=run_id,
        artifact_type=ArtifactType.NEIGHBORHOOD_PROFILE_MARKDOWN,
        artifact_path=Path("artifacts/readysetrentables/neighborhood_profile.md"),
    )

    assert record.run_id == run_id
    assert record.artifact_type == ArtifactType.NEIGHBORHOOD_PROFILE_MARKDOWN
    assert record.artifact_path == Path("artifacts/readysetrentables/neighborhood_profile.md")


def test_artifact_type_includes_neighborhood_profile_markdown() -> None:
    assert (
        ArtifactType("neighborhood_profile_markdown") == ArtifactType.NEIGHBORHOOD_PROFILE_MARKDOWN
    )
    assert ArtifactType.NEIGHBORHOOD_PROFILE_MARKDOWN.value == "neighborhood_profile_markdown"


def test_neighborhood_profile_markdown_artifact_json_serializes_artifact_type_value() -> None:
    record = ArtifactRecord(
        artifact_id=uuid4(),
        run_id=uuid4(),
        artifact_type=ArtifactType.NEIGHBORHOOD_PROFILE_MARKDOWN,
        artifact_path=Path("artifacts/readysetrentables/neighborhood_profile.md"),
        created_at_utc=datetime(2026, 5, 7, 10, 0, tzinfo=UTC),
    )

    data = cast(dict[str, Any], json.loads(record.model_dump_json()))

    assert data["artifact_type"] == "neighborhood_profile_markdown"
    assert data["artifact_path"] == "artifacts/readysetrentables/neighborhood_profile.md"


def test_artifact_record_can_represent_neighborhood_profile_json_artifact() -> None:
    run_id = uuid4()

    record = ArtifactRecord.create(
        run_id=run_id,
        artifact_type=ArtifactType.NEIGHBORHOOD_PROFILE_JSON,
        artifact_path=Path("artifacts/readysetrentables/neighborhood_profile.json"),
    )

    assert record.run_id == run_id
    assert record.artifact_type == ArtifactType.NEIGHBORHOOD_PROFILE_JSON
    assert record.artifact_path == Path("artifacts/readysetrentables/neighborhood_profile.json")


def test_artifact_type_includes_neighborhood_profile_json() -> None:
    assert ArtifactType("neighborhood_profile_json") == ArtifactType.NEIGHBORHOOD_PROFILE_JSON
    assert ArtifactType.NEIGHBORHOOD_PROFILE_JSON.value == "neighborhood_profile_json"


def test_neighborhood_profile_json_artifact_json_serializes_artifact_type_value() -> None:
    record = ArtifactRecord(
        artifact_id=uuid4(),
        run_id=uuid4(),
        artifact_type=ArtifactType.NEIGHBORHOOD_PROFILE_JSON,
        artifact_path=Path("artifacts/readysetrentables/neighborhood_profile.json"),
        created_at_utc=datetime(2026, 5, 7, 10, 0, tzinfo=UTC),
    )

    data = cast(dict[str, Any], json.loads(record.model_dump_json()))

    assert data["artifact_type"] == "neighborhood_profile_json"
    assert data["artifact_path"] == "artifacts/readysetrentables/neighborhood_profile.json"
