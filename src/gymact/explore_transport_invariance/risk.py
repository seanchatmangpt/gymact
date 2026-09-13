from __future__ import annotations

from fractions import Fraction

from .refusal import require


def horvitz_thompson(losses: tuple[Fraction, ...], weights: tuple[Fraction, ...]) -> Fraction:
    require(
        len(losses) == len(weights) and bool(losses),
        "MISALIGNED_EVIDENCE",
        "losses and weights must align",
    )
    return sum(
        (loss * weight for loss, weight in zip(losses, weights, strict=True)), Fraction()
    ) / len(losses)


def self_normalized(losses: tuple[Fraction, ...], weights: tuple[Fraction, ...]) -> Fraction:
    require(
        len(losses) == len(weights) and bool(losses),
        "MISALIGNED_EVIDENCE",
        "losses and weights must align",
    )
    denominator = sum(weights, Fraction())
    require(denominator > 0, "ZERO_WEIGHT_MASS", "self-normalized risk needs positive weight mass")
    return (
        sum((loss * weight for loss, weight in zip(losses, weights, strict=True)), Fraction())
        / denominator
    )
