"""Shared contract: a degraded standing must be explicitly permitted, never
silently defaulted into.

A skipped test and a stubbed-out adapter path look identical to whatever
reads the outcome afterward -- "green," or "materialized" -- unless
something forces a visible distinction. Per
~/.claude/rules/testing-chicago-style.md, a missing real collaborator must
degrade to a *named, visible skip*, never a silent mock substitution. This
module is the other half of that rule: even a named, visible skip must be
something the run explicitly consented to, not something it silently got by
default. That consent has to be a runtime environment variable, not a
config-file or settings value -- a settings default is exactly the kind of
thing that becomes an unnoticed standing over time.

This lives in production code (not tests/) so it is a real contract any
adapter can share, not just test collaborators: an `EnvironmentProvider`
that ever gains a genuine degraded/simulated fallback path (none does today
-- `MemoryProvider` is a real deterministic reference world, not a stand-in
for something else; `CubeCounterProvider` and `GgenLegacyVerifierProvider`
each hard-require their real external collaborator) should gate that
fallback through `require_standing()` too, not invent its own flag.
"""

from __future__ import annotations

import os

_ENV_VAR = "GYMACT_ALLOW_DEGRADED_STANDINGS"


def _allowed_standings() -> frozenset[str]:
    raw = os.environ.get(_ENV_VAR, "")
    return frozenset(item.strip() for item in raw.split(",") if item.strip())


def require_standing(standing: str, *, available: bool, reason: str) -> None:
    """Real is the default. Degrading to a skip must be explicitly allowed.

    If `available` is True, this does nothing -- the real thing is present.

    If `available` is False, this fails loudly UNLESS the runtime
    environment variable GYMACT_ALLOW_DEGRADED_STANDINGS lists this exact
    `standing` string (or the wildcard "*"). Only then does it degrade to a
    named, visible skip.

    Under pytest, "fails loudly" is `pytest.fail(...)` and "skip" is
    `pytest.skip(..., allow_module_level=True)` -- both work whether this
    is called inside a test body or at module import time. Outside pytest
    (e.g. a future adapter's own runtime path), "fails loudly" is a raised
    RuntimeError; there is no non-pytest equivalent of "skip," so an
    allow-listed-but-unavailable standing there is the caller's problem to
    handle (raise, log, or otherwise surface -- require_standing only
    decides whether degrading is *permitted*, not what "degraded" means).
    """
    if available:
        return

    permitted = standing in _allowed_standings() or "*" in _allowed_standings()

    try:
        import pytest
    except ImportError:
        pytest = None  # type: ignore[assignment]

    if not permitted:
        message = (
            f"standing {standing!r} is not available in this run and "
            f"{_ENV_VAR} does not allow degrading it: {reason}\n"
            f'Set {_ENV_VAR}={standing!r} (or "*") to explicitly accept '
            "a skip instead of this failure."
        )
        if pytest is not None:
            pytest.fail(message, pytrace=False)
        raise RuntimeError(message)

    if pytest is not None:
        pytest.skip(reason, allow_module_level=True)
        return
    raise RuntimeError(
        f"standing {standing!r} is allow-listed as degradable but there is "
        f"no pytest skip mechanism outside a test run: {reason}"
    )
