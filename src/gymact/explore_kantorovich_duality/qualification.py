from __future__ import annotations

from fractions import Fraction

from .certificate import DualityCertificate
from .independent_checker import independent_gap
from .potentials import DualPotentials
from .primal import PrimalPlan
from .receipt import Receipt
from .standing import Standing, combine


def qualify(subject: str, certificate: DualityCertificate, plan: PrimalPlan, potentials: DualPotentials, metric: dict[tuple[str, str], Fraction], supply: dict[str, Fraction], demand: dict[str, Fraction], dependencies: list[Standing]) -> Receipt | None:
    standing = combine(dependencies)
    if standing is Standing.BUILD_BROKEN:
        return None
    gap = independent_gap(plan, potentials, metric, supply, demand)
    if gap != 0:
        standing = Standing.UNSUPPORTED
    return Receipt(subject, str(certificate.optimum), standing)
