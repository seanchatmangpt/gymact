"""Bounded concurrent automation over the GymAct MAPE-K consequence controller."""

from __future__ import annotations

from collections import Counter
from collections.abc import Sequence

import anyio
from pydantic import Field

from gymact.autonomic import AutonomicController, AutonomicOutcome, ConsequenceRequest
from gymact.models import FrozenModel, Standing


class AutomationPolicy(FrozenModel):
    max_concurrency: int = Field(default=8, ge=1)
    max_requests: int = Field(default=256, ge=1)


class AutomationBatchResult(FrozenModel):
    outcomes: tuple[AutonomicOutcome, ...]
    standing_counts: dict[str, int]
    verified_count: int

    @property
    def all_verified(self) -> bool:
        return bool(self.outcomes) and self.verified_count == len(self.outcomes)

    @property
    def terminal_count(self) -> int:
        return len(self.outcomes)


class AutonomicAutomation:
    """Execute an explicitly bounded request set with stable result ordering."""

    def __init__(
        self,
        controller: AutonomicController,
        *,
        policy: AutomationPolicy | None = None,
    ) -> None:
        self.controller = controller
        self.policy = policy or AutomationPolicy()

    async def run(self, requests: Sequence[ConsequenceRequest]) -> AutomationBatchResult:
        if len(requests) > self.policy.max_requests:
            raise ValueError(
                "REFUSED:AUTOMATION_REQUEST_LIMIT_EXCEEDED:"
                f"{len(requests)}>{self.policy.max_requests}"
            )
        if len({request.request_id for request in requests}) != len(requests):
            raise ValueError("REFUSED:DUPLICATE_AUTOMATION_REQUEST_ID")
        if not requests:
            return AutomationBatchResult(
                outcomes=(),
                standing_counts={},
                verified_count=0,
            )

        limiter = anyio.Semaphore(self.policy.max_concurrency)
        results: list[AutonomicOutcome | None] = [None] * len(requests)

        async def execute(index: int, request: ConsequenceRequest) -> None:
            async with limiter:
                results[index] = await self.controller.run(request)

        async with anyio.create_task_group() as task_group:
            for index, request in enumerate(requests):
                task_group.start_soon(execute, index, request)

        outcomes = tuple(result for result in results if result is not None)
        if len(outcomes) != len(requests):
            raise RuntimeError("AUTOMATION_RESULT_CARDINALITY_VIOLATION")
        counts = Counter(outcome.standing.value for outcome in outcomes)
        return AutomationBatchResult(
            outcomes=outcomes,
            standing_counts=dict(sorted(counts.items())),
            verified_count=sum(
                outcome.standing is Standing.ALIVE and outcome.verified for outcome in outcomes
            ),
        )
