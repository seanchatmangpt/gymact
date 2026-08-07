"""Test-conventional import point for the fail-real/allow-degraded contract.

The contract itself lives in `gymact.standing` (production code, not test
infrastructure) so adapters can share it too -- see that module's docstring.
"""

from __future__ import annotations

from gymact.standing import require_standing as require_standing

__all__ = ["require_standing"]
