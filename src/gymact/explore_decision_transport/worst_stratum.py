from fractions import Fraction

from .refusal import Refused


def worst_stratum(
    risks: dict[tuple[str, str, str, str], Fraction],
) -> tuple[tuple[str, str, str, str], Fraction]:
    if not risks:
        raise Refused("EMPTY_STRATUM_SET")
    return max(sorted(risks.items()), key=lambda item: item[1])
