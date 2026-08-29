from gymact.explore_evidence_composition.pareto import Candidate
from gymact.explore_evidence_composition.selectors import (
    select_information,
    select_minimax_uncertainty,
    select_pareto,
    select_strongest,
)


def test_selector_families_remain_observably_distinct() -> None:
    candidates = (
        Candidate("strong", 0.7, 0.2, 5.0, 4),
        Candidate("precise", 0.75, 0.05, 7.0, 2),
        Candidate("cheap", 0.6, 0.3, 1.0, 1),
    )
    assert {item.name for item in select_strongest(candidates)} == {"strong"}
    assert {item.name for item in select_minimax_uncertainty(candidates)} == {"precise"}
    assert len(select_pareto(candidates)) >= 2
    assert select_information(candidates)
