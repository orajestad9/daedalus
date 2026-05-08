import json
from pathlib import Path
from typing import Any, cast

from daedalus.domains.readysetrentables_reviews.graph_workflow import (
    run_readysetrentables_review_graph,
)
from daedalus.domains.readysetrentables_reviews.workflow import (
    run_review_normalization_workflow,
)
from daedalus.orchestrator.status import WorkflowStatus


SAMPLE_CSV_PATH = Path("sample_data/readysetrentables_reviews/airbnb_reviews_sample.csv")
EXPECTED_STEP_NAMES = [
    "load_reviews",
    "write_normalized_artifact",
    "write_metadata_artifact",
    "write_summary_artifact",
    "write_run_record_artifact",
]


def test_langgraph_workflow_matches_deterministic_normalized_review_output(
    tmp_path: Path,
) -> None:
    deterministic_output_path = tmp_path / "deterministic" / "normalized_reviews.json"
    graph_output_path = tmp_path / "graph" / "normalized_reviews.json"

    deterministic_result = run_review_normalization_workflow(
        input_csv_path=SAMPLE_CSV_PATH,
        output_json_path=deterministic_output_path,
    )
    graph_state = run_readysetrentables_review_graph(
        input_csv_path=SAMPLE_CSV_PATH,
        output_json_path=graph_output_path,
    )

    assert deterministic_result.output_json_path.is_file()
    assert graph_output_path.is_file()

    deterministic_artifact = _load_json(deterministic_output_path)
    graph_artifact = _load_json(graph_output_path)

    assert len(graph_artifact["reviews"]) == len(deterministic_artifact["reviews"])
    assert _stable_reviews(graph_artifact) == _stable_reviews(deterministic_artifact)

    assert graph_state.metadata_json_path is not None
    assert graph_state.summary_markdown_path is not None
    assert graph_state.run_record_json_path is not None
    assert graph_state.metadata_json_path.is_file()
    assert graph_state.summary_markdown_path.is_file()
    assert graph_state.run_record_json_path.is_file()

    assert [step.step_name for step in graph_state.steps] == EXPECTED_STEP_NAMES
    assert all(step.status == WorkflowStatus.COMPLETED for step in graph_state.steps)


def _load_json(path: Path) -> dict[str, Any]:
    return cast(dict[str, Any], json.loads(path.read_text(encoding="utf-8")))


def _stable_reviews(artifact: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        {
            "review_id": review["review_id"],
            "property_id": review["property_id"],
            "source": review["source"],
            "reviewer_name": review["reviewer_name"],
            "review_text": review["review_text"],
            "review_date": review["review_date"],
            "rating": review["rating"],
            "language": review["language"],
            "country": review["country"],
        }
        for review in artifact["reviews"]
    ]
