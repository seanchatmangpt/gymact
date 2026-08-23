"""Plan provenance binding at GymAct's exclusive BRCE DO boundary.

Plans are SELECT/CONSTRUCT artifacts. They may describe required authority classes,
but neither a cached plan nor its provenance grants authority. A plan is bound into
an existing :class:`BrokerRequest` by adding only its content digest to the powerless
``PreparedAction``. Consequential execution still occurs exclusively through
:class:`BRCEBroker`, which admits the identity-bound execution grant before DO.

The returned binding is descriptive evidence: it content-binds the exact plan to the
exact BRCE transition receipt. It is not a second receipt and carries no authority.
"""

from __future__ import annotations

from pydantic import Field, model_validator

from gymact.brce import BRCEBroker, BrokerRequest
from gymact.crown_runtime import VerifiedTransition
from gymact.evidence import digest
from gymact.models import CanonicalInputModel, FrozenModel, Receipt


class PlanProvenance(CanonicalInputModel):
    """Immutable identity of the candidate plan and step that selected a DO."""

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


class PlannedBrokerRequest(FrozenModel):
    """A powerless BRCE request whose prepared action is bound to one plan."""

    request: BrokerRequest
    plan_provenance: PlanProvenance

    @model_validator(mode="after")
    def require_exact_plan_binding(self) -> "PlannedBrokerRequest":
        if self.request.prepared.planning_provenance_digest != self.plan_provenance.digest:
            raise ValueError("PLAN_PROVENANCE_BINDING_MISMATCH")
        return self


class PlanReceiptBinding(FrozenModel):
    """Content binding between one plan selection and one BRCE receipt."""

    plan_digest: str
    receipt_id: str
    receipt_digest: str
    binding_digest: str

    @classmethod
    def manufacture(cls, plan: PlanProvenance, receipt: Receipt) -> "PlanReceiptBinding":
        plan_digest = plan.digest
        if receipt.planning_provenance_digest != plan_digest:
            raise ValueError("RECEIPT_PLAN_PROVENANCE_MISMATCH")
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


class PlannedTransition(FrozenModel):
    """Ordinary verified BRCE transition plus non-authoritative plan binding."""

    transition: VerifiedTransition
    binding: PlanReceiptBinding


def bind_plan(request: BrokerRequest, provenance: PlanProvenance) -> PlannedBrokerRequest:
    """CONSTRUCT: bind plan identity into a powerless prepared BRCE request."""
    prepared = request.prepared.model_copy(
        update={"planning_provenance_digest": provenance.digest}
    )
    bound_request = request.model_copy(update={"prepared": prepared})
    return PlannedBrokerRequest(request=bound_request, plan_provenance=provenance)


async def execute_planned(
    broker: BRCEBroker, planned: PlannedBrokerRequest
) -> PlannedTransition:
    """DO only through BRCE, then prove the final receipt retains plan identity."""
    transition = await broker.execute(planned.request)
    binding = PlanReceiptBinding.manufacture(planned.plan_provenance, transition.receipt)
    return PlannedTransition(transition=transition, binding=binding)
