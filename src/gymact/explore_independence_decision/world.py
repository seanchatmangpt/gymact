from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction

from .dependence import DependenceEvidence


@dataclass(frozen=True)
class FailureWorld:
    name: str
    dependence: DependenceEvidence
    drift_samples: tuple[Fraction, ...]
    dependency_broken: bool = False


def shared_root_world() -> FailureWorld:
    return FailureWorld(
        name="shared-root",
        dependence=DependenceEvidence(Fraction(1, 2), Fraction(0), Fraction(0), 20),
        drift_samples=(Fraction(0),) * 4,
    )


def empirical_drift_world() -> FailureWorld:
    return FailureWorld(
        name="empirical-drift",
        dependence=DependenceEvidence(Fraction(0), Fraction(0), Fraction(0), 20),
        drift_samples=(Fraction(0), Fraction(1, 2), Fraction(3, 4), Fraction(1)),
    )


def broken_dependency_world() -> FailureWorld:
    return FailureWorld(
        name="broken-dependency",
        dependence=DependenceEvidence(Fraction(0), Fraction(0), Fraction(0), 20),
        drift_samples=(Fraction(0),),
        dependency_broken=True,
    )
