# Copyright (c) AIRBUS and its affiliates.
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Bidirectional converter between the two real POWL representations.

:class:`~gymact.powl._turtle.PowlModel` (a content fork of
``autofde_lab.fabric.powl``'s type -- see that module for the original
parser/serializer and ``_turtle.py`` in this directory for what was forked
and why) is a flat, IRI-addressed, node-id graph (``ChildBinding`` slots +
``ActivityLeaf`` + ``precedes`` edges). ``gymact.powl.algebra`` is a
*separate* real model, :data:`~gymact.powl.algebra.PowlNode`, consumed by
``gymact.powl.executor``'s traversal (``enabled()``/``fire()``/
``is_final()``): index-addressed children with an explicit transitive-
reduction order relation.

Confirmed this session (``ocel/powl_replay.py``'s own module docstring and
``.claude/rules/ecosystem-boundary.md``) that no converter between the two
existed. This module is that converter, scoped exactly to the shape
``fabric/powl.py`` actually produces: a **flat total order** of
``powl2:ActivityLeaf`` steps (what ``project_plan_to_powl`` emits and
``parse_powl_turtle`` accepts -- there is no ``powl2:ChoiceGraph`` or nested
``powl2:PartialOrder`` in that vocabulary at all, so this module does not
attempt to invent a mapping for constructs that do not exist on the Turtle
side). This module itself only ever sees the forked ``PowlModel`` shape
in ``_turtle.py``, never imports ``autofde_lab`` directly.

Two directions:

- :func:`powl_model_to_node` -- ``PowlModel`` (Turtle-parsed) ->
  :data:`~gymact.powl.algebra.PowlNode` (executor-consumable).
- :func:`powl_node_to_model` -- the reverse, producing a ``PowlModel`` that
  :func:`model_to_turtle` (added here -- no ``PowlModel`` -> Turtle
  serializer existed anywhere in this repo before this module) can render
  back into ``parse_powl_turtle``-acceptable text.

Scope refusals, named rather than silent
-----------------------------------------
- A ``PowlModel`` with zero ``ChildBinding`` children is refused
  (``EMPTY_MODEL``): the algebra has no "empty" node.
- A :data:`~gymact.powl.algebra.PowlNode` that is not a flat
  :class:`~gymact.powl.algebra.PartialOrder` of
  :class:`~gymact.powl.algebra.Atom` children (or a single bare
  ``Atom``) is refused (``UNSUPPORTED_NODE_SHAPE``): POWL2 Turtle as parsed
  by this repo's decoder has no vocabulary for ``ChoiceGraph``, ``Start``,
  ``End``, ``Silent``, or nested composites, so there is nothing honest to
  emit for one.
"""

from __future__ import annotations

from typing import Dict, List, Tuple

from rdflib import Graph, Literal, URIRef
from rdflib.namespace import Namespace, RDF

from gymact.powl._turtle import (
    MFWP,
    POWL2,
    PROV,
    XSD,
    ActivityLeaf,
    ChildBinding,
    ParameterBinding,
    PowlModel,
)
from gymact.powl.algebra import Atom, NodeId, OrderEdge, PartialOrder, PowlNode

__all__ = [
    "BridgeError",
    "parse_powl_turtle",
    "powl_model_to_node",
    "powl_node_to_model",
    "model_to_turtle",
]

_POWL2 = Namespace(POWL2)
_MFWP = Namespace(MFWP)
_PROV = Namespace(PROV)


class BridgeError(ValueError):
    """Raised when a model on either side is outside this bridge's named scope."""


# ---------------------------------------------------------------------------
# PowlModel (Turtle-parsed) -> PowlNode (executor-consumable)
# ---------------------------------------------------------------------------


def powl_model_to_node(model: PowlModel) -> PowlNode:
    """Convert a parsed-Turtle :class:`PowlModel` into a :class:`PowlNode` tree.

    ``model.ordered_children()`` gives the ``ChildBinding`` slots sorted by
    ``child_index`` (contiguous from 0 -- already enforced by
    :func:`autofde_lab.fabric.powl.validate_powl`, which
    :func:`~autofde_lab.fabric.powl.parse_powl_turtle` always runs before
    returning). Each slot's ``child_index`` becomes that atom's 0-based
    position in the resulting :class:`~gymact.powl.algebra.PartialOrder`
    -- the same arena convention ``algebra.py``'s own docstring describes.
    ``powl2:precedes`` edges between binding-slot IRIs become
    :class:`~gymact.powl.algebra.OrderEdge` between those positions.

    A single-step model reduces to a bare :class:`Atom` (not a one-child
    ``PartialOrder`` -- ``PartialOrder`` itself refuses ``n < 2``, per
    ``INVALID_PARTIAL_ORDER_ARITY``). :func:`powl_node_to_model` accepts a
    bare ``Atom`` back symmetrically, so the round trip is stable at n=1.
    """
    ordered = model.ordered_children()
    if not ordered:
        raise BridgeError("EMPTY_MODEL: powl2:Model has zero powl2:ChildBinding children")

    index_of_child_iri: Dict[str, int] = {
        child.iri: position for position, child in enumerate(ordered)
    }

    atoms: List[Atom] = []
    for child in ordered:
        leaf = model.leaves.get(child.child_model)
        if leaf is None:
            # Unreachable given parse_powl_turtle's own validate_powl call,
            # but this module never trusts a caller-constructed PowlModel to
            # have gone through that gate.
            raise BridgeError(
                f"DANGLING_CHILD_MODEL: <{child.iri}> powl2:childModel "
                f"<{child.child_model}> has no matching powl2:ActivityLeaf"
            )
        bindings: Dict[str, str] = {}
        for binding_iri in leaf.binds_parameter:
            binding = model.bindings.get(binding_iri)
            if binding is None:
                raise BridgeError(
                    f"DANGLING_BINDING: <{leaf.iri}> mfwp:bindsParameter "
                    f"<{binding_iri}> has no matching mfwp:ParameterBinding"
                )
            bindings[str(binding.binding_index)] = binding.bound_object
        atoms.append(
            Atom(label=leaf.activity_label, action=leaf.implements_action, bindings=bindings)
        )

    order_edges: set[OrderEdge] = set()
    for child in ordered:
        src = index_of_child_iri[child.iri]
        for target_iri in child.precedes:
            if target_iri not in index_of_child_iri:
                raise BridgeError(
                    f"DANGLING_PRECEDES: <{child.iri}> powl2:precedes "
                    f"<{target_iri}> is not one of this model's child bindings"
                )
            order_edges.add(OrderEdge(NodeId(src), NodeId(index_of_child_iri[target_iri])))

    if len(atoms) == 1:
        return atoms[0]

    return PartialOrder(tuple(atoms), frozenset(order_edges))


# ---------------------------------------------------------------------------
# PowlNode (executor-consumable) -> PowlModel (Turtle-parseable)
# ---------------------------------------------------------------------------


def powl_node_to_model(
    node: PowlNode,
    base_iri: str = "urn:autofde-lab:powl-bridge",
    planner_run: str = "run-turtle-bridge",
) -> PowlModel:
    """Convert an executor-consumable :class:`PowlNode` back into a ``PowlModel``.

    Accepts exactly the two shapes :func:`powl_model_to_node` can produce: a
    bare :class:`Atom` (n=1), or a :class:`PartialOrder` whose children are
    all :class:`Atom` (n>=2, per ``PartialOrder``'s own arity refusal).
    Anything else -- a :class:`~gymact.powl.algebra.ChoiceGraph`, a
    :class:`~gymact.powl.algebra.Start`/:class:`End`/
    :class:`~gymact.powl.algebra.Silent` leaf, or a nested composite --
    is refused by name (``UNSUPPORTED_NODE_SHAPE``): POWL2 Turtle as this
    repo's decoder accepts has no vocabulary for any of them.

    The order relation emitted is the model's transitive closure, so it
    round-trips through :func:`parse_powl_turtle`'s acyclicity check
    correctly even though it may be denser than the minimal reduction
    ``fabric/powl.py`` itself emits for a pure total order.
    """
    if isinstance(node, Atom):
        atoms: Tuple[Atom, ...] = (node,)
        precedes_by_index: Dict[int, Tuple[int, ...]] = {0: ()}
    elif isinstance(node, PartialOrder) and all(isinstance(c, Atom) for c in node.children):
        atoms = node.children  # type: ignore[assignment]
        by_src: Dict[int, List[int]] = {i: [] for i in range(len(atoms))}
        for edge in node.closure:
            by_src[int(edge.src)].append(int(edge.dst))
        precedes_by_index = {i: tuple(sorted(dsts)) for i, dsts in by_src.items()}
    else:
        raise BridgeError(
            f"UNSUPPORTED_NODE_SHAPE: {type(node).__name__} has no POWL2 Turtle "
            "vocabulary in this repo's decoder/emitter (fabric/powl.py models "
            "only a flat total order of powl2:ActivityLeaf steps)"
        )

    plan_iri = f"{base_iri}/plan"
    domain_iri = f"{base_iri}/domain"

    children: Dict[str, ChildBinding] = {}
    leaves: Dict[str, ActivityLeaf] = {}
    bindings: Dict[str, ParameterBinding] = {}
    has_child: List[str] = []

    for index, atom in enumerate(atoms):
        step_iri = f"{plan_iri}/step/{index}"
        slot_iri = f"{plan_iri}/binding-slot/{index}"
        implements_action = (
            atom.action if isinstance(atom.action, str) and atom.action else f"{base_iri}/{atom.label}"
        )

        binds_parameter: List[str] = []
        for position, key in enumerate(sorted(atom.bindings, key=_binding_sort_key)):
            binding_iri = f"{step_iri}/binding/{position}"
            bound_object = atom.bindings[key]
            bindings[binding_iri] = ParameterBinding(
                iri=binding_iri,
                binding_index=_binding_index(key, position),
                parameter=f"{base_iri}/{atom.label}-p{position}",
                bound_object=str(bound_object),
            )
            binds_parameter.append(binding_iri)

        leaves[step_iri] = ActivityLeaf(
            iri=step_iri,
            activity_label=atom.label,
            implements_action=implements_action,
            plan_ordinal=index,
            binds_parameter=tuple(binds_parameter),
        )

        precedes_iris = tuple(
            f"{plan_iri}/binding-slot/{target}" for target in precedes_by_index.get(index, ())
        )
        children[slot_iri] = ChildBinding(
            iri=slot_iri,
            child_index=index,
            child_model=step_iri,
            precedes=precedes_iris,
        )
        has_child.append(slot_iri)

    return PowlModel(
        iri=plan_iri,
        types=(POWL2 + "Model", POWL2 + "PartialOrder"),
        derived_from=(base_iri,),
        was_derived_from=(domain_iri,),
        has_child=tuple(has_child),
        projection="total-order",
        planner_run=planner_run,
        domain_digest=None,
        problem_digest=None,
        activity_count=len(atoms),
        children=children,
        leaves=leaves,
        bindings=bindings,
    )


def _binding_index(key: str, fallback_position: int) -> int:
    """Recover an int binding index from an ``Atom.bindings`` key.

    :func:`powl_model_to_node` always writes ``str(binding_index)`` keys, so
    this round-trips exactly for any model this bridge produced. A caller
    handing this function a hand-built ``Atom`` with non-numeric keys still
    gets a deterministic index (sorted position), rather than a crash.
    """
    try:
        return int(key)
    except ValueError:
        return fallback_position


def _binding_sort_key(key: str) -> Tuple[int, str]:
    try:
        return (0, f"{int(key):020d}")
    except ValueError:
        return (1, key)


# ---------------------------------------------------------------------------
# PowlModel -> Turtle. No such serializer existed anywhere in this repo
# before this module -- fabric/powl.py's writer goes plan_lines -> Turtle
# directly and never materializes a PowlModel on the way. This is the
# missing leg needed to close the round-trip loop for a test.
# ---------------------------------------------------------------------------


def parse_powl_turtle(text: str) -> PowlModel:
    """Real ``rdflib``-based parse of POWL2 Turtle into a :class:`PowlModel`.

    Accepts exactly the shape :func:`model_to_turtle` emits (and, by
    construction, the shape ``autofde_lab.fabric.powl.project_plan_to_powl``
    already produces -- same predicates: ``powl2:Model``/``PartialOrder``,
    ``powl2:hasChild``/``ChildBinding``/``childIndex``/``childModel``,
    ``powl2:Leaf``/``ActivityLeaf``/``activityLabel``, ``mfwp:implementsAction``,
    ``mfwp:bindsParameter``/``ParameterBinding``, ``powl2:precedes``).

    No parser for this direction existed anywhere in this repo before this
    function -- ``model_to_turtle`` above was the only serializer, and
    nothing round-tripped Turtle text back into a real :class:`PowlModel`.
    This closes that gap for real, using ``rdflib`` (already a gymact
    dependency) rather than hand-rolled string parsing.

    Refuses (``BridgeError``) rather than guesses on: no ``powl2:Model``
    subject, more than one, or any required field missing -- never silently
    defaults a digest/label/action to an empty string.
    """
    graph = Graph()
    try:
        graph.parse(data=text, format="turtle")
    except Exception as exc:  # noqa: BLE001 -- real rdflib parse errors, re-typed
        raise BridgeError(f"UNPARSEABLE_TURTLE: {exc}") from exc

    model_subjects = sorted(
        str(s) for s in graph.subjects(RDF.type, _POWL2.Model)
    )
    if not model_subjects:
        raise BridgeError("NO_POWL_MODEL: no subject typed powl2:Model in the document")
    if len(model_subjects) > 1:
        raise BridgeError(
            f"MULTIPLE_POWL_MODELS: {len(model_subjects)} subjects typed powl2:Model "
            f"({model_subjects}) -- this bridge accepts exactly one per document"
        )
    root = URIRef(model_subjects[0])

    def _one_literal(subject: URIRef, predicate: URIRef, *, required: bool, label: str) -> str | None:
        values = list(graph.objects(subject, predicate))
        if not values:
            if required:
                raise BridgeError(f"MISSING_REQUIRED_FIELD: <{subject}> has no {label}")
            return None
        if len(values) > 1:
            raise BridgeError(f"MULTI_VALUED_SCALAR: <{subject}> has more than one {label}")
        value = values[0]
        return str(value) if isinstance(value, Literal) else str(value)

    activity_count_literal = _one_literal(
        root, _MFWP.activityCount, required=False, label="mfwp:activityCount"
    )

    children: Dict[str, ChildBinding] = {}
    leaves: Dict[str, ActivityLeaf] = {}
    bindings: Dict[str, ParameterBinding] = {}

    for child_iri in sorted(str(c) for c in graph.objects(root, _POWL2.hasChild)):
        child_subject = URIRef(child_iri)
        types = {str(t) for t in graph.objects(child_subject, RDF.type)}
        if str(_POWL2.ChildBinding) not in types:
            raise BridgeError(
                f"UNTYPED_HAS_CHILD_TARGET: <{child_iri}> is powl2:hasChild of "
                f"<{root}> but is not typed powl2:ChildBinding"
            )
        child_index_literal = _one_literal(
            child_subject, _POWL2.childIndex, required=True, label="powl2:childIndex"
        )
        child_model = _one_literal(
            child_subject, _POWL2.childModel, required=True, label="powl2:childModel"
        )
        precedes = tuple(
            sorted(str(t) for t in graph.objects(child_subject, _POWL2.precedes))
        )
        children[child_iri] = ChildBinding(
            iri=child_iri,
            child_index=int(child_index_literal),  # type: ignore[arg-type]
            child_model=child_model,  # type: ignore[arg-type]
            precedes=precedes,
        )

        leaf_subject = URIRef(child_model)  # type: ignore[arg-type]
        leaf_types = {str(t) for t in graph.objects(leaf_subject, RDF.type)}
        if str(_POWL2.ActivityLeaf) not in leaf_types:
            raise BridgeError(
                f"DANGLING_CHILD_MODEL: <{child_iri}> powl2:childModel <{child_model}> "
                f"is not typed powl2:ActivityLeaf"
            )
        activity_label = _one_literal(
            leaf_subject, _POWL2.activityLabel, required=True, label="powl2:activityLabel"
        )
        implements_action = _one_literal(
            leaf_subject, _MFWP.implementsAction, required=True, label="mfwp:implementsAction"
        )
        plan_ordinal_literal = _one_literal(
            leaf_subject, _MFWP.planOrdinal, required=True, label="mfwp:planOrdinal"
        )
        binds_parameter = tuple(
            sorted(str(b) for b in graph.objects(leaf_subject, _MFWP.bindsParameter))
        )
        leaves[child_model] = ActivityLeaf(  # type: ignore[index]
            iri=str(leaf_subject),
            activity_label=activity_label,  # type: ignore[arg-type]
            implements_action=implements_action,  # type: ignore[arg-type]
            plan_ordinal=int(plan_ordinal_literal),  # type: ignore[arg-type]
            binds_parameter=binds_parameter,
        )

        for binding_iri in binds_parameter:
            if binding_iri in bindings:
                continue
            binding_subject = URIRef(binding_iri)
            binding_types = {str(t) for t in graph.objects(binding_subject, RDF.type)}
            if str(_MFWP.ParameterBinding) not in binding_types:
                raise BridgeError(
                    f"DANGLING_BINDING: <{leaf_subject}> mfwp:bindsParameter "
                    f"<{binding_iri}> is not typed mfwp:ParameterBinding"
                )
            binding_index_literal = _one_literal(
                binding_subject, _MFWP.bindingIndex, required=True, label="mfwp:bindingIndex"
            )
            parameter = _one_literal(
                binding_subject, _MFWP.parameter, required=True, label="mfwp:parameter"
            )
            bound_object = _one_literal(
                binding_subject, _MFWP.boundObject, required=True, label="mfwp:boundObject"
            )
            bindings[binding_iri] = ParameterBinding(
                iri=binding_iri,
                binding_index=int(binding_index_literal),  # type: ignore[arg-type]
                parameter=parameter,  # type: ignore[arg-type]
                bound_object=bound_object,  # type: ignore[arg-type]
            )

    return PowlModel(
        iri=str(root),
        types=tuple(sorted({str(t) for t in graph.objects(root, RDF.type)})),
        derived_from=tuple(sorted(str(d) for d in graph.objects(root, _POWL2.derivedFrom))),
        was_derived_from=tuple(sorted(str(d) for d in graph.objects(root, _PROV.wasDerivedFrom))),
        has_child=tuple(sorted(str(c) for c in graph.objects(root, _POWL2.hasChild))),
        projection=_one_literal(root, _MFWP.projection, required=False, label="mfwp:projection"),
        planner_run=_one_literal(root, _MFWP.plannerRun, required=False, label="mfwp:plannerRun"),
        domain_digest=_one_literal(
            root, _MFWP.domainDigest, required=False, label="mfwp:domainDigest"
        ),
        problem_digest=_one_literal(
            root, _MFWP.problemDigest, required=False, label="mfwp:problemDigest"
        ),
        activity_count=int(activity_count_literal) if activity_count_literal is not None else None,
        children=children,
        leaves=leaves,
        bindings=bindings,
    )


def model_to_turtle(model: PowlModel) -> str:
    """Render ``model`` as POWL2 Turtle, in exactly the subset
    :func:`~autofde_lab.fabric.powl.parse_powl_turtle` accepts.

    Structurally mirrors ``project_plan_to_powl``'s emission shape (same
    predicates, same literal datatypes) but is driven from a real
    :class:`PowlModel` object rather than from raw plan lines, so it can
    round-trip a model built by :func:`powl_node_to_model`.
    """
    out: List[str] = [
        f"@prefix powl2: <{POWL2}> .",
        f"@prefix mfwp: <{MFWP}> .",
        f"@prefix prov: <{PROV}> .",
        f"@prefix xsd: <{XSD}> .",
        "",
    ]

    root = [f"<{model.iri}> a powl2:Model, powl2:PartialOrder ;"]
    for iri in model.derived_from:
        root.append(f"    powl2:derivedFrom <{iri}> ;")
    for iri in model.was_derived_from:
        root.append(f"    prov:wasDerivedFrom <{iri}> ;")
    if model.domain_digest is not None:
        root.append(f'    mfwp:domainDigest "{model.domain_digest}" ;')
    if model.problem_digest is not None:
        root.append(f'    mfwp:problemDigest "{model.problem_digest}" ;')
    if model.planner_run is not None:
        root.append(f'    mfwp:plannerRun "{model.planner_run}" ;')
    if model.projection is not None:
        root.append(f'    mfwp:projection "{model.projection}" ;')
    for iri in model.has_child:
        root.append(f"    powl2:hasChild <{iri}> ;")
    activity_count = model.activity_count if model.activity_count is not None else len(model.children)
    root.append(f'    mfwp:activityCount "{activity_count}"^^xsd:integer .')
    out.extend(root)
    out.append("")

    for slot in model.ordered_children():
        out.extend(
            [
                f"<{slot.iri}> a powl2:ChildBinding ;",
                f'    powl2:childIndex "{slot.child_index}"^^xsd:integer ;',
                f"    powl2:childModel <{slot.child_model}> .",
                "",
            ]
        )
        leaf = model.leaves[slot.child_model]
        leaf_lines = [
            f"<{leaf.iri}> a powl2:Leaf, powl2:ActivityLeaf ;",
            f'    powl2:activityLabel "{leaf.activity_label}" ;',
            f"    mfwp:implementsAction <{leaf.implements_action}> ;",
        ]
        for binding_iri in leaf.binds_parameter:
            leaf_lines.append(f"    mfwp:bindsParameter <{binding_iri}> ;")
        leaf_lines.append(f'    mfwp:planOrdinal "{leaf.plan_ordinal}"^^xsd:integer .')
        out.extend(leaf_lines)
        out.append("")

        for binding_iri in leaf.binds_parameter:
            binding = model.bindings[binding_iri]
            out.extend(
                [
                    f"<{binding.iri}> a mfwp:ParameterBinding ;",
                    f'    mfwp:bindingIndex "{binding.binding_index}"^^xsd:integer ;',
                    f"    mfwp:parameter <{binding.parameter}> ;",
                    f"    mfwp:boundObject <{binding.bound_object}> .",
                    "",
                ]
            )

    for slot in model.ordered_children():
        for target in slot.precedes:
            out.append(f"<{slot.iri}> powl2:precedes <{target}> .")
    if any(slot.precedes for slot in model.ordered_children()):
        out.append("")

    return "\n".join(out)
