from fractions import Fraction
from .refusal import DualChainRefusal

def effective_evidence(n: int, rho: Fraction) -> Fraction:
    if n < 1 or rho < 0 or rho > 1:
        raise DualChainRefusal("INVALID_CORRELATION")
    return Fraction(n, 1) / (1 + (n - 1) * rho)

def require_quorum(n: int, rho: Fraction, minimum: Fraction) -> Fraction:
    value = effective_evidence(n, rho)
    if value < minimum:
        raise DualChainRefusal("PSEUDO_QUORUM")
    return value
