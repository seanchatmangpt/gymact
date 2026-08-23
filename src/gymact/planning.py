"""Plan provenance binding for bounded GymAct actuation.

Plans are SELECT/CONSTRUCT artifacts.  They may describe required authority classes,
but neither a cached plan nor its provenance grants authority.  ``execute_planned``
passes the planned intent through the ordinary :meth:`GymAct.act` path, so the same
live authority resolver, idempotency, limits, consequence and receipt laws apply.

The binding returned here is descriptive evidence: it content-binds the exact plan
provenance to the exact runtime receipt.  It is not a second receipt and carries no
execution authority.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from pydantic import Field

from gymact.evidence import digest
from gymact.models import ActuationIntent, ActuationResult, CanonicalInputModel, FrozenModel, Receipt

if TYPE_CHECKING:
    from gymact.kernel import GymAct


class PlanProvenance(CanonicalInputModel):
    """Immutable identity of the candidate plan and step that selected an actuation."""

    plan_id: str = Field(min_length=1)
    plan_version: str | None = None
    plan_step_id: str | None = None
    parent_step_ids: tuple[str, ...] = ()
    planning_receipt: str | None = None
    expected_state_digest: str | None = None
    precondition_digest: str | None = None
    postcondition_digest: str | None = None
    supersedes_plan: str | None = None
    required_authority_classes: tuple[str, ...] = ()

    @property
    def digest(self) -> str:
        """RFC8785/BLAKE3 identity inherited from GymAct evidence semantics."""
        return digest(self.model_dump(mode="json"))


class PlannedActuationIntent(ActuationIntent):
    """Actuation intent whose selection is explicitly bound to plan provenance.

    The inherited ``authority_ref`` remains only a request reference.  Plan
    provenance cannot satisfy, replace, or weaken GymAct's authority resolver.
    Because this model subclasses :class:`ActuationIntent`, GymAct's existing
    semantic idempotency digest includes the complete plan provenance.
    """

    plan_provenance: PlanProvenance


class PlanReceiptBinding(FrozenModel):
    """Content binding between one plan selection and one actual GymAct receipt."""

    plan_digest: str
    receipt_id: str
    receipt_digest: str
    binding_digest: str

    @classmethod
    def manufacture(cls, plan: PlanProvenance, receipt: Receipt) -> "PlanReceiptBinding":
        plan_digest = plan.digest
        receipt_digest = digest(receipt.model_dump(mode="json"))
        binding_digest = digest(
            {
                "schema": "urn:gymact:plan-receipt-binding:1",
                "plan_digest": plan_digest,
                "receipt_id": receipt.receipt_id,
                "receipt_digest": receipt_digest,
            }
        )
        return cls(
            plan_digest=plan_digest,
            receipt_id=receipt.receipt_id,
            receipt_digest=receipt_digest,
            binding_digest=binding_digest,
        )


class PlannedActuationResult(FrozenModel):
    """Ordinary actuation result plus non-authoritative provenance binding."""

    actuation: ActuationResult
    binding: PlanReceiptBinding


async def execute_planned(
    runtime: "GymAct", intent: PlannedActuationIntent
) -> PlannedActuationResult:
    """Execute only through GymAct's existing DO path, then bind plan to receipt."""
    result = await runtime.act(intent)
    return PlannedActuationResult(
        actuation=result,
        binding=PlanReceiptBinding.manufacture(intent.plan_provenance, result.receipt),
    )
