import pytest

from gymact.explore_real_certificate_chain.methodology import MethodCoverage, REQUIRED
from gymact.explore_real_certificate_chain.pareto import frontier
from gymact.explore_real_certificate_chain.runtime import RuntimeProjection, correspond
from gymact.explore_real_certificate_chain.selector import Candidate


def test_cross_runtime_correspondence_requires_distinct_runtime_and_equal_result() -> None:
    beam = RuntimeProjection("BEAM", "sem", "result")
    wasm = RuntimeProjection("WASM", "sem", "result")
    assert correspond(beam, wasm)
    with pytest.raises(ValueError, match="NONINDEPENDENT_ENGINE"):
        correspond(beam, beam)


def test_methodology_closure_and_pareto_preserve_reversible_alternatives() -> None:
    assert MethodCoverage(REQUIRED).complete
    candidates = [
        Candidate("independent", 3, 1, 5),
        Candidate("diverse", 2, 3, 5),
        Candidate("dominated", 1, 1, 8),
    ]
    assert {c.name for c in frontier(candidates)} == {"independent", "diverse"}
