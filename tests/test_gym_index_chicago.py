"""Chicago-style tests for `gymact.gym_index` and its composition-admission
verdict. Real `audit_vendor` against the real, pinned `awesome-ai-gyms`
vendor entry -- no mocks. Gated on real external-checkout availability the
same way `tests/test_kubernetes_reconciliation.py` gates on real cluster
reachability: skip with a named, honest reason if the checkout isn't present
on this machine, never fabricate or fake its content.
"""

from __future__ import annotations

import pytest

from gymact.composition import CapabilityContract, compute_residual
from gymact.composition_inventory import (
    known_capability_classifications,
    known_component_inventory,
)
from gymact.gym_index import GymIndexUnavailable, gym_index_provenance_ref, load_gym_index
from gymact.gyms.vendor_benchmarks import audit_vendor

_AUDIT = audit_vendor("awesome-ai-gyms")
_AVAILABLE = _AUDIT.standing == "PARTIAL_ALIVE"


def test_gym_index_ingestion_resolves_to_adapt():
    """Real CapabilityContract for GYM_INDEX_INGESTION, run through the real
    compute_residual against the real inventory/classification tables --
    proves this bridge composes only already-ALIVE components (no new
    provider), independent of whether the external checkout happens to be
    present on this machine right now."""
    contract = CapabilityContract(
        name="GymIndexIngestion",
        required_capabilities=frozenset({"VENDOR_PIN_AUDIT", "GYM_INDEX_INGESTION"}),
    )
    decision = compute_residual(
        contract, known_component_inventory(), known_capability_classifications()
    )

    assert decision.decision == "ADAPT"
    assert decision.orchestration_residual == frozenset({"GYM_INDEX_INGESTION"})
    assert "gymact.gyms.vendor_benchmarks.audit_vendor" in decision.selected_components


def test_process_model_discovery_is_still_blocked_by_gym_index_too():
    """This module doesn't accidentally re-open the discovery gap CROWN_P1's
    follow-up work deliberately left BLOCKED_DISCOVERY."""
    contract = CapabilityContract(
        name="ProcessModelDiscoveryViaGymIndex",
        required_capabilities=frozenset({"PROCESS_MODEL_DISCOVERY"}),
    )
    decision = compute_residual(
        contract, known_component_inventory(), known_capability_classifications()
    )
    assert decision.decision == "BLOCKED_DISCOVERY"


def test_gym_index_refuses_when_checkout_is_absent_or_mismatched():
    """Real refusal path: without a real, pin-matching external checkout,
    load_gym_index must raise GymIndexUnavailable naming the real audit
    reason -- never silently return an empty or fabricated index."""
    if _AVAILABLE:
        pytest.skip(
            "a real awesome-ai-gyms checkout matching the pinned SHA is "
            "present on this machine; the negative-path assertion below "
            "does not apply here (see test_gym_index_loads_real_entries "
            "for the positive-path assertion instead)"
        )
    with pytest.raises(GymIndexUnavailable) as excinfo:
        load_gym_index()
    assert _AUDIT.reason in str(excinfo.value)


@pytest.mark.skipif(
    not _AVAILABLE,
    reason=(
        "no real awesome-ai-gyms checkout matching the pinned "
        f"VENDOR_REVISIONS SHA found at the default vendor root "
        f"({_AUDIT.reason}); this is the same real-availability gate "
        "test_kubernetes_reconciliation.py uses for its own external "
        "dependency, not a mock substitute"
    ),
)
def test_gym_index_loads_real_entries_when_checkout_is_present():
    """Only runs with a real, pin-matching checkout on disk. Parses the real
    registry/gyms.tsv and asserts on real returned data."""
    entries = load_gym_index()

    assert len(entries) > 0
    names = {e.name for e in entries}
    assert "AirSim" in names  # real, known first data row of registry/gyms.tsv
    for entry in entries:
        assert entry.standing == "UNKNOWN"
        assert entry.canonical_url.startswith("https://")
        assert entry.kind in {
            "environment",
            "benchmark",
            "simulator",
            "framework",
            "infrastructure",
        }

    provenance_ref = gym_index_provenance_ref()
    assert provenance_ref.startswith("urn:gymact:vendor:awesome-ai-gyms:")
