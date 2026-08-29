# Copyright (c) AIRBUS and its affiliates.
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Integration seam onto ``~/POWL``'s canonical ``powl.execution`` engine.

What this module IS
--------------------
A real, working import of ``powl.execution`` (the canonical ``TaggedPOWL``
execution engine from the sibling ``~/POWL`` repo, wired into this project as
a real editable path dependency in ``pyproject.toml``: ``powl = { path =
"/Users/sac/POWL", editable = true }`` under ``[tool.uv.sources]``), with its
public API re-exported here under ``gymact.powl.canonical_bridge`` so future
callers have one place to start migrating onto it.

What this module IS NOT
------------------------
It is **not** a replacement for :mod:`gymact.powl.executor`. This project's
own executor implements the same conceptual semantics -- marking, enabled
sets, replay, refusals -- independently, on this project's own
:class:`~gymact.powl.algebra.PowlNode` object model (``Start``/``End``/
``Atom``/``Silent``/``PartialOrder``/``ChoiceGraph``, arena-indexed,
frequency-aware, guard-evaluated). ``powl.execution`` operates on a
*structurally different* object model: ``TaggedPOWL``/``Activity`` from
``~/POWL``'s own algebra, not this project's ``PowlNode``.

Those two models are not the same shape. ``PowlNode``'s ``ChoiceGraph`` is an
arbitrary (possibly cyclic) directed graph over indexed children with guarded
edges and a ``Frequency`` object governing repetition; ``~/POWL``'s
``TaggedPOWL`` model is built around a different composition discipline
entirely (see ``~/POWL/powl/objects/obj.py`` for its own node kinds). Writing
a real, non-lossy structural converter between them is a genuine design task
-- deciding how an arena-indexed cyclic choice graph with per-edge guards
maps onto ``TaggedPOWL``'s composition primitives without silently dropping
semantics -- and is explicitly out of scope for this pass. See
``~/POWL/docs/superpowers/specs/2026-08-14-fortune-5-concurrent-runner-design.md``
for the design decision that scoped it out (this project's independently
diverged fork is left as-is; only the dependency wiring and this seam are
in scope now).

# NOT YET WIRED
--------------
The one thing this module does **not** do, stated exactly: convert a real
``gymact.powl.algebra.PowlNode`` into a real ``powl.objects.obj.POWL``/
``TaggedPOWL`` instance (or the reverse). No such converter exists here.
Nothing in :mod:`gymact.powl.executor` has been changed to call into
``powl.execution`` -- it still runs its own, independent marking/enabled/
replay logic entirely on ``PowlNode``. Until a real structural converter is
written, importing ``powl.execution``'s ``replay``/``enabled``/``Marking``
and handing them a ``PowlNode`` tree would be wrong (the two ``Marking``
types, ``enabled`` signatures, and node kinds do not correspond), so this
module makes no attempt to bridge the two at the object level -- it only
proves the dependency is real and gives future callers a stable import path.
"""

from __future__ import annotations

from powl.execution import (
    Chooser,
    ConformanceResult,
    ExecutionRefusal,
    ExecutionStep,
    Marking,
    PhaseBoundary,
    PowlRefusal,
    RepeatDecider,
    check_conformance,
    enabled,
    is_final,
    phase_boundaries,
    replay,
    replay_concurrent,
)

__all__ = [
    "Chooser",
    "ConformanceResult",
    "ExecutionRefusal",
    "ExecutionStep",
    "Marking",
    "PhaseBoundary",
    "PowlRefusal",
    "RepeatDecider",
    "check_conformance",
    "enabled",
    "is_final",
    "phase_boundaries",
    "replay",
    "replay_concurrent",
]
