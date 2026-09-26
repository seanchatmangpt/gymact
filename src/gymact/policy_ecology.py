"""Condition policy populations without turning behavioral variation into authority.

This module adds the policy-population layer described by arXiv:2609.29423 to
GymAct's existing reversible ecology substrate. It remains candidate-only:
strategic conditioning changes search/coordination behavior, never execution
permission, authority standing, or the BRCE DO gate.
"""

from __future__ import annotations

import re
import unicodedata
from enum import StrEnum
from functools import lru_cache
from math import dist, isfinite
from typing import Self

from pydantic import Field, field_validator, model_validator

from gymact.models import FrozenModel

TEMPERAMENT_ENGINEERING_PROVENANCE = ("https://arxiv.org/abs/2609.29423",)

# The authority boundary is structural: no code path in GymAct reads a
# condition value as authority, and no model here has an authority field. The
# axis-name fence below is defense-in-depth on top of that, and it is built to
# fail closed rather than to enumerate spellings:
#
# * axis ids must be ASCII after NFKC folding and removal of invisible format
#   characters (Unicode category Cf), so homoglyph spellings ("authority"
#   spelled with a Cyrillic small a, U+0430) are refused instead of being read
#   as unrelated words;
# * camelCase and acronym boundaries split into words before case folding, so
#   "ExecutionGrant" and "authorityLevel" read as "execution_grant" and
#   "authority_level";
# * a word is refused when it *starts with* an authority stem, so plurals and
#   derived forms (permissions, authorities, authorization, privileged) are
#   refused, and the separator-free form is scanned for the same stems, so
#   "executiongrant" and "permissionset" are refused too.
_FORBIDDEN_AUTHORITY_WORDS = frozenset({"do", "auth", "sudo"})
_FORBIDDEN_AUTHORITY_STEMS = (
    "authori",
    "authz",
    "permission",
    "permit",
    "privilege",
    "entitle",
    "grant",
    "capabilit",
    "execut",
)
_FORBIDDEN_AUTHORITY_SUBSTRINGS = (
    "authori",
    "permission",
    "privilege",
    "entitlement",
    "executiongrant",
    "executionauthority",
)
_AXIS_SEPARATORS = re.compile(r"[^0-9a-z]+")
_CAMEL_BOUNDARY = re.compile(r"(?<=[a-z0-9])(?=[A-Z])|(?<=[A-Z])(?=[A-Z][a-z])")


def _visible_nfkc(axis_id: str) -> str:
    folded = unicodedata.normalize("NFKC", axis_id)
    return "".join(char for char in folded if unicodedata.category(char) != "Cf")


@lru_cache(maxsize=4096)
def _normalized_axis_id(axis_id: str) -> str:
    """Canonical comparison key for an axis id.

    NFKC folds compatibility forms (full-width letters), invisible format
    characters (zero-width space/joiner, ...) are removed, camelCase boundaries
    become word boundaries, casefold removes case, and every run of
    non-alphanumeric characters collapses to one underscore. "selfModel",
    "Self-Model" and "self_model" therefore name the same axis.
    """
    split = _CAMEL_BOUNDARY.sub("_", _visible_nfkc(axis_id))
    return _AXIS_SEPARATORS.sub("_", split.casefold()).strip("_")


@lru_cache(maxsize=4096)
def _axis_is_non_ascii(axis_id: str) -> bool:
    return not _visible_nfkc(axis_id).isascii()


@lru_cache(maxsize=4096)
def _encodes_authority(axis_id: str) -> bool:
    if _axis_is_non_ascii(axis_id):
        # Fail closed: a non-ASCII letter that survives NFKC may be a homoglyph
        # of an authority word, and this fence cannot read it.
        return True
    normalized = _normalized_axis_id(axis_id)
    words = normalized.split("_")
    collapsed = normalized.replace("_", "")
    if collapsed in _FORBIDDEN_AUTHORITY_WORDS:
        return True
    if any(word in _FORBIDDEN_AUTHORITY_WORDS for word in words):
        return True
    if any(word.startswith(_FORBIDDEN_AUTHORITY_STEMS) for word in words):
        return True
    return any(fragment in collapsed for fragment in _FORBIDDEN_AUTHORITY_SUBSTRINGS)


def _require_finite(value: float, refusal: str) -> float:
    if not isfinite(value):
        raise ValueError(f"REFUSED:{refusal}")
    return value


def _admit_axis_id(axis_id: str) -> None:
    """Shared axis-id admission for every surface that names an axis."""
    if _axis_is_non_ascii(axis_id):
        raise ValueError(f"REFUSED:TEMPERAMENT_CANNOT_ENCODE_AUTHORITY:NON_ASCII_AXIS:{axis_id!r}")
    if not _normalized_axis_id(axis_id):
        raise ValueError("REFUSED:EMPTY_CONDITION_AXIS")
    if _encodes_authority(axis_id):
        raise ValueError(f"REFUSED:TEMPERAMENT_CANNOT_ENCODE_AUTHORITY:{axis_id}")


def _refuse_axis_pairs(
    pairs: tuple[tuple[str, float], ...],
    duplicate: str,
    non_finite: str = "NON_FINITE_CONDITION_VALUE",
) -> None:
    for key, _ in sorted(pairs):
        _admit_axis_id(key)
    normalized = [_normalized_axis_id(key) for key, _ in pairs]
    if len(normalized) != len(set(normalized)):
        raise ValueError(f"REFUSED:{duplicate}")
    for key, value in pairs:
        _require_finite(value, f"{non_finite}:{key}")


class PopulationKind(StrEnum):
    HOMOGENEOUS = "homogeneous"
    INCIDENTAL = "incidental"
    ENGINEERED = "engineered"
    ADAPTIVE = "adaptive"


class ConditionAxis(FrozenModel):
    axis_id: str = Field(min_length=1)
    lower: float = 0.0
    upper: float = 1.0
    provenance_refs: tuple[str, ...] = ()

    @model_validator(mode="after")
    def valid_axis(self) -> Self:
        _admit_axis_id(self.axis_id)
        _require_finite(self.lower, "NON_FINITE_CONDITION_AXIS_BOUND")
        _require_finite(self.upper, "NON_FINITE_CONDITION_AXIS_BOUND")
        if self.lower >= self.upper:
            raise ValueError("REFUSED:CONDITION_AXIS_REQUIRES_NONEMPTY_RANGE")
        return self


class StrategicCondition(FrozenModel):
    """A point on a behavioral conditioning manifold.

    Values intentionally contain no authority field, and no code path reads a
    condition value as authority. As defense-in-depth the validator also
    refuses axis names that spell authority, permission, privilege, grants,
    execution or DO in any case, separator, camelCase, plural or derived form,
    and refuses non-ASCII axis ids (homoglyphs) outright.
    """

    values: tuple[tuple[str, float], ...] = ()

    @field_validator("values")
    @classmethod
    def canonical_order(
        cls, values: tuple[tuple[str, float], ...]
    ) -> tuple[tuple[str, float], ...]:
        # Canonical identity: the same condition written in any order is equal.
        return tuple(sorted(values))

    @model_validator(mode="after")
    def unique_non_authority_axes(self) -> Self:
        _refuse_axis_pairs(self.values, "DUPLICATE_CONDITION_AXIS")
        return self

    def as_dict(self) -> dict[str, float]:
        return dict(self.values)


class ReactionNorm(FrozenModel):
    """Linear cue response around a reference cue.

    condition(c) = baseline + slope * (c - reference_cue), clamped to each
    declared axis range.
    """

    slopes: tuple[tuple[str, float], ...] = ()
    reference_cue: float = 0.0

    @field_validator("slopes")
    @classmethod
    def canonical_order(
        cls, slopes: tuple[tuple[str, float], ...]
    ) -> tuple[tuple[str, float], ...]:
        return tuple(sorted(slopes))

    @model_validator(mode="after")
    def unique_non_authority_axes(self) -> Self:
        _refuse_axis_pairs(self.slopes, "DUPLICATE_REACTION_NORM_AXIS")
        _require_finite(self.reference_cue, "NON_FINITE_REFERENCE_CUE")
        return self

    def apply(
        self,
        baseline: StrategicCondition,
        cue: float,
        axes: tuple[ConditionAxis, ...],
    ) -> StrategicCondition:
        _require_finite(cue, "NON_FINITE_CUE")
        # Every lookup is keyed by the normalized axis id, the same identity
        # every admission path uses, so a case- or separator-variant spelling
        # cannot skip the range check or register a second range.
        ranges: dict[str, ConditionAxis] = {}
        for axis in axes:
            key = _normalized_axis_id(axis.axis_id)
            if key in ranges:
                raise ValueError(f"REFUSED:DUPLICATE_CONDITION_AXIS:{axis.axis_id}")
            ranges[key] = axis
        values = baseline.as_dict()
        spelled = {_normalized_axis_id(axis_id): axis_id for axis_id in values}
        for axis_id, value in values.items():
            axis = ranges.get(_normalized_axis_id(axis_id))
            if axis is not None and not axis.lower <= value <= axis.upper:
                raise ValueError(f"REFUSED:CONDITION_OUTSIDE_AXIS_RANGE:{axis_id}")
        delta = cue - self.reference_cue
        for axis_id, slope in self.slopes:
            key = _normalized_axis_id(axis_id)
            axis = ranges.get(key)
            if axis is None:
                raise ValueError(f"REFUSED:UNKNOWN_CONDITION_AXIS:{axis_id}")
            target = spelled.get(key, axis_id)
            value = values.get(target, axis.lower) + slope * delta
            if not isfinite(value):
                raise ValueError(f"REFUSED:NON_FINITE_CONDITION_VALUE:{axis_id}")
            values[target] = min(axis.upper, max(axis.lower, value))
            spelled[key] = target
        return StrategicCondition(values=tuple(sorted(values.items())))


class PolicyPhenotype(FrozenModel):
    """One conditioned realization of an existing policy."""

    policy_ref: str = Field(min_length=1)
    condition: StrategicCondition = Field(default_factory=StrategicCondition)
    evidence_refs: tuple[str, ...] = ()


class WeightedPhenotype(FrozenModel):
    phenotype: PolicyPhenotype
    weight: float = Field(gt=0.0, allow_inf_nan=False)


class PolicyPopulation(FrozenModel):
    kind: PopulationKind
    members: tuple[WeightedPhenotype, ...] = Field(min_length=1)
    reaction_norm: ReactionNorm | None = None

    @model_validator(mode="after")
    def population_contract(self) -> Self:
        if self.kind is PopulationKind.HOMOGENEOUS and len(self.members) != 1:
            raise ValueError("REFUSED:HOMOGENEOUS_POPULATION_REQUIRES_ONE_PHENOTYPE")
        if self.kind is PopulationKind.ADAPTIVE and self.reaction_norm is None:
            raise ValueError("REFUSED:ADAPTIVE_POPULATION_REQUIRES_REACTION_NORM")
        self.normalized_weights()
        return self

    def normalized_weights(self) -> tuple[float, ...]:
        total = sum(member.weight for member in self.members)
        if not isfinite(total) or total <= 0.0:
            raise ValueError("REFUSED:POPULATION_WEIGHT_NOT_NORMALIZABLE")
        return tuple(member.weight / total for member in self.members)


class PopulationDiversity(FrozenModel):
    disparity: float = Field(ge=0.0)
    complexity: float = Field(ge=1.0)


DEFAULT_TEMPERAMENT_AXES: tuple[ConditionAxis, ...] = tuple(
    ConditionAxis(
        axis_id=axis_id,
        provenance_refs=TEMPERAMENT_ENGINEERING_PROVENANCE,
    )
    for axis_id in (
        "boldness",
        "exploration",
        "activity",
        "aggressiveness",
        "sociability",
        "self_model_plasticity",
        "forcefulness",
        "initiative",
        "expressiveness",
    )
)


def condition_population(
    population: PolicyPopulation,
    *,
    cue: float,
    axes: tuple[ConditionAxis, ...] = DEFAULT_TEMPERAMENT_AXES,
) -> PolicyPopulation:
    """Apply an adaptive reaction norm without changing policy identity or weight."""
    if population.kind is not PopulationKind.ADAPTIVE:
        return population
    if population.reaction_norm is None:  # unreachable: population_contract refuses it
        raise ValueError("REFUSED:ADAPTIVE_POPULATION_REQUIRES_REACTION_NORM")
    return PolicyPopulation(
        kind=population.kind,
        reaction_norm=population.reaction_norm,
        members=tuple(
            WeightedPhenotype(
                phenotype=PolicyPhenotype(
                    policy_ref=member.phenotype.policy_ref,
                    condition=population.reaction_norm.apply(
                        member.phenotype.condition,
                        cue,
                        axes,
                    ),
                    evidence_refs=member.phenotype.evidence_refs,
                ),
                weight=member.weight,
            )
            for member in population.members
        ),
    )


def population_diversity(population: PolicyPopulation) -> PopulationDiversity:
    """Return weighted geometric disparity and effective population complexity.

    Disparity is the weighted mean pairwise Euclidean distance over the union
    of condition axes. Complexity is the inverse Simpson effective member
    count. They are intentionally separate: two populations can have the same
    member count but radically different behavioral separation.
    """
    weights = population.normalized_weights()
    conditions = [member.phenotype.condition.as_dict() for member in population.members]
    # One canonical (sorted) axis order for every member: an axis absent from a
    # member reads as 0.0, identical to the per-pair union, but the vectors are
    # built once (O(n*k)) instead of per pair, and the summation order no
    # longer depends on set iteration order. math.dist is scaled internally,
    # so large-but-finite coordinates do not overflow through squaring.
    axis_order = sorted({key for condition in conditions for key in condition})
    vectors = [tuple(condition.get(key, 0.0) for key in axis_order) for condition in conditions]

    disparity = 0.0
    pair_weight = 0.0
    for left in range(len(vectors)):
        left_vector = vectors[left]
        left_weight = weights[left]
        for right in range(left + 1, len(vectors)):
            weight = left_weight * weights[right]
            disparity += weight * dist(left_vector, vectors[right])
            pair_weight += weight

    if pair_weight:
        disparity /= pair_weight

    complexity = 1.0 / sum(weight * weight for weight in weights)
    if not (isfinite(disparity) and isfinite(complexity)):
        raise ValueError("REFUSED:POPULATION_DIVERSITY_NOT_FINITE")
    return PopulationDiversity(disparity=disparity, complexity=complexity)
