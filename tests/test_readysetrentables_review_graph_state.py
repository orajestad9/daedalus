from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID, uuid4

from daedalus.domains.readysetrentables_reviews.graph_state import (
    ReadySetRentablesReviewGraphState,
)
from daedalus.domains.readysetrentables_reviews.theme_summary_models import (
    ReviewThemeSummaryInput,
    ReviewThemeSummaryResult,
)
from daedalus.model_clients.invocation_record import (
    ModelInvocationRecord,
    ModelInvocationStatus,
)
from daedalus.model_clients.types import ModelProvider
from daedalus.orchestrator.step_record import WorkflowStepRecord


def test_graph_state_create_generates_run_id_and_preserves_paths() -> None:
    input_csv_path = Path("sample_data/readysetrentables_reviews/airbnb_reviews_sample.csv")
    output_json_path = Path("artifacts/readysetrentables/normalized_reviews.json")

    state = ReadySetRentablesReviewGraphState.create(
        input_csv_path=input_csv_path,
        output_json_path=output_json_path,
    )

    assert isinstance(state.run_id, UUID)
    assert state.started_at_utc.tzinfo is not None
    assert state.input_csv_path == input_csv_path
    assert state.output_json_path == output_json_path


def test_graph_state_create_starts_with_empty_workflow_data() -> None:
    state = ReadySetRentablesReviewGraphState.create(
        input_csv_path=Path("reviews.csv"),
        output_json_path=Path("normalized_reviews.json"),
    )

    assert state.batch is None
    assert state.metadata_json_path is None
    assert state.summary_markdown_path is None
    assert state.run_record_json_path is None
    assert state.review_theme_summary_input is None
    assert state.review_theme_summary_result is None
    assert state.review_theme_summary_markdown_path is None
    assert state.model_invocations == []
    assert state.steps == []
    assert state.approval_required is False
    assert state.approved is False


def test_graph_state_create_accepts_approval_flags() -> None:
    state = ReadySetRentablesReviewGraphState.create(
        input_csv_path=Path("reviews.csv"),
        output_json_path=Path("normalized_reviews.json"),
        approval_required=True,
        approved=True,
    )

    assert state.approval_required is True
    assert state.approved is True


def test_graph_state_steps_are_not_shared_between_instances() -> None:
    first_state = ReadySetRentablesReviewGraphState.create(
        input_csv_path=Path("first.csv"),
        output_json_path=Path("first.json"),
    )
    second_state = ReadySetRentablesReviewGraphState.create(
        input_csv_path=Path("second.csv"),
        output_json_path=Path("second.json"),
    )

    first_state.steps.append(WorkflowStepRecord.start(run_id=uuid4(), step_name="load_reviews"))

    assert len(first_state.steps) == 1
    assert second_state.steps == []


def test_graph_state_model_invocations_are_not_shared_between_instances() -> None:
    first_state = ReadySetRentablesReviewGraphState.create(
        input_csv_path=Path("first.csv"),
        output_json_path=Path("first.json"),
    )
    second_state = ReadySetRentablesReviewGraphState.create(
        input_csv_path=Path("second.csv"),
        output_json_path=Path("second.json"),
    )

    first_state.model_invocations.append(_model_invocation_record(run_id=first_state.run_id))

    assert len(first_state.model_invocations) == 1
    assert second_state.model_invocations == []


def test_graph_state_accepts_review_theme_summary_fields() -> None:
    state = ReadySetRentablesReviewGraphState.create(
        input_csv_path=Path("reviews.csv"),
        output_json_path=Path("normalized_reviews.json"),
    )
    summary_input = ReviewThemeSummaryInput(
        run_id=state.run_id,
        review_count=2,
        representative_reviews=["Great location.", "Clean apartment."],
        rating_distribution={"5": 2},
    )
    summary_result = ReviewThemeSummaryResult(
        run_id=state.run_id,
        summary_text="Guests mention location and cleanliness.",
        prompt_name=summary_input.prompt_name,
        prompt_version=summary_input.prompt_version,
        model_provider=ModelProvider.FAKE,
        model_name="fake-model",
    )
    summary_path = Path("artifacts/readysetrentables/review_theme_summary.md")

    updated_state = state.model_copy(
        update={
            "review_theme_summary_input": summary_input,
            "review_theme_summary_result": summary_result,
            "review_theme_summary_markdown_path": summary_path,
        }
    )

    assert updated_state.review_theme_summary_input == summary_input
    assert updated_state.review_theme_summary_result == summary_result
    assert updated_state.review_theme_summary_markdown_path == summary_path


def _model_invocation_record(run_id: UUID) -> ModelInvocationRecord:
    return ModelInvocationRecord(
        invocation_id=uuid4(),
        run_id=run_id,
        provider=ModelProvider.FAKE,
        model_name="fake-model",
        prompt_name="readysetrentables/review_theme_summary",
        prompt_version="v0",
        status=ModelInvocationStatus.SUCCEEDED,
        started_at_utc=datetime(2026, 5, 7, 10, 0, tzinfo=UTC),
        completed_at_utc=datetime(2026, 5, 7, 10, 0, 1, tzinfo=UTC),
        duration_ms=1_000,
    )
