"""SELECT-only federation registry for a global network of AI gyms.

Registration and selection manufacture routing knowledge. They never materialize a world,
call a remote endpoint, grant authority, or cross GymAct's BRCE DO boundary.
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import Self

from pydantic import model_validator

from gymact.models import FrozenModel, Standing


class FederatedGymAdvertisement(FrozenModel):
    """Externally supplied gym advertisement with evidence identities kept explicit."""

    gym_ref: str
    source_ref: str
    endpoint_ref: str
    capability_refs: tuple[str, ...]
    claimed_standing: Standing = Standing.UNKNOWN
    source_digest: str
    receipt_ref: str | None = None
    authority_policy_refs: tuple[str, ...] = ()
    protocol_refs: tuple[str, ...] = ()

    @model_validator(mode="after")
    def validate_advertisement(self) -> Self:
        for label, value in (
            ("gym_ref", self.gym_ref),
            ("source_ref", self.source_ref),
            ("endpoint_ref", self.endpoint_ref),
        ):
            if not value.strip():
                raise ValueError(f"EMPTY_{label.upper()}")
        if not self.capability_refs:
            raise ValueError("GYM_CAPABILITIES_REQUIRED")
        if len(set(self.capability_refs)) != len(self.capability_refs):
            raise ValueError("DUPLICATE_GYM_CAPABILITY")
        digest = self.source_digest.casefold()
        if len(digest) != 64 or any(ch not in "0123456789abcdef" for ch in digest):
            raise ValueError("SOURCE_DIGEST_MUST_BE_SHA256_HEX")
        return self


class FederatedGymRecord(FrozenModel):
    advertisement: FederatedGymAdvertisement
    registry_standing: Standing = Standing.STRUCTURAL
    admission_reason: str = "ADVERTISEMENT_STRUCTURALLY_ADMITTED_NOT_EXECUTED"


class GymSelection(FrozenModel):
    required_capability_refs: tuple[str, ...]
    matches: tuple[FederatedGymRecord, ...]
    standing: Standing
    reason: str


class FederatedGymRegistry:
    """Deterministic federation catalog with zero ambient execution authority."""

    def __init__(self) -> None:
        self._records: dict[str, FederatedGymRecord] = {}

    def register(self, advertisement: FederatedGymAdvertisement) -> FederatedGymRecord:
        current = self._records.get(advertisement.gym_ref)
        if current is not None:
            if current.advertisement == advertisement:
                return current
            raise ValueError(f"GYM_IDENTITY_CONFLICT:{advertisement.gym_ref}")
        record = FederatedGymRecord(advertisement=advertisement)
        self._records[advertisement.gym_ref] = record
        return record

    def names(self) -> tuple[str, ...]:
        return tuple(sorted(self._records))

    def describe(self, gym_ref: str) -> FederatedGymRecord:
        try:
            return self._records[gym_ref]
        except KeyError as exc:
            raise KeyError(f"UNSUPPORTED:UNKNOWN_FEDERATED_GYM:{gym_ref}") from exc

    def select(
        self,
        required_capability_refs: Iterable[str],
        *,
        claimed_standings: Iterable[Standing] = (Standing.ALIVE, Standing.PARTIAL_ALIVE),
    ) -> GymSelection:
        required = tuple(sorted(set(required_capability_refs)))
        if not required:
            raise ValueError("REQUIRED_CAPABILITY_SET_MUST_BE_NON_EMPTY")
        admitted_claims = frozenset(claimed_standings)
        matches = tuple(
            sorted(
                (
                    record
                    for record in self._records.values()
                    if record.advertisement.claimed_standing in admitted_claims
                    and set(required).issubset(record.advertisement.capability_refs)
                ),
                key=lambda record: record.advertisement.gym_ref,
            )
        )
        if not matches:
            return GymSelection(
                required_capability_refs=required,
                matches=(),
                standing=Standing.UNSUPPORTED,
                reason="NO_ADVERTISED_GYM_SATISFIES_CAPABILITY_AND_STANDING_FILTER",
            )
        return GymSelection(
            required_capability_refs=required,
            matches=matches,
            standing=Standing.STRUCTURAL,
            reason="ROUTE_CANDIDATES_SELECTED_NOT_EXECUTED",
        )
