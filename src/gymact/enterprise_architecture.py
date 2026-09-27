"""Enterprise-architecture experiment world for RFC v26.9.26.

GymAct explores selection and transition worlds. Results are evidence/candidates,
never production authority.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import json


@dataclass(frozen=True)
class SBBCandidate:
    candidate_id: str
    abb_digest: str
    contract_digest: str
    standing: str
    cost: float
    risk: float
    reversibility: float
    method: str = "reuse"


@dataclass(frozen=True)
class ArchitectureWorld:
    strategy_digest: str
    operating_model: str
    abb_digest: str
    contract_digest: str
    baseline_sbb: str | None
    candidates: tuple[SBBCandidate, ...]


@dataclass(frozen=True)
class SelectionReceipt:
    schema: str
    abb_digest: str
    contract_digest: str
    frontier: tuple[str, ...]
    selected: str | None
    selection_digest: str
    authority: str = "NONE"


@dataclass(frozen=True)
class TransitionReceipt:
    schema: str
    baseline: str | None
    transition: str | None
    target: str | None
    disposition: str
    receipt_digest: str
    authority: str = "NONE"


def _digest(value) -> str:
    if hasattr(value, "__dataclass_fields__"):
        value = asdict(value)
    payload = json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    return "sha256:" + hashlib.sha256(payload).hexdigest()


def qualified_frontier(world: ArchitectureWorld) -> tuple[SBBCandidate, ...]:
    """Return all exact qualified candidates; never collapse qualification into selection."""

    return tuple(
        sorted(
            (
                candidate
                for candidate in world.candidates
                if candidate.standing == "QUALIFIED"
                and candidate.abb_digest == world.abb_digest
                and candidate.contract_digest == world.contract_digest
            ),
            key=lambda candidate: candidate.candidate_id,
        )
    )


def select(
    world: ArchitectureWorld,
    *,
    cost_weight: float = 1.0,
    risk_weight: float = 1.0,
    reversibility_weight: float = 1.0,
) -> SelectionReceipt:
    """Select inside the admitted frontier while retaining frontier evidence."""

    frontier = qualified_frontier(world)

    selected = min(
        frontier,
        key=lambda candidate: (
            cost_weight * candidate.cost
            + risk_weight * candidate.risk
            - reversibility_weight * candidate.reversibility,
            candidate.candidate_id,
        ),
        default=None,
    )

    body = {
        "schema": "gymact.ea-selection.v1",
        "strategy_digest": world.strategy_digest,
        "operating_model": world.operating_model,
        "abb_digest": world.abb_digest,
        "contract_digest": world.contract_digest,
        "frontier": tuple(candidate.candidate_id for candidate in frontier),
        "selected": selected.candidate_id if selected else None,
        "weights": {
            "cost": cost_weight,
            "risk": risk_weight,
            "reversibility": reversibility_weight,
        },
        "authority": "NONE",
    }

    return SelectionReceipt(
        schema=body["schema"],
        abb_digest=world.abb_digest,
        contract_digest=world.contract_digest,
        frontier=body["frontier"],
        selected=body["selected"],
        selection_digest=_digest(body),
    )


def transition(
    world: ArchitectureWorld, selected: str, *, failure: str | None = None
) -> TransitionReceipt:
    """Simulate Baseline -> Transition -> Target with explicit rollback."""

    candidate_ids = {candidate.candidate_id for candidate in qualified_frontier(world)}
    if selected not in candidate_ids:
        raise ValueError("SELECTED_SBB_NOT_IN_QUALIFIED_FRONTIER")

    if failure is None:
        disposition = "TARGET_REACHED"
        target = selected
    else:
        disposition = "ROLLED_BACK"
        target = world.baseline_sbb

    provisional = {
        "schema": "gymact.ea-transition.v1",
        "baseline": world.baseline_sbb,
        "transition": selected,
        "target": target,
        "disposition": disposition,
        "failure": failure,
        "authority": "NONE",
    }

    return TransitionReceipt(
        schema=provisional["schema"],
        baseline=world.baseline_sbb,
        transition=selected,
        target=target,
        disposition=disposition,
        receipt_digest=_digest(provisional),
    )


def method_frontier(world: ArchitectureWorld) -> dict[str, tuple[str, ...]]:
    """Expose Reuse/Compose/Extend/Manufacture alternatives without ranking across methods."""

    result = {"reuse": [], "compose": [], "extend": [], "manufacture": []}
    for candidate in qualified_frontier(world):
        result.setdefault(candidate.method, []).append(candidate.candidate_id)
    return {key: tuple(sorted(values)) for key, values in result.items()}
