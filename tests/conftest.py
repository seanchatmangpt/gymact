"""Test-conventional import point for the fail-real/allow-degraded contract.

The contract itself lives in `gymact.standing` (production code, not test
infrastructure) so adapters can share it too -- see that module's docstring.

Allocation tracing is intentionally enabled for the current integration court:
the exact-head Python matrix treats ResourceWarning as an error and has observed
unclosed sockets/event loops/AnyIO streams whose finalizers fire during unrelated
later tests. Tracing does not suppress or reclassify those warnings; it preserves
the strict failure while binding each leaked resource to its allocation site so
the owning lifecycle can be repaired rather than guessed at.

Collection is intentionally *not* global. `ConcurrentMcpDispatchTests` exercises
a real FastMCP failed-handshake path whose third-party client leaves unreachable
AnyIO resources behind despite a real best-effort `Client.close()`. That test
class already carries a narrow `PytestUnraisableExceptionWarning` exclusion for
this observed upstream gap. Collecting only after that class's call phase keeps
the known third-party finalizers inside their existing scoped policy instead of
moving them into unrelated later tests. Every other test remains fail-real under
the repository's warnings-as-errors policy.
"""

from __future__ import annotations

import gc
import tracemalloc

import pytest

from gymact.standing import require_standing as require_standing

# Five frames retain the owning allocation edge without turning the full
# 953-test matrix into a tracing benchmark. This is diagnostic evidence only:
# warnings remain errors and no standing is promoted by tracing itself.
if not tracemalloc.is_tracing():
    tracemalloc.start(5)


@pytest.hookimpl(trylast=True)
def pytest_runtest_call(item: pytest.Item) -> None:
    """Finalize the one admitted third-party failed-handshake leak in scope.

    The SREGym concurrency court intentionally drives real FastMCP clients into
    a deterministic failed-handshake path. Its class-local warning mark is the
    admitted boundary for FastMCP's observed unraisable cleanup defect. Running
    collection here, after the unittest call but before pytest leaves that test
    item, prevents those unreachable resources from being attributed to a later
    unrelated test. This hook does not close sockets/loops itself and does not
    filter, catch, downgrade, or ignore warnings anywhere else.

    Pytest 8.4's own unraisable-exception cleanup deliberately performs five GC
    passes because one pass does not necessarily finalize everything. Mirror
    that bounded cleanup depth here only at the owning FastMCP boundary; the
    predecessor's single pass was insufficient and left event-loop self-pipes
    to surface during unrelated later tests and session unconfigure.
    """
    if (
        item.path.name == "test_sregym_provider.py"
        and item.cls is not None
        and item.cls.__name__ == "ConcurrentMcpDispatchTests"
    ):
        for _ in range(5):
            gc.collect()


__all__ = ["require_standing"]