from fractions import Fraction


def simpson_reversal(source: dict[str, Fraction], target: dict[str, Fraction]) -> bool:
    common = sorted(set(source) & set(target))
    if len(common) < 2:
        return False
    source_order = sorted(common, key=lambda k: source[k])
    target_order = sorted(common, key=lambda k: target[k])
    return source_order == list(reversed(target_order))
