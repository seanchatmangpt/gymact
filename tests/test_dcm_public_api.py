from __future__ import annotations

import gymact.dcm as dcm


def test_dcm_facade_exposes_first_principles_pipeline() -> None:
    required = {
        "PossibilityGraph",
        "ConsequenceBinding",
        "explore_combinatorial_maximum",
        "validate_possibility_rdf",
        "structural_scan",
        "EmpiricalPossibilityIndex",
        "DCMDecisionCourt",
        "select_irreversible_cut",
        "CombinatorialBRCEBroker",
        "compile_graph_recipe",
        "compose_paths",
    }
    assert required <= set(dcm.__all__)
    assert "ExecutionGrant" not in dcm.__all__
    assert "BrokerRequest" not in dcm.__all__
