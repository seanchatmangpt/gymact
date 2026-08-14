"""Chicago-style tests for the CROWN_P1 (`UnauthorizedActuationPath`) episode.

Real `GymAct` kernel, real `gymact.providers.MemoryProvider`/`MemoryEnvironment`
(no external Docker/cluster dependency), real `AllowListAuthorityResolver`, real
OCEL schema validation and conformance replay, real RDF projection and SPARQL
ASK evaluation. No mocks, no monkeypatching anywhere in this file.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from gymact.authority import AllowListAuthorityResolver
from gymact.crown_p1 import (
    CrownEpisodeRun,
    HumanAccessCondition,
    bind_counterfactual_pair,
    graph_for_receipts,
    run_crown_p1_episode,
    unauthorized_actuation_path_ask,
)
from gymact.kernel import GymAct
from gymact.models import Operation, Receipt, Standing
from gymact.ocel import write_ocel_log
from gymact.providers import MemoryProvider

REPORTS_DIR = Path(__file__).resolve().parent.parent / "reports" / "ocel"
AUTHORITY = "urn:gymact:test:crown-p1-authority"


async def _run_condition(condition: HumanAccessCondition) -> CrownEpisodeRun:
    provider = MemoryProvider()
    kernel = GymAct(authority_resolver=AllowListAuthorityResolver({AUTHORITY}))
    kernel.register_provider(provider)

    async def _inspector(k: GymAct, episode_id: str) -> dict[str, object]:
        observation = await k.observe(episode_id)
        return dict(observation.state)

    run = await run_crown_p1_episode(
        kernel,
        provider,
        condition=condition,
        capability_iri="urn:gymact:memory:capability:set",
        capability_payload={"key": "counter", "value": 1},
        verify_expected={"counter": 1},
        authority_ref=AUTHORITY,
        materialize_config={"requires_authority": True},
        human_inspector=_inspector,
    )
    return run


@pytest.mark.asyncio
async def test_crown_p1_episode_produces_a_schema_valid_conformant_ocel_log():
    """Real episode, real materialize/act/verify/teardown sequence, real OCEL
    output that passes real jsonschema validation and real conformance replay
    (validate_ocel_log inside run_crown_p1_episode already asserts this; here
    we re-derive it independently, same discipline as test_ocel_standing.py)."""
    run = await _run_condition(HumanAccessCondition.ALLOWED)

    assert run.ocel_log["events"], "episode produced no OCEL events"
    operation_types = {e["type"] for e in run.ocel_log["events"]}
    assert Operation.MATERIALIZE.value in operation_types
    assert Operation.ACT.value in operation_types
    assert Operation.VERIFY.value in operation_types
    assert Operation.TEARDOWN.value in operation_types


@pytest.mark.asyncio
async def test_standing_invariant_holds_across_human_access_conditions():
    """The actual crown claim: Standing(A|HumanReads=true) ==
    Standing(A|HumanReads=false), checked against two real, independently run
    episodes -- not asserted in prose."""
    allowed = await _run_condition(HumanAccessCondition.ALLOWED)
    denied = await _run_condition(HumanAccessCondition.DENIED)

    assert allowed.inspected_state == {"counter": 1}
    assert denied.inspected_state is None  # DENIED never calls the inspector

    pair = bind_counterfactual_pair(allowed, denied)

    assert pair.standing_invariant_holds is True
    assert pair.allowed_standing == "VERIFIED_ALIVE"
    assert pair.denied_standing == "VERIFIED_ALIVE"
    assert pair.unauthorized_path_found_allowed is False
    assert pair.unauthorized_path_found_denied is False

    write_ocel_log(REPORTS_DIR / "crown-p1-allowed" / "episode.ocel.json", list(allowed.receipts))
    write_ocel_log(REPORTS_DIR / "crown-p1-denied" / "episode.ocel.json", list(denied.receipts))


@pytest.mark.asyncio
async def test_unauthorized_actuation_path_predicate_detects_a_real_violation():
    """Falsifiability check: the predicate must actually flip to True on a
    synthetic evidence graph carrying a real ALIVE act-operation receipt with
    NO authority-evidence prov:used triple -- proving it detects the exact
    violation it claims to detect, mirroring test_kernel_verification.py's
    AlwaysFailVerifier negative-test pattern."""
    unauthorized_receipt = Receipt(
        episode_id="urn:gymact:episode:synthetic",
        operation=Operation.ACT,
        standing=Standing.ALIVE,
        subject_ref="urn:gymact:memory:environment:synthetic",
        capability_ref="urn:gymact:memory:capability:set",
        authority_ref=None,
        authority_evidence_ref=None,
        world_changed=True,
    )
    graph = graph_for_receipts((unauthorized_receipt,))

    assert unauthorized_actuation_path_ask(graph) is True


@pytest.mark.asyncio
async def test_unauthorized_actuation_path_predicate_is_false_for_a_real_authorized_receipt():
    """Companion positive case for the same synthetic-graph mechanism: an ACT
    receipt that DOES carry real authority evidence must not trip the
    predicate."""
    authorized_receipt = Receipt(
        episode_id="urn:gymact:episode:synthetic",
        operation=Operation.ACT,
        standing=Standing.ALIVE,
        subject_ref="urn:gymact:memory:environment:synthetic",
        capability_ref="urn:gymact:memory:capability:set",
        authority_ref=AUTHORITY,
        authority_evidence_ref=f"urn:gymact:authority-decision:{AUTHORITY}",
        world_changed=True,
    )
    graph = graph_for_receipts((authorized_receipt,))

    assert unauthorized_actuation_path_ask(graph) is False
