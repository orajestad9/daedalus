"""Compiled LangGraph workflow for ReadySetRentables review normalization."""

from pathlib import Path

from langgraph.graph import END, StateGraph
from langgraph.graph.state import CompiledStateGraph

from daedalus.domains.readysetrentables_reviews.graph_nodes import (
    load_reviews_node,
    write_metadata_artifact_node,
    write_normalized_artifact_node,
    write_run_record_artifact_node,
    write_summary_artifact_node,
)
from daedalus.domains.readysetrentables_reviews.graph_state import (
    ReadySetRentablesReviewGraphState,
)


ReadySetRentablesReviewCompiledGraph = CompiledStateGraph[
    ReadySetRentablesReviewGraphState,
    None,
    ReadySetRentablesReviewGraphState,
    ReadySetRentablesReviewGraphState,
]


def build_readysetrentables_review_graph() -> ReadySetRentablesReviewCompiledGraph:
    """Build and compile the deterministic ReadySetRentables LangGraph workflow."""
    graph: StateGraph[
        ReadySetRentablesReviewGraphState,
        None,
        ReadySetRentablesReviewGraphState,
        ReadySetRentablesReviewGraphState,
    ] = StateGraph(ReadySetRentablesReviewGraphState)
    graph.add_node("load_reviews", load_reviews_node)
    graph.add_node("write_normalized_artifact", write_normalized_artifact_node)
    graph.add_node("write_metadata_artifact", write_metadata_artifact_node)
    graph.add_node("write_summary_artifact", write_summary_artifact_node)
    graph.add_node("write_run_record_artifact", write_run_record_artifact_node)

    graph.set_entry_point("load_reviews")
    graph.add_edge("load_reviews", "write_normalized_artifact")
    graph.add_edge("write_normalized_artifact", "write_metadata_artifact")
    graph.add_edge("write_metadata_artifact", "write_summary_artifact")
    graph.add_edge("write_summary_artifact", "write_run_record_artifact")
    graph.add_edge("write_run_record_artifact", END)

    return graph.compile()


def run_readysetrentables_review_graph(
    *,
    input_csv_path: Path,
    output_json_path: Path,
    approval_required: bool = False,
    approved: bool = False,
) -> ReadySetRentablesReviewGraphState:
    """Run the compiled graph and return typed final graph state."""
    initial_state = ReadySetRentablesReviewGraphState.create(
        input_csv_path=input_csv_path,
        output_json_path=output_json_path,
        approval_required=approval_required,
        approved=approved,
    )
    raw_state: object = build_readysetrentables_review_graph().invoke(initial_state)
    if isinstance(raw_state, ReadySetRentablesReviewGraphState):
        return raw_state

    return ReadySetRentablesReviewGraphState.model_validate(raw_state)
