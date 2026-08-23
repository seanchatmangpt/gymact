from fractions import Fraction

from gymact.explore_kantorovich_duality import DualPotential, normalize_gauge


def test_dual_gauge_normalization_preserves_relative_potentials() -> None:
    potential = DualPotential({"a": Fraction(3), "b": Fraction(5)}, {"x": Fraction(-2)})
    normalized = normalize_gauge(potential)
    assert normalized.u["a"] == 0
    assert normalized.u["b"] == 2
    assert normalized.v["x"] == 1
