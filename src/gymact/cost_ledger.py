"""Cost-per-action as a query over the real OCEL evidence graph.

Cost is never a stored/cached field -- it is summed on demand from the
`cost:<unit>` attributes `gymact.ocel.receipts_to_ocel` already projects onto
each real event, from `Receipt.costs` (see `gymact.models.CostDimension`).
This keeps exactly one durable place cost lives (the receipt/OCEL trail) and
zero parallel bookkeeping (`.claude/rules/no-dual-bookkeeping.md`).

Cost is explicitly not always money: a `unit` may be `"usd"`, but also
`"compute_hour"`, `"fuel_liter"`, `"political_capital"`, or any other real
dimension a gym declares. `sum_costs_by_unit` never converts between units --
that would silently manufacture an exchange rate nobody asserted.
"""

from __future__ import annotations

from typing import Any

_COST_PREFIX = "cost:"


def sum_costs_by_unit(events: list[dict[str, Any]]) -> dict[str, float]:
    """Sum every `cost:<unit>` attribute across a real OCEL event list.

    `events` is the `"events"` array of a `receipts_to_ocel(...)` log (or any
    subset of it -- e.g. one episode's events, filtered by the caller). Units
    with zero recorded events are absent from the result, never coerced to
    `0.0` -- absence of a cost fact is not evidence the cost was zero.
    """
    totals: dict[str, float] = {}
    for event in events:
        for attribute in event.get("attributes", ()):
            name = attribute.get("name", "")
            if not name.startswith(_COST_PREFIX):
                continue
            unit = name[len(_COST_PREFIX) :]
            value = attribute.get("value")
            if not isinstance(value, int | float) or isinstance(value, bool):
                continue
            totals[unit] = totals.get(unit, 0.0) + float(value)
    return totals


def cost_sources_by_unit(events: list[dict[str, Any]]) -> dict[str, set[str]]:
    """Return the distinct real `cost_source:<unit>` provenance strings seen.

    Lets a caller check whether a total mixes `declared_estimate` and
    `observed_actual` figures, or cites more than one pricing source, before
    treating the sum as a single clean number.
    """
    sources: dict[str, set[str]] = {}
    for event in events:
        for attribute in event.get("attributes", ()):
            name = attribute.get("name", "")
            if not name.startswith("cost_source:"):
                continue
            unit = name[len("cost_source:") :]
            value = attribute.get("value")
            if isinstance(value, str):
                sources.setdefault(unit, set()).add(value)
    return sources
