from fractions import Fraction

from .belief import BeliefState


def collision_entropy_proxy(belief: BeliefState) -> Fraction:
    """Exact concentration proxy: 1-sum(p^2), avoiding float/log drift."""
    return Fraction(1) - sum((p * p for p in belief.probabilities), Fraction(0))


def uncertainty_reduction(before: BeliefState, after: BeliefState) -> Fraction:
    return collision_entropy_proxy(before) - collision_entropy_proxy(after)
