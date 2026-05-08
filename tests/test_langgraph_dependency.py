def test_langgraph_can_be_imported() -> None:
    import langgraph

    assert langgraph is not None


def test_state_graph_can_be_imported() -> None:
    from langgraph.graph import StateGraph

    assert StateGraph is not None
