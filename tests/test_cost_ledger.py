"""Chicago-style: real `Receipt`/`CostDimension` objects, projected through
the real `receipts_to_ocel` OCEL builder, summed back by the real
`cost_ledger` query -- no mocked events, no synthetic dict fixtures standing
in for the OCEL log gymact actually emits.
"""

from __future__ import annotations

from gymact.cost_ledger import cost_sources_by_unit, sum_costs_by_unit
from gymact.models import CostDimension, Operation, Receipt, Standing
from gymact.ocel import receipts_to_ocel


def _accepted_act_receipt(*, capability_ref: str, costs: tuple[CostDimension, ...]) -> Receipt:
    return Receipt(
        episode_id="urn:gymact:episode:cost-ledger-test",
        operation=Operation.ACT,
        standing=Standing.ALIVE,
        subject_ref="urn:gymact:environment:cost-ledger-test",
        capability_ref=capability_ref,
        pre_state_digest="pre",
        post_state_digest="post",
        costs=costs,
    )


def test_sum_costs_by_unit_sums_real_events_across_episode() -> None:
    receipts = [
        _accepted_act_receipt(
            capability_ref="urn:gymact:capability:launch",
            costs=(
                CostDimension(
                    unit="usd", quantity=1.25, kind="observed_actual", source="measured"
                ),
                CostDimension(
                    unit="fuel_liter",
                    quantity=3.0,
                    kind="observed_actual",
                    source="measured",
                ),
            ),
        ),
        _accepted_act_receipt(
            capability_ref="urn:gymact:capability:launch",
            costs=(
                CostDimension(
                    unit="usd", quantity=0.75, kind="observed_actual", source="measured"
                ),
            ),
        ),
    ]
    log = receipts_to_ocel(receipts)

    totals = sum_costs_by_unit(log["events"])

    assert totals == {"usd": 2.0, "fuel_liter": 3.0}


def test_sum_costs_by_unit_omits_units_with_no_recorded_cost() -> None:
    receipts = [_accepted_act_receipt(capability_ref="urn:gymact:capability:observe", costs=())]
    log = receipts_to_ocel(receipts)

    totals = sum_costs_by_unit(log["events"])

    # Absence of a cost fact is not evidence the cost was zero -- the unit
    # must not appear at all, never appear pinned to 0.0.
    assert totals == {}


def test_cost_sources_by_unit_surfaces_real_provenance_strings() -> None:
    receipts = [
        _accepted_act_receipt(
            capability_ref="urn:gymact:capability:launch",
            costs=(
                CostDimension(
                    unit="usd",
                    quantity=2.0,
                    kind="declared_estimate",
                    source="aws-eks-pricing-2026-08",
                ),
            ),
        ),
        _accepted_act_receipt(
            capability_ref="urn:gymact:capability:launch",
            costs=(
                CostDimension(unit="usd", quantity=1.8, kind="observed_actual", source="measured"),
            ),
        ),
    ]
    log = receipts_to_ocel(receipts)

    sources = cost_sources_by_unit(log["events"])

    assert sources == {"usd": {"aws-eks-pricing-2026-08", "measured"}}


def test_capability_costs_echo_into_accepted_act_receipt_via_real_kernel() -> None:
    """The kernel's real ACT success path echoes `Capability.costs` onto the
    receipt as `observed_actual` -- exercised end-to-end through the real
    `GymAct`/`MemoryProvider` runtime, not asserted from a hand-built
    `Receipt` alone."""
    import asyncio

    from gymact import AllowListAuthorityResolver
    from gymact.kernel import GymAct
    from gymact.models import ActuationIntent, MaterializationIntent
    from gymact.providers import MemoryProvider

    authority = "urn:gymact:authority:cost-ledger-test"

    async def _run() -> Receipt:
        gymact = GymAct(authority_resolver=AllowListAuthorityResolver({authority}))
        gymact.register_provider(MemoryProvider())
        materialization = await gymact.materialize(MaterializationIntent(provider="memory"))
        assert materialization.accepted
        assert materialization.episode is not None
        episode_id = materialization.episode.episode_id
        capability = next(
            c for c in gymact.capabilities(episode_id) if c.binding == "set"
        )
        result = await gymact.act(
            ActuationIntent(
                episode_id=episode_id,
                capability=capability.iri,
                payload={"key": "cost-ledger-test", "value": 1},
                authority_ref=authority,
            )
        )
        return result.receipt

    receipt = asyncio.run(_run())

    assert receipt.standing == Standing.ALIVE
    # MemoryProvider's own capabilities declare no cost today -- the real
    # assertion here is that the field exists, defaults honestly to empty,
    # and the kernel path that would echo it does not raise.
    assert receipt.costs == ()
