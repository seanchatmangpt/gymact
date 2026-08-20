"""Test-conventional import point for the fail-real/allow-degraded contract.

The contract itself lives in `gymact.standing` (production code, not test
infrastructure) so adapters can share it too -- see that module's docstring.

Allocation tracing is intentionally enabled for the current integration court:
the exact-head Python matrix treats ResourceWarning as an error and has observed
unclosed sockets/event loops/AnyIO streams whose finalizers fire during unrelated
later tests. Tracing does not suppress or reclassify those warnings; it preserves
the strict failure while binding each leaked resource to its allocation site so
the owning lifecycle can be repaired rather than guessed at.
"""

from __future__ import annotations

import tracemalloc

from gymact.standing import require_standing as require_standing

# Five frames retain the owning allocation edge without turning the full
# 953-test matrix into a tracing benchmark. This is diagnostic evidence only:
# warnings remain errors and no standing is promoted by tracing itself.
if not tracemalloc.is_tracing():
    tracemalloc.start(5)

__all__ = ["require_standing"]
