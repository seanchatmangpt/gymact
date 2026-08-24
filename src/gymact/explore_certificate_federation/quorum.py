from fractions import Fraction

from .refusal import FederationRefusal


def effective_sample_size(n: int, rho: Fraction) -> Fraction:
    if n < 1 or rho < 0 or rho >= 1:
        raise FederationRefusal("INVALID_CORRELATION")
    return Fraction(n, 1) / (1 + (n - 1) * rho)


def require_effective_quorum(n: int, rho: Fraction, minimum: Fraction) -> Fraction:
    value = effective_sample_size(n, rho)
    if value < minimum:
        raise FederationRefusal("PSEUDO_QUORUM")
    return value
