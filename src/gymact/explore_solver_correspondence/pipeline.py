from __future__ import annotations

from fractions import Fraction

from .correspondence import compare
from .effective_evidence import require_effective_quorum
from .oracle_adapter import run_oracle
from .primal_adapter import run_primal
from .receipt import Receipt
from .standing import qualify


def verify_correspondence(
    subject,
    a,
    b,
    metric,
    *,
    correlation: Fraction = Fraction(0),
    minimum: Fraction = Fraction(2),
):
    primal = run_primal(subject, a, b, metric)
    oracle = run_oracle(subject, a, b, metric)
    evidence = compare(primal, oracle)
    n_eff = require_effective_quorum(2, correlation, minimum)
    standing = qualify(
        cost_gap=evidence.cost_gap,
        effective_evidence=n_eff,
        minimum=minimum,
        dependency_states=("ALIVE", "ALIVE"),
    )
    receipt = Receipt(
        subject.identity,
        primal.engine,
        oracle.engine,
        str(evidence.cost_gap),
        standing.state,
    )
    return evidence, standing, receipt
