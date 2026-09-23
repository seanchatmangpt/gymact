# Ported from autofde_lab.fabric.powl (namespace constants + the
# ParameterBinding/ActivityLeaf/ChildBinding/PowlModel dataclasses only) as
# part of the POWL v2 runner migration into gymact.
#
# This is a deliberate content fork, not a re-export -- same rationale as
# `_canonical.py` beside this file: gymact must not import autofde_lab (the
# dependency direction is the reverse -- autofde-lab depends on gymact as an
# editable sibling package), so `gymact.powl.turtle_bridge` needs its own
# copy of the flat, IRI-addressed Turtle-model shape `autofde_lab.fabric.powl`
# parses/emits. Field-for-field identical to the source; only
# `ordered_children()` is carried over as a method, nothing else from that
# module (no parser, no serializer, no digest helpers) is forked here --
# `turtle_bridge.py` never calls `parse_powl_turtle`/`model_to_turtle` on
# these types, only builds/reads `PowlModel` instances directly.
#
# Cross-reference: see `_canonical.py`'s header comment in this same
# directory for the sibling fork this one mirrors.

from __future__ import annotations

from dataclasses import dataclass, field

__all__ = [
    "MFWP",
    "POWL2",
    "PROV",
    "XSD",
    "ActivityLeaf",
    "ChildBinding",
    "ParameterBinding",
    "PowlModel",
]

POWL2 = "https://truex.io/ontology/powl2#"
MFWP = "urn:mfw:powl-trace:"
PROV = "http://www.w3.org/ns/prov#"
XSD = "http://www.w3.org/2001/XMLSchema#"


@dataclass(frozen=True)
class ParameterBinding:
    """One ``mfwp:ParameterBinding`` node."""

    iri: str
    binding_index: int
    parameter: str
    bound_object: str


@dataclass(frozen=True)
class ActivityLeaf:
    """One ``powl2:ActivityLeaf`` node."""

    iri: str
    activity_label: str
    implements_action: str
    plan_ordinal: int
    binds_parameter: tuple[str, ...] = ()


@dataclass(frozen=True)
class ChildBinding:
    """One ``powl2:ChildBinding`` slot."""

    iri: str
    child_index: int
    child_model: str
    precedes: tuple[str, ...] = ()


@dataclass(frozen=True)
class PowlModel:
    """The decoded ``powl2:Model`` root plus everything it reaches."""

    iri: str
    types: tuple[str, ...]
    derived_from: tuple[str, ...]
    was_derived_from: tuple[str, ...]
    has_child: tuple[str, ...]
    projection: str | None = None
    planner_run: str | None = None
    domain_digest: str | None = None
    problem_digest: str | None = None
    activity_count: int | None = None
    children: dict[str, ChildBinding] = field(default_factory=dict)
    leaves: dict[str, ActivityLeaf] = field(default_factory=dict)
    bindings: dict[str, ParameterBinding] = field(default_factory=dict)

    def ordered_children(self) -> list[ChildBinding]:
        return sorted(self.children.values(), key=lambda c: c.child_index)
