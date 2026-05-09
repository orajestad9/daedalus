import json
from pathlib import Path

from daedalus.domains.readysetrentables_reviews.graph_state import (
    ReadySetRentablesReviewGraphState,
)
from daedalus.domains.readysetrentables_reviews.graph_workflow import (
    build_readysetrentables_review_graph,
    run_readysetrentables_review_graph,
)
from daedalus.model_clients.invocation_record import ModelInvocationStatus
from daedalus.model_clients.types import ModelProvider
from daedalus.orchestrator.status import WorkflowStatus


SAMPLE_CSV_PATH = Path("sample_data/readysetrentables_reviews/airbnb_reviews_sample.csv")
EXPECTED_SAMPLE_REVIEW_COUNT = 8
EXPECTED_STEP_NAMES = [
    "load_reviews",
    "write_normalized_artifact",
    "write_metadata_artifact",
    "write_summary_artifact",
    "write_run_record_artifact",
    "build_review_theme_summary_input",
    "run_fake_review_theme_summary_agent",
    "write_review_theme_summary_artifact",
]


def test_build_readysetrentables_review_graph_succeeds() -> None:
    graph = build_readysetrentables_review_graph()

    assert graph is not None


def test_run_readysetrentables_review_graph_writes_artifacts(
    tmp_path: Path,
) -> None:
    output_json_path = tmp_path / "normalized_reviews.json"

    final_state = run_readysetrentables_review_graph(
        input_csv_path=SAMPLE_CSV_PATH,
        output_json_path=output_json_path,
    )

    assert output_json_path.is_file()
    assert final_state.metadata_json_path == tmp_path / "normalized_reviews.metadata.json"
    assert final_state.summary_markdown_path == tmp_path / "normalized_reviews.summary.md"
    assert final_state.run_record_json_path == tmp_path / "normalized_reviews.run.json"
    assert final_state.review_theme_summary_markdown_path == (tmp_path / "review_theme_summary.md")
    assert final_state.metadata_json_path.is_file()
    assert final_state.summary_markdown_path.is_file()
    assert final_state.run_record_json_path.is_file()
    assert final_state.review_theme_summary_markdown_path.is_file()


def test_run_readysetrentables_review_graph_returns_typed_populated_state(
    tmp_path: Path,
) -> None:
    final_state = run_readysetrentables_review_graph(
        input_csv_path=SAMPLE_CSV_PATH,
        output_json_path=tmp_path / "normalized_reviews.json",
        approval_required=True,
        approved=True,
    )

    assert isinstance(final_state, ReadySetRentablesReviewGraphState)
    assert final_state.batch is not None
    assert final_state.batch.review_count == EXPECTED_SAMPLE_REVIEW_COUNT
    assert final_state.metadata_json_path is not None
    assert final_state.summary_markdown_path is not None
    assert final_state.run_record_json_path is not None
    assert final_state.review_theme_summary_input is not None
    assert final_state.review_theme_summary_result is not None
    assert final_state.review_theme_summary_markdown_path is not None
    assert len(final_state.model_invocations) == 1
    invocation = final_state.model_invocations[0]
    assert invocation.run_id == final_state.run_id
    assert invocation.provider == ModelProvider.FAKE
    assert invocation.status == ModelInvocationStatus.SUCCEEDED
    assert final_state.approval_required is True
    assert final_state.approved is True


def test_run_readysetrentables_review_graph_records_completed_steps(
    tmp_path: Path,
) -> None:
    final_state = run_readysetrentables_review_graph(
        input_csv_path=SAMPLE_CSV_PATH,
        output_json_path=tmp_path / "normalized_reviews.json",
    )

    assert [step.step_name for step in final_state.steps] == EXPECTED_STEP_NAMES
    assert {step.run_id for step in final_state.steps} == {final_state.run_id}
    assert all(step.status == WorkflowStatus.COMPLETED for step in final_state.steps)
    assert all(step.duration_ms is not None for step in final_state.steps)
    assert all(step.duration_ms is not None and step.duration_ms >= 0 for step in final_state.steps)


def test_run_readysetrentables_review_graph_artifact_review_count_matches_sample(
    tmp_path: Path,
) -> None:
    output_json_path = tmp_path / "normalized_reviews.json"

    run_readysetrentables_review_graph(
        input_csv_path=SAMPLE_CSV_PATH,
        output_json_path=output_json_path,
    )

    artifact = json.loads(output_json_path.read_text(encoding="utf-8"))
    assert len(artifact["reviews"]) == EXPECTED_SAMPLE_REVIEW_COUNT
