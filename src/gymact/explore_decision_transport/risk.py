from fractions import Fraction

from .refusal import Refused


def transported_risk(losses: list[Fraction], weights: list[Fraction], *, self_normalized: bool = True) -> Fraction:
    if len(losses) != len(weights) or not losses:
        raise Refused("INVALID_TRANSPORT_SAMPLE")
    if any(loss < 0 for loss in losses) or any(weight < 0 for weight in weights):
        raise Refused("INVALID_TRANSPORT_SAMPLE")
    numerator = sum((loss * weight for loss, weight in zip(losses, weights, strict=True)), Fraction())
    if self_normalized:
        denominator = sum(weights, Fraction())
        if denominator <= 0:
            raise Refused("ZERO_TRANSPORT_WEIGHT")
        return numerator / denominator
    return numerator / len(losses)
