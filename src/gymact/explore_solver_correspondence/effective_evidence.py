from __future__ import annotations

from fractions import Fraction

from .refusal import Refused


def effective_sample_size(count: int, correlation: Fraction) -> Fraction:
    if count <= 0:
        raise Refused("EMPTY_EVIDENCE_SET")
    if correlation < 0 or correlation > 1:
        raise Refused("INVALID_CORRELATION")
    return Fraction(count, 1) / (1 + (count - 1) * correlation)


def require_effective_quorum(count: int, correlation: Fraction, minimum: Fraction) -> Fraction:
    n_eff = effective_sample_size(count, correlation)
    if n_eff < minimum:
        raise Refused("PSEUDO_QUORUM", f"{n_eff}<{minimum}")
    return n_eff
