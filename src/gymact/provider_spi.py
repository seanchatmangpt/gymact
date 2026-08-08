"""Crown provider service-provider interface.

The SPI describes provider physics and BRCE-facing execution ports. Implementing this
protocol does not grant authority: callers still need an admitted ExecutionGrant before
invoking a consequential provider port.
"""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

from pydantic import Field

from gymact.action_contract import (
    ExecutionGrant,
    PreparedAction,
    ProviderHealth,
    ProviderMetadata,
    ReconciliationResult,
    SubjectRef,
)
from gymact.models import Capability, FrozenModel, Observation, Standing


class ObservationRequest(FrozenModel):
    fields: tuple[str, ...] = ()
    expected_revision: str | None = None
    parameters: dict[str, Any] = Field(default_factory=dict)


class ProviderPreparation(FrozenModel):
    provider_ref: str = Field(min_length=1)
    action_ref: str = Field(min_length=1)
    subject: SubjectRef
    provider_payload: dict[str, Any] = Field(default_factory=dict)
    preparation_ref: str = Field(min_length=1)
    standing: Standing = Standing.STRUCTURAL


class ProviderExecutionAttempt(FrozenModel):
    provider_ref: str = Field(min_length=1)
    action_ref: str = Field(min_length=1)
    subject: SubjectRef
    provider_operation_ref: str | None = None
    acknowledgement_status: str
    effect: dict[str, Any] = Field(default_factory=dict)
    standing: Standing
    reason: str | None = None


class ProviderRollbackResult(FrozenModel):
    standing: Standing
    compensated: bool = False
    rolled_back: bool = False
    observation_ref: str | None = None
    reason: str | None = None


@runtime_checkable
class CrownProvider(Protocol):
    """Provider physics behind BRCE; the protocol itself has zero authority."""

    def metadata(self) -> ProviderMetadata: ...

    def capabilities(self, subject: SubjectRef | None = None) -> tuple[Capability, ...]: ...

    async def inspect(
        self,
        subject: SubjectRef,
        request: ObservationRequest,
    ) -> Observation: ...

    async def prepare(self, intent: PreparedAction) -> ProviderPreparation: ...

    async def actuate(
        self,
        grant: ExecutionGrant,
        preparation: ProviderPreparation,
    ) -> ProviderExecutionAttempt: ...

    async def observe(
        self,
        subject: SubjectRef,
        request: ObservationRequest,
    ) -> Observation: ...

    async def reconcile(
        self,
        attempt: ProviderExecutionAttempt,
        request: ObservationRequest,
    ) -> ReconciliationResult: ...

    async def rollback(
        self,
        grant: ExecutionGrant,
        attempt: ProviderExecutionAttempt,
    ) -> ProviderRollbackResult: ...

    async def health(self) -> ProviderHealth: ...
