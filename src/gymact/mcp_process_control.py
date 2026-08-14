"""Deterministic MCP-call dispatch against a hand/ontology-authored partial-
order control graph — the ADAPT-composable slice of the "compile the MCP call
sequence instead of re-reasoning it" concept explored this session (see
`.claude/plans/yes-gymact-is-exactly-purrfect-shell.md`).

Scope, stated explicitly so this module is never oversold:

- The control graph (`ProcessControlGraph`) is hand/ontology-authored, the
  same trust model as `gymact.gdmcp`'s solution catalog and
  `gymact.composition_inventory`'s tables — NOT mined from OCEL logs via ILP
  or any other discovery algorithm. Process-model *discovery* stays out of
  scope (see `composition_inventory.py`'s deliberate omission of a
  `PROCESS_MODEL_DISCOVERY` classification entry).
- This module composes only already-`ALIVE` GymAct components: `GymAct.act`
  (which itself still runs `CapabilityScope`/`AuthorityResolver` unchanged)
  and `gymact.process.ConformanceChecker`. Per the composition-admission gate
  (`gymact.composition`), the capability contract this module fulfills
  resolves to `ADAPT`, not `CREATE_PROVIDER` — see
  `tests/test_mcp_process_control_admission_chicago.py`.
- `MCPValidity != DOAuthority` holds exactly as it does everywhere else in
  this codebase: a capability being *licensed by the graph* never bypasses
  `CapabilityScope`/`AuthorityResolver` admission. `dispatch()` below refuses
  before ever calling `kernel.act()` if the graph doesn't license the call,
  but if the graph DOES license it, `kernel.act()`'s own gates still run
  unchanged and can still refuse it.
"""

from __future__ import annotations

from typing import Any

from gymact.kernel import GymAct
from gymact.models import ActuationIntent, ActuationResult, FrozenModel, Operation, Standing
from gymact.process import ConformanceChecker


class ProcessTransition(FrozenModel):
    """One admitted edge: from a completed capability (or `None` for START)
    to a licensed next capability. Hand/ontology-authored, not mined.

    `condition` is reserved for a future guard-based dispatch (e.g. "only if
    the last observed state matched X") and is NOT currently evaluated by
    `ProcessControlGraph.licensed_next`/`dispatch` — only capability-to-
    capability adjacency is enforced today. Stated here so this field is
    never mistaken for live behavior."""

    from_capability: str | None = None
    to_capability: str
    condition: str | None = None


class ProcessControlGraph(FrozenModel):
    """A real, evaluable partial-order over capability_refs."""

    graph_id: str
    transitions: tuple[ProcessTransition, ...]

    def licensed_next(self, completed: tuple[str, ...]) -> frozenset[str]:
        """Pure function: given the capability_refs completed so far (in
        order), return the set of capability_refs licensed to come next.
        Only the most recently completed capability (or START, if none) is
        consulted -- this graph shape is a first-order Markov chain over
        capability_refs, not a full partial-order/choice algebra (see module
        docstring's scope note)."""
        predecessor = completed[-1] if completed else None
        return frozenset(
            t.to_capability for t in self.transitions if t.from_capability == predecessor
        )


class DispatchRefusal(RuntimeError):
    """Raised when a requested capability is not licensed by the graph at
    the current point in the episode, or when the resulting operation
    sequence fails a real post-hoc conformance replay. Never raised in place
    of a CapabilityScope/AuthorityResolver refusal -- those surface as an
    ordinary `ActuationResult(accepted=False, ...)`, unchanged, exactly as
    `kernel.act()` already returns them."""


def _completed_capabilities(kernel: GymAct, episode_id: str) -> tuple[str, ...]:
    """Real, ordered history of accepted (`Standing.ALIVE`) ACT capability
    refs for this episode, read directly off `kernel.episode_receipts` --
    the same real receipt trail every other evidence path in this codebase
    reads from, not a separately tracked shadow state."""
    receipts = kernel.episode_receipts(episode_id)
    return tuple(
        r.capability_ref
        for r in receipts
        if r.operation is Operation.ACT and r.standing is Standing.ALIVE and r.capability_ref
    )


async def dispatch(
    kernel: GymAct,
    graph: ProcessControlGraph,
    episode_id: str,
    *,
    capability_iri: str,
    payload: dict[str, Any],
    authority_ref: str | None = None,
) -> ActuationResult:
    """Deterministically gate one MCP-shaped call against `graph`, then
    delegate to the real, unchanged `GymAct.act()` gates, then audit the
    resulting real operation sequence with a real `ConformanceChecker`
    replay -- composing three already-`ALIVE` collaborators, no LLM call
    anywhere in this function."""
    completed = _completed_capabilities(kernel, episode_id)
    licensed = graph.licensed_next(completed)
    if capability_iri not in licensed:
        raise DispatchRefusal(
            f"DISPATCH_REFUSED:NOT_LICENSED capability={capability_iri!r} "
            f"graph={graph.graph_id!r} completed={completed!r} licensed={sorted(licensed)!r}"
        )

    result = await kernel.act(
        ActuationIntent(
            episode_id=episode_id,
            capability=capability_iri,
            payload=payload,
            authority_ref=authority_ref,
        )
    )
    if not result.accepted:
        # The graph licensed this call; CapabilityScope/AuthorityResolver did
        # not. Real, unmodified kernel refusal -- returned as-is, not
        # re-wrapped, so callers see the same ActuationResult they always
        # would have without this module in front of kernel.act().
        return result

    operations = [
        r.operation for r in kernel.episode_receipts(episode_id) if r.operation is not None
    ]
    conformance = ConformanceChecker().check(operations)
    if not conformance.conformant:
        reasons = "; ".join(d.reason for d in conformance.deviations)
        raise DispatchRefusal(f"DISPATCH_REFUSED:POST_HOC_NONCONFORMANT {reasons}")

    return result
