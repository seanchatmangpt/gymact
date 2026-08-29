import pytest
from fractions import Fraction
from gymact.explore_dual_chain.engine_identity import EngineIdentity, require_independent
from gymact.explore_dual_chain.correlation import effective_evidence, require_quorum
from gymact.explore_dual_chain.refusal import DualChainRefusal

def test_independence_and_quorum():
    require_independent(EngineIdentity("solver", "m1", "BEAM"), EngineIdentity("checker", "m2", "WASM"))
    assert effective_evidence(3, Fraction(1, 2)) == Fraction(3, 2)
    with pytest.raises(DualChainRefusal, match="PSEUDO_QUORUM"):
        require_quorum(3, Fraction(1, 2), Fraction(2))
