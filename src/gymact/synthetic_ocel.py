"""Canonical OCEL 2.0 gym results with explicit execution/manufacture provenance.

The OCEL document is the operational result surface. Provenance is deliberately
kept outside the OCEL document so an admitted operational observer can compare
real, executed, and manufactured histories without a synthetic-only marker
leaking into the domain trace. The audit projection always restores provenance.

A manufactured history is never execution evidence: it cannot carry an
execution receipt and cannot claim observed execution.
"""

from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from dataclasses import asdict, dataclass
from enum import StrEnum
from typing import Any, Mapping, Sequence

from gymact.models import Receipt
from gymact.ocel import digest_ocel_log, receipts_to_ocel, validate_ocel_log


class OCELTraceOrigin(StrEnum):
    """Privileged provenance class for an OCEL gym result."""

    REAL_OBSERVED = "REAL_OBSERVED"
    GYM_EXECUTED = "GYM_EXECUTED"
    GGEN_MANUFACTURED = "GGEN_MANUFACTURED"


def _canonical_digest(value: Any) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


@dataclass(frozen=True)
class OCELTraceProvenance:
    """Audit-only provenance for one canonical OCEL history."""

    origin: OCELTraceOrigin
    trace_digest: str
    observed_execution: bool
    manufactured_trace: bool
    claimed_actor: str | None = None
    source_ref: str | None = None
    generator: str | None = None
    generator_spec_digest: str | None = None
    world_model_digest: str | None = None
    seed: int | str | None = None

    def __post_init__(self) -> None:
        if not self.trace_digest:
            raise ValueError("OCEL_TRACE_DIGEST_REQUIRED")
        if self.origin is OCELTraceOrigin.GGEN_MANUFACTURED:
            if self.observed_execution:
                raise ValueError("MANUFACTURED_TRACE_CANNOT_CLAIM_OBSERVED_EXECUTION")
            if not self.manufactured_trace:
                raise ValueError("MANUFACTURED_TRACE_MUST_DECLARE_MANUFACTURE")
            if not self.claimed_actor:
                raise ValueError("MANUFACTURED_TRACE_CLAIMED_ACTOR_REQUIRED")
            if not self.generator:
                raise ValueError("MANUFACTURED_TRACE_GENERATOR_REQUIRED")
            if not self.generator_spec_digest:
                raise ValueError("MANUFACTURED_TRACE_GENERATOR_SPEC_DIGEST_REQUIRED")
            if not self.world_model_digest:
                raise ValueError("MANUFACTURED_TRACE_WORLD_MODEL_DIGEST_REQUIRED")
        else:
            if not self.observed_execution:
                raise ValueError("OBSERVED_OR_EXECUTED_TRACE_MUST_DECLARE_EXECUTION")
            if self.manufactured_trace:
                raise ValueError("OBSERVED_OR_EXECUTED_TRACE_CANNOT_DECLARE_MANUFACTURE")
            if self.generator is not None:
                raise ValueError("EXECUTED_TRACE_CANNOT_DECLARE_SYNTHETIC_GENERATOR")
            if self.generator_spec_digest is not None or self.world_model_digest is not None:
                raise ValueError("EXECUTED_TRACE_CANNOT_DECLARE_SYNTHETIC_MODEL_DIGESTS")

    def as_audit_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["origin"] = self.origin.value
        return data


@dataclass(frozen=True)
class OCELGymResult:
    """One canonical gym result with operational and privileged audit views."""

    log: dict[str, Any]
    provenance: OCELTraceProvenance
    execution_receipt_refs: tuple[str, ...] = ()
    cursor: str | None = None

    def __post_init__(self) -> None:
        copied = deepcopy(self.log)
        validate_ocel_log(copied)
        if digest_ocel_log(copied) != self.provenance.trace_digest:
            raise ValueError("OCEL_TRACE_DIGEST_MISMATCH")
        object.__setattr__(self, "log", copied)

        if self.provenance.origin is OCELTraceOrigin.GGEN_MANUFACTURED:
            if self.execution_receipt_refs:
                raise ValueError("MANUFACTURED_TRACE_CANNOT_CARRY_EXECUTION_RECEIPT")
        elif self.provenance.origin is OCELTraceOrigin.GYM_EXECUTED:
            if not self.execution_receipt_refs:
                raise ValueError("GYM_EXECUTED_TRACE_REQUIRES_EXECUTION_RECEIPT")

    def operational_view(self) -> dict[str, Any]:
        """Projection supplied to ordinary domain observers/discriminators."""

        return deepcopy(self.log)

    def audit_view(self) -> dict[str, Any]:
        """Privileged projection that always reveals origin and proof identity."""

        return {
            "ocel": deepcopy(self.log),
            "provenance": self.provenance.as_audit_dict(),
            "execution_receipt_refs": list(self.execution_receipt_refs),
            "cursor": self.cursor,
        }


def manufacture_ocel_history(
    *,
    history_spec: Mapping[str, Any],
    claimed_actor: str,
    generator_spec: Any,
    world_model: Any,
    seed: int | str,
    generator: str = "ggen",
    cursor: str | None = None,
) -> OCELGymResult:
    """Admit a GGen-manufactured OCEL history as synthetic evidence.

    The caller/GGen manufactures the domain history; GymAct validates the
    official OCEL 2.0 shape, content-addresses the trace and its generating
    specifications, and returns a result with zero execution receipts.

    This function has no BRCE/actuator dependency and cannot confer execution
    standing. Same inputs produce the same trace/spec/model digests.
    """

    log = deepcopy(dict(history_spec))
    validate_ocel_log(log)
    provenance = OCELTraceProvenance(
        origin=OCELTraceOrigin.GGEN_MANUFACTURED,
        trace_digest=digest_ocel_log(log),
        observed_execution=False,
        manufactured_trace=True,
        claimed_actor=claimed_actor,
        generator=generator,
        generator_spec_digest=_canonical_digest(generator_spec),
        world_model_digest=_canonical_digest(world_model),
        seed=seed,
    )
    return OCELGymResult(log=log, provenance=provenance, cursor=cursor)


def executed_ocel_result(
    receipts: Sequence[Receipt],
    *,
    claimed_actor: str = "gymact.runtime.GymAct",
    source_ref: str = "gymact:receipt-trail",
    cursor: str | None = None,
) -> OCELGymResult:
    """Build the symmetric canonical result from an actually executed trail."""

    receipt_list = list(receipts)
    log = receipts_to_ocel(receipt_list)
    provenance = OCELTraceProvenance(
        origin=OCELTraceOrigin.GYM_EXECUTED,
        trace_digest=digest_ocel_log(log),
        observed_execution=True,
        manufactured_trace=False,
        claimed_actor=claimed_actor,
        source_ref=source_ref,
    )
    return OCELGymResult(
        log=log,
        provenance=provenance,
        execution_receipt_refs=tuple(receipt.receipt_id for receipt in receipt_list),
        cursor=cursor,
    )


def observed_ocel_result(
    log: Mapping[str, Any],
    *,
    source_ref: str,
    claimed_actor: str | None = None,
    cursor: str | None = None,
) -> OCELGymResult:
    """Admit an externally observed real-system OCEL history."""

    copied = deepcopy(dict(log))
    validate_ocel_log(copied)
    provenance = OCELTraceProvenance(
        origin=OCELTraceOrigin.REAL_OBSERVED,
        trace_digest=digest_ocel_log(copied),
        observed_execution=True,
        manufactured_trace=False,
        claimed_actor=claimed_actor,
        source_ref=source_ref,
    )
    return OCELGymResult(log=copied, provenance=provenance, cursor=cursor)


def operationally_equivalent(left: OCELGymResult, right: OCELGymResult) -> bool:
    """Exact equivalence under the canonical operational OCEL projection."""

    return _canonical_digest(left.operational_view()) == _canonical_digest(
        right.operational_view()
    )
