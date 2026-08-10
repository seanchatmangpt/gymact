"""Shared bounded-poll helper.

Extracted from three near-identical inline `deadline = time.monotonic() + timeout;
while ...: <check>; time.sleep(interval)` loops that were each independently
maintained in `gymact.gyms.sregym`, `gymact.gyms.kubernetes_reconciliation`, and
`gymact.gyms.terraform_docker_apply` (startup readiness, `verify()` convergence
polling, and `teardown()` deletion/destruction confirmation). No public ontology
term applies here -- this is pure control-flow, not a domain concept -- so per
`.claude/rules/ontology.md` no `gymact:` semantic term is introduced; this module
is plain Python kernel plumbing.

Both variants preserve the real call sites' existing behavior exactly: they use
real wall-clock `time.monotonic()` deadlines and real blocking `time.sleep()`
between checks (never `asyncio.sleep`, matching what the async call site
--`TerraformDockerApplyEnvironment.verify()`-- already did before extraction).
Neither variant raises on timeout; both return whether the condition became true
before the deadline, matching every real call site's own timeout handling (each
decides for itself what to do -- break and report, or raise with a
call-site-specific message -- once the boolean comes back `False`).
"""

from __future__ import annotations

import time
from collections.abc import Awaitable, Callable

__all__ = ["poll_until", "poll_until_async"]


def poll_until(
    condition: Callable[[], bool],
    *,
    timeout_seconds: float,
    interval_seconds: float,
) -> bool:
    """Poll a real synchronous `condition` until it returns `True` or a real
    `time.monotonic()` deadline elapses.

    Calls `condition()` once immediately, then -- while it keeps returning
    `False` and the deadline has not passed -- sleeps `interval_seconds` and
    calls it again. Returns the last observed boolean result. `condition` may
    raise; the exception propagates immediately, ending the poll (matching
    `sregym.py`'s startup loop, where a dead subprocess must abort the wait
    rather than be retried).
    """
    deadline = time.monotonic() + timeout_seconds
    ready = condition()
    while not ready and time.monotonic() < deadline:
        time.sleep(interval_seconds)
        ready = condition()
    return ready


async def poll_until_async(
    condition: Callable[[], Awaitable[bool]],
    *,
    timeout_seconds: float,
    interval_seconds: float,
) -> bool:
    """`await`-based twin of `poll_until` for a real async `condition` (e.g. one
    that itself `await`s a real environment's `observe()`).

    Uses a real blocking `time.sleep()` between checks, not `asyncio.sleep()` --
    this matches `TerraformDockerApplyEnvironment.verify()`'s pre-extraction
    behavior exactly, which polled a real `docker inspect`-observed state on a
    real blocking sleep despite running inside an `async def` method.
    """
    deadline = time.monotonic() + timeout_seconds
    ready = await condition()
    while not ready and time.monotonic() < deadline:
        time.sleep(interval_seconds)
        ready = await condition()
    return ready
