from dataclasses import dataclass

@dataclass(frozen=True)
class Currentness:
    ontology_version: int
    profile_version: int
    projection_version: int


def dominates(a: Currentness, b: Currentness) -> bool:
    av = (a.ontology_version, a.profile_version, a.projection_version)
    bv = (b.ontology_version, b.profile_version, b.projection_version)
    return all(x >= y for x, y in zip(av, bv)) and any(x > y for x, y in zip(av, bv))


def test_currentness_is_partial_order_not_scalar_recency() -> None:
    a = Currentness(3, 2, 1)
    b = Currentness(2, 2, 1)
    c = Currentness(2, 3, 1)
    assert dominates(a, b)
    assert not dominates(a, c)
    assert not dominates(c, a)
