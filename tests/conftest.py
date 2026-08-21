"""Test-conventional import point for the fail-real/allow-degraded contract.

The contract itself lives in `gymact.standing` (production code, not test
infrastructure) so adapters can share it too -- see that module's docstring.

Allocation tracing is intentionally enabled for the current integration court:
the exact-head Python matrix treats ResourceWarning as an error and has observed
unclosed sockets/event loops/AnyIO streams whose finalizers fire during unrelated
later tests. Tracing does not suppress or reclassify those warnings; it preserves
the strict failure while binding each leaked resource to its allocation site so
the owning lifecycle can be repaired rather than guessed at.

The autouse collection fence below is the other half of that contract. Python
resource finalizers are otherwise free to run many tests after the object that
lost ownership, which makes the eventual pytest item a victim rather than the
owner. Forcing cyclic collection at every test teardown makes leaked resources
finalize at the narrowest deterministic ownership boundary. Pytest's unraisable
exception plugin still observes the resulting ResourceWarning during teardown,
so this is attribution, not suppression: a leaking test fails earlier and more
locally instead of poisoning a later unrelated test.
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


@pytest.fixture(autouse=True)
def collect_owned_resources_at_test_boundary():
    """Finalize unreachable resources before ownership can drift to another test.

    The fixture intentionally performs no warning filtering, exception handling,
    loop manipulation, or transport-specific cleanup. It merely establishes a
    deterministic GC boundary; any leaked socket, event loop, AnyIO stream, or
    other finalizer warning remains visible to pytest's existing strict court.
    """
    yield
    gc.collect()


__all__ = ["require_standing"]
