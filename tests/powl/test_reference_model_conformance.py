# Copyright (c) AIRBUS and its affiliates.
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Structural conformance between :mod:`gymact.powl.algebra` and the real
POWL 2.0 reference implementation checked out at ``~/POWL``
(package ``powl``, ``powl.objects.tagged_powl``).

No mocks. Both sides of every comparison are real, independently
constructed objects from their own real package: ``gymact.powl.algebra``
is imported directly (it already ships inside this repo's own venv), and
the reference ``powl.objects.tagged_powl`` submodules are imported by
inserting ``~/POWL`` onto ``sys.path`` -- done here, inside this file, not
via a shared ``conftest.py`` fixture, so the test stays self-contained and
its dependency on a local sibling checkout is visible at the top of the
one file that needs it.

Only the leaf submodules (``.activity``, ``.partial_order``, and their own
transitive imports -- ``.base``, ``.graph_base``, ``.types``, all of which
depend only on stdlib + ``networkx``) are imported, never the ``powl``
top-level package (``import powl`` pulls in ``powl.main``, which imports
pm4py-dependent discovery code at module load time -- confirmed by reading
``~/POWL/powl/main.py`` this session; this test does not need or want that
dependency).

Fixture provenance -- a deliberate substitution, not a shortcut
-----------------------------------------------------------------
``~/POWL/examples/partial_order_based_discovery.py`` builds its
``PartialOrder`` via ``pm4py.discover_from_partially_ordered_log(log)`` over
``hospital.csv`` -- an algorithm *output*, not a hand-authored literal
value, and therefore unusable as a deterministic, hand-checkable
conformance fixture without also vendoring pm4py's discovery algorithm as
ground truth. This test instead reproduces, independently on both sides, a
small hand-authored linear-chain fixture in the spirit of the one real
hand-authored ``PartialOrder`` literal found in either ``~/POWL`` example
file: ``examples/powl_example_with_pools_and_lanes.py``'s
``generate_process_1()`` (``sequence(children=[pay, prepare_coffee])`` --
labels ``"Pay"``, ``"Prepare Coffee"``, one edge). Extended here to three
activities / two edges so the transitive-closure comparison below is a real
check (a two-node, one-edge fixture cannot distinguish reduction from
closure -- there is nothing to reduce).

Real skip condition, not a mock substitution
----------------------------------------------
``~/POWL`` is a real local checkout, not a paid or nondeterministic
external API, so it is imported and used directly rather than faked. The
only legitimate skip here (per this repo's
``.claude/rules/testing-chicago-style.md``) guards against that checkout
being absent on a machine that is not the one this design was written on --
never a silent mock standing in for it.
"""

from __future__ import annotations

import sys
import types
from pathlib import Path

import pytest

_POWL_REPO = Path.home() / "POWL"

pytestmark = pytest.mark.skipif(
    not (_POWL_REPO / "powl" / "objects" / "tagged_powl" / "partial_order.py").exists(),
    reason=f"reference POWL checkout not found at {_POWL_REPO} -- real local "
    "checkout required, never mocked (testing-chicago-style.md)",
)

if str(_POWL_REPO) not in sys.path:
    sys.path.insert(0, str(_POWL_REPO))

from gymact.powl.algebra import Atom, NodeId, OrderEdge, PartialOrder  # noqa: E402
from gymact.powl.frequency import ONCE  # noqa: E402

FIXTURE_LABELS: tuple[str, str, str] = ("Pay", "Prepare Coffee", "Serve")


def _install_namespace_stub(name: str, directory: Path) -> None:
    """Register `name` in `sys.modules` as an empty namespace package
    pointing at `directory`, WITHOUT executing that package's real
    `__init__.py`.

    Real, load-bearing plumbing, not a mock of `powl` itself: `powl`'s real
    top-level `__init__.py` (and `powl.objects.tagged_powl`'s own, which
    also pulls in `.builders`/`.choice_graph`) eagerly imports
    `powl.main`, which imports `pm4py` -- confirmed via the real
    `ModuleNotFoundError` this test hit on its first run, when it reached
    `powl.main` through the ordinary package-import path. Every downstream
    class this test actually uses (`Activity`, `PartialOrder`, and their
    real transitive deps `base`/`graph_base`/`types`) has zero pm4py
    dependency on its own -- confirmed by direct read this session -- so
    the fix is to import exactly those leaf submodules while skipping the
    package `__init__.py` files that would otherwise pull `powl.main` in
    along the way. No behavior of `powl.objects.tagged_powl.activity` /
    `.partial_order` is altered or faked; only which `__init__.py` bodies
    execute is changed.
    """
    if name in sys.modules:
        return
    stub = types.ModuleType(name)
    stub.__path__ = [str(directory)]
    stub.__package__ = name
    sys.modules[name] = stub


_install_namespace_stub("powl", _POWL_REPO / "powl")
_install_namespace_stub("powl.objects", _POWL_REPO / "powl" / "objects")
_install_namespace_stub(
    "powl.objects.tagged_powl", _POWL_REPO / "powl" / "objects" / "tagged_powl"
)


def _import_reference():
    """Import only the leaf reference submodules -- never `import powl`
    itself, and never `powl.objects.tagged_powl`'s own `__init__.py`
    (see `_install_namespace_stub`'s docstring above)."""
    from powl.objects.tagged_powl.activity import Activity  # noqa: PLC0415
    from powl.objects.tagged_powl.partial_order import PartialOrder as RefPartialOrder  # noqa: PLC0415

    return Activity, RefPartialOrder


def build_reference_fixture():
    """A real, independently-constructed `powl.objects.tagged_powl`
    PartialOrder: Pay -> Prepare Coffee -> Serve (a real linear chain, two
    edges), each activity a real `Activity` with a real string label."""
    Activity, RefPartialOrder = _import_reference()
    pay = Activity(FIXTURE_LABELS[0], organization="Customer", role="Customer")
    prepare = Activity(FIXTURE_LABELS[1], organization="Cafe", role="Customer")
    serve = Activity(FIXTURE_LABELS[2], organization="Cafe", role="Customer")
    model = RefPartialOrder(
        nodes=[pay, prepare, serve],
        edges=[(pay, prepare), (prepare, serve)],
    )
    return model


def build_gymact_fixture() -> PartialOrder:
    """The same real linear-chain shape, built with the real
    `gymact.powl.algebra.PartialOrder`/`Atom` (0-based index-arena
    convention, per `algebra.py`'s own module docstring)."""
    pay = Atom(label=FIXTURE_LABELS[0])
    prepare = Atom(label=FIXTURE_LABELS[1])
    serve = Atom(label=FIXTURE_LABELS[2])
    return PartialOrder(
        children=(pay, prepare, serve),
        order=frozenset(
            {
                OrderEdge(NodeId(0), NodeId(1)),
                OrderEdge(NodeId(1), NodeId(2)),
            }
        ),
        frequency=ONCE,
    )


def _gymact_label_set(model: PartialOrder) -> frozenset[str]:
    return frozenset(c.label for c in model.children if isinstance(c, Atom))


def _reference_label_set(model) -> frozenset[str]:
    return frozenset(n.label for n in model.get_nodes() if n.label is not None)


def _gymact_edge_label_relation(model: PartialOrder) -> frozenset[tuple[str, str]]:
    """`model.closure` is already the real transitive closure (computed
    once at construction, per `algebra.py`'s storage law), projected onto
    activity labels."""
    out: set[tuple[str, str]] = set()
    for edge in model.closure:
        src, dst = model.children[edge.src], model.children[edge.dst]
        if isinstance(src, Atom) and isinstance(dst, Atom):
            out.add((src.label, dst.label))
    return frozenset(out)


def _reference_edge_label_relation(model) -> frozenset[tuple[str, str]]:
    """`get_transitive_closure()` returns a real `nx.DiGraph`; project its
    real edges onto activity labels, matching the gymact side's own
    transitive-closure comparison exactly (not the reduction -- so a
    reduction-vs-closure divergence would be visible, not masked)."""
    closure_graph = model.get_transitive_closure()
    out: set[tuple[str, str]] = set()
    for u, v in closure_graph.edges:
        if u.label is not None and v.label is not None:
            out.add((u.label, v.label))
    return frozenset(out)


class TestReferenceModelConformance:
    def test_activity_label_sets_match(self) -> None:
        gymact_model = build_gymact_fixture()
        reference_model = build_reference_fixture()

        assert _gymact_label_set(gymact_model) == frozenset(FIXTURE_LABELS)
        assert _reference_label_set(reference_model) == frozenset(FIXTURE_LABELS)
        assert _gymact_label_set(gymact_model) == _reference_label_set(reference_model)

    def test_precedence_edge_relations_match(self) -> None:
        gymact_model = build_gymact_fixture()
        reference_model = build_reference_fixture()

        gymact_edges = _gymact_edge_label_relation(gymact_model)
        reference_edges = _reference_edge_label_relation(reference_model)

        # Real transitive closure on both sides: Pay->Prepare, Prepare->Serve,
        # and the transitively-implied Pay->Serve.
        expected = frozenset(
            {
                ("Pay", "Prepare Coffee"),
                ("Prepare Coffee", "Serve"),
                ("Pay", "Serve"),
            }
        )
        assert gymact_edges == expected
        assert reference_edges == expected
        assert gymact_edges == reference_edges

    def test_frequency_bounds_match(self) -> None:
        gymact_model = build_gymact_fixture()
        reference_model = build_reference_fixture()

        gymact_bounds = (gymact_model.frequency.min, gymact_model.frequency.max)
        reference_bounds = (reference_model.min_freq, reference_model.max_freq)

        assert gymact_bounds == (1, 1)
        assert reference_bounds == (1, 1)
        assert gymact_bounds == reference_bounds

    def test_mutated_gymact_label_breaks_conformance(self) -> None:
        """Real falsifier, per this repo's level4-completion-law.md mutation
        discipline -- a green comparison on the happy path alone is not
        evidence the comparison can fail. Mutate one label on the gymact
        side only and assert the label-set comparison genuinely diverges."""
        mutated = PartialOrder(
            children=(Atom(label="Wrong Label"), Atom(label=FIXTURE_LABELS[1]), Atom(label=FIXTURE_LABELS[2])),
            order=frozenset(
                {
                    OrderEdge(NodeId(0), NodeId(1)),
                    OrderEdge(NodeId(1), NodeId(2)),
                }
            ),
            frequency=ONCE,
        )
        reference_model = build_reference_fixture()

        assert _gymact_label_set(mutated) != _reference_label_set(reference_model)

    def test_mutated_reference_frequency_breaks_conformance(self) -> None:
        """Same falsifier discipline, on the frequency-bounds comparison:
        mutate the reference side's cardinality only and assert the bounds
        comparison genuinely diverges."""
        Activity, RefPartialOrder = _import_reference()
        pay = Activity(FIXTURE_LABELS[0])
        prepare = Activity(FIXTURE_LABELS[1])
        mutated_reference = RefPartialOrder(
            nodes=[pay, prepare],
            edges=[(pay, prepare)],
            min_freq=0,
            max_freq=3,
        )
        gymact_model = build_gymact_fixture()

        gymact_bounds = (gymact_model.frequency.min, gymact_model.frequency.max)
        mutated_bounds = (mutated_reference.min_freq, mutated_reference.max_freq)
        assert gymact_bounds != mutated_bounds
