from gymact.research_runtime.graph import RuntimeGraph

def test_graph_contract():
    assert RuntimeGraph(("a",), frozenset()).edges == ("a",)
