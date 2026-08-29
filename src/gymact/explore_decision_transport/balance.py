from fractions import Fraction


def max_balance_error(weighted: dict[str, Fraction], target: dict[str, Fraction]) -> Fraction:
    keys = set(weighted) | set(target)
    return max((abs(weighted.get(k, Fraction()) - target.get(k, Fraction())) for k in keys), default=Fraction())
