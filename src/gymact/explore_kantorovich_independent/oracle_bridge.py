from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction

from .refusal import IndependentVerifierRefusal
from .witness import IndependentWitness


@dataclass(frozen=True)
class OracleAgreement:
    primary: Fraction
    exhaustive: Fraction
    dual: Fraction


def admit_oracle_agreement(primary: Fraction, exhaustive: Fraction, witness: IndependentWitness) -> OracleAgreement:
    if primary != exhaustive:
        raise IndependentVerifierRefusal("PRIMAL_ORACLE_DIVERGENCE", f"{primary}!={exhaustive}")
    if primary != witness.primal or primary != witness.dual:
        raise IndependentVerifierRefusal("PRIMAL_DUAL_ORACLE_DIVERGENCE", f"primary={primary},primal={witness.primal},dual={witness.dual}")
    return OracleAgreement(primary, exhaustive, witness.dual)
