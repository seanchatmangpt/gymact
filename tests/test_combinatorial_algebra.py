from __future__ import annotations

import pytest

from gymact.algebra import compose_paths, identity_path
from gymact.combinatorial import ObjectiveVector, PossibilityPath


def path(
    source: str,
    target: str,
    morphism: str,
    *,
    cost: float,
    confidence: int,
) -> PossibilityPath:
    return PossibilityPath(
        object_ids=(source, target),
        morphism_ids=(morphism,),
        objectives=ObjectiveVector(
            monetary_cost=cost,
            verification_confidence=confidence,
        ),
    )


def test_identity_path_is_left_and_right_neutral() -> None:
    value = path("a", "b", "f", cost=2.0, confidence=3)
    assert compose_paths(identity_path("a"), value) == value
    assert compose_paths(value, identity_path("b")) == value


def test_path_composition_is_associative() -> None:
    f = path("a", "b", "f", cost=1.0, confidence=4)
    g = path("b", "c", "g", cost=2.0, confidence=3)
    h = path("c", "d", "h", cost=3.0, confidence=2)
    left = compose_paths(compose_paths(f, g), h)
    right = compose_paths(f, compose_paths(g, h))
    assert left == right
    assert left.object_ids == ("a", "b", "c", "d")
    assert left.morphism_ids == ("f", "g", "h")
    assert left.objectives.monetary_cost == 6.0
    assert left.objectives.verification_confidence == 2


def test_non_adjacent_paths_do_not_compose_by_analogy() -> None:
    left = path("a", "b", "f", cost=1.0, confidence=4)
    right = path("c", "d", "g", cost=1.0, confidence=4)
    with pytest.raises(ValueError, match="PATH_COMPOSITION_ENDPOINT_MISMATCH"):
        compose_paths(left, right)
