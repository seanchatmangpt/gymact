from __future__ import annotations

from gymact.provider_spi import (
    CrownProvider,
    ObservationRequest,
    ProviderExecutionAttempt,
    ProviderPreparation,
    ProviderRollbackResult,
)
from gymact.models import Standing


class CompleteProviderShape:
    def metadata(self): ...

    def capabilities(self, subject=None): ...

    async def inspect(self, subject, request): ...

    async def prepare(self, intent): ...

    async def actuate(self, grant, preparation): ...

    async def observe(self, subject, request): ...

    async def reconcile(self, attempt, request): ...

    async def rollback(self, grant, attempt): ...

    async def health(self): ...


class MissingActuationShape:
    def metadata(self): ...

    def capabilities(self, subject=None): ...



def test_crown_provider_protocol_requires_full_provider_physics() -> None:
    assert isinstance(CompleteProviderShape(), CrownProvider)
    assert not isinstance(MissingActuationShape(), CrownProvider)


def test_spi_values_do_not_embed_ambient_authority() -> None:
    request = ObservationRequest(expected_revision="abc")
    assert request.expected_revision == "abc"
    assert "authority_ref" not in request.model_fields
    assert "authority_ref" not in ProviderPreparation.model_fields
    assert "authority_ref" not in ProviderExecutionAttempt.model_fields
    assert "authority_ref" not in ProviderRollbackResult.model_fields


def test_provider_attempt_keeps_acknowledgement_separate_from_standing() -> None:
    fields = ProviderExecutionAttempt.model_fields
    assert "acknowledgement_status" in fields
    assert "standing" in fields
    assert Standing.ALIVE != Standing.UNCERTAIN
