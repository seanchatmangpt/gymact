"""CONSTRUCT8: a powerless eight-bit projection of canonical action law.

The canonical semantic source remains :class:`gymact.action_contract.ActionDefinition`.
A CONSTRUCT8 word is deliberately insufficient to authorize or execute an action: it
only carries a compact execution-law projection plus the digest and semantic identity
of the canonical contract from which it was manufactured.

Bit layout (least-significant first):

* bits 0..1: idempotency class
* bits 2..3: reversal class
* bit 4: preconditions are present
* bit 5: explicit capability/policy authority requirements are present
* bit 6: an output schema is present
* bit 7: non-zero cost/risk is declared

The full action semantics, effects, verifier, provider binding, and BRCE authority
remain outside the byte and are recovered only through ``source_contract_digest``.
"""

from __future__ import annotations

from typing import Literal

from pydantic import Field

from gymact.action_contract import ActionDefinition, IdempotencyClass, ReversalClass
from gymact.models import FrozenModel

CONSTRUCT8_SCHEMA = "urn:gymact:construct8:v1"

_IDEMPOTENCY_MASK = 0b00000011
_REVERSAL_MASK = 0b00001100
_REVERSAL_SHIFT = 2
_PRECONDITION_BIT = 0b00010000
_AUTHORITY_BIT = 0b00100000
_OUTPUT_BIT = 0b01000000
_COST_BIT = 0b10000000

_IDEMPOTENCY_TO_CODE = {
    IdempotencyClass.UNKNOWN: 0,
    IdempotencyClass.IDEMPOTENT: 1,
    IdempotencyClass.CONDITIONALLY_IDEMPOTENT: 2,
    IdempotencyClass.NON_IDEMPOTENT: 3,
}
_CODE_TO_IDEMPOTENCY = {value: key for key, value in _IDEMPOTENCY_TO_CODE.items()}

_REVERSAL_TO_CODE = {
    ReversalClass.UNKNOWN: 0,
    ReversalClass.REVERSIBLE: 1,
    ReversalClass.COMPENSATABLE: 2,
    ReversalClass.IRREVERSIBLE: 3,
}
_CODE_TO_REVERSAL = {value: key for key, value in _REVERSAL_TO_CODE.items()}


class Construct8Word(FrozenModel):
    """Digest-bound, authority-free 8-bit projection of one canonical action."""

    schema_uri: Literal["urn:gymact:construct8:v1"] = Field(
        default=CONSTRUCT8_SCHEMA,
        alias="schema",
        serialization_alias="schema",
    )
    source_contract_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    action_ref: str = Field(min_length=1)
    value: int = Field(ge=0, le=255)
    do_authority: Literal[False] = False

    @property
    def idempotency(self) -> IdempotencyClass:
        return _CODE_TO_IDEMPOTENCY[self.value & _IDEMPOTENCY_MASK]

    @property
    def reversal(self) -> ReversalClass:
        code = (self.value & _REVERSAL_MASK) >> _REVERSAL_SHIFT
        return _CODE_TO_REVERSAL[code]

    @property
    def has_preconditions(self) -> bool:
        return bool(self.value & _PRECONDITION_BIT)

    @property
    def has_explicit_authority_requirements(self) -> bool:
        return bool(self.value & _AUTHORITY_BIT)

    @property
    def has_output_schema(self) -> bool:
        return bool(self.value & _OUTPUT_BIT)

    @property
    def has_declared_cost_or_risk(self) -> bool:
        return bool(self.value & _COST_BIT)

    @property
    def hex(self) -> str:
        """Canonical two-hex-digit representation for tiny-runtime manufacture."""
        return f"{self.value:02x}"


def encode_construct8(action: ActionDefinition) -> int:
    """Deterministically encode execution-law features into one byte.

    This function performs no admission and grants no authority. Unknown execution
    semantics remain explicitly encoded as zero-valued enum lanes rather than being
    guessed or promoted.
    """

    value = _IDEMPOTENCY_TO_CODE[action.idempotency]
    value |= _REVERSAL_TO_CODE[action.reversal] << _REVERSAL_SHIFT

    if action.preconditions:
        value |= _PRECONDITION_BIT
    if action.authority.capability_refs or action.authority.policy_refs:
        value |= _AUTHORITY_BIT
    if action.output_schema:
        value |= _OUTPUT_BIT

    cost = action.cost
    if any(
        (
            cost.monetary,
            cost.expected_wall_time_s,
            cost.compute_units,
            cost.expected_human_approvals,
            cost.expected_failure_probability,
        )
    ):
        value |= _COST_BIT

    return value


def manufacture_construct8(
    action: ActionDefinition,
    *,
    source_contract_digest: str,
) -> Construct8Word:
    """CONSTRUCT only: manufacture a powerless byte bound to canonical semantics."""

    return Construct8Word(
        source_contract_digest=source_contract_digest,
        action_ref=action.semantic_id,
        value=encode_construct8(action),
    )
