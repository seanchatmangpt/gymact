"""BRCE production DO port: candidate -> admitted grant -> verified consequence."""
from __future__ import annotations

from typing import Any, Protocol

from pydantic import Field

from gymact.action_contract import ActionDefinition, ExecutionGrant, PreparedAction
from gymact.crown_runtime import VerifiedTransition, execute_admitted
from gymact.models import FrozenModel


class BrokerRuntime(Protocol):
    async def act(self, intent: Any) -> Any: ...

    async def verify(self, episode_id: str, expected: dict[str, Any]) -> Any: ...

    def _record(self, receipt: Any) -> Any: ...


class BrokerRequest(FrozenModel):
    action: ActionDefinition
    prepared: PreparedAction
    grant: ExecutionGrant
    current_revision: str | None = None
    expected: dict[str, Any] = Field(default_factory=dict)


class BRCEBroker:
    """Exclusive production-oriented DO facade.

    The broker exposes no raw ``act`` method. It accepts only a prepared candidate and
    an identity-bound ExecutionGrant, runs mechanical admission, delegates the provider
    consequence to the existing kernel, and returns independently verified standing.
    """

    def __init__(self, runtime: BrokerRuntime) -> None:
        self._runtime = runtime

    async def execute(self, request: BrokerRequest) -> VerifiedTransition:
        return await execute_admitted(
            self._runtime,
            request.action,
            request.prepared,
            request.grant,
            current_revision=request.current_revision,
            expected=request.expected,
        )
