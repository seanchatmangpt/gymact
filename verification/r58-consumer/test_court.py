from pathlib import Path
from rdflib import Graph

ROOT = Path(__file__).resolve().parent


def ask(graph: Graph, name: str) -> bool:
    result = graph.query((ROOT / "queries" / name).read_text())
    return bool(getattr(result, "askAnswer", False))


def test_valid_adapter_satisfies_all_twenty_courts():
    graph = Graph().parse(ROOT / "adapter.ttl", format="turtle")
    queries = sorted((ROOT / "queries").glob("*.rq"))
    assert len(queries) == 20
    assert all(bool(getattr(graph.query(path.read_text()), "askAnswer", False)) for path in queries)


def test_wrong_target_is_refused_by_target_court():
    graph = Graph().parse(ROOT / "fixtures" / "wrong-target.ttl", format="turtle")
    assert not ask(graph, "03_target_token.rq")
