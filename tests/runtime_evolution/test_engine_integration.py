from gymact.runtime_evolution.engine import EvolutionEngine, EvolutionState


def test_failure_is_edge_local():
    e = EvolutionEngine()
    s = e.fail_edge(EvolutionState("S"), "a")
    after = e.advance(s, "b", "ok")
    assert after.subject == "S" and after.epoch == 1 and "a" in after.excluded
